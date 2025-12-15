from datetime import date
from typing import Any, Sequence, Literal

import numpy as np
from langchain_core.documents import Document as LCDocument
from langchain_core.vectorstores.utils import maximal_marginal_relevance
from langchain_postgres import PGEngine, PGVectorStore
from langchain_postgres.v2.indexes import HNSWQueryOptions
from pydantic import BaseModel
from sqlalchemy import Row, RowMapping, text
from sqlmodel import select, or_

from db.session import async_engine
from models import ChatSpaceDocument, DocumentChunk
from models.statute import StatuteType
from rag.context_manager import get_db_session
from rag.law_category import StatuteTitle
from rag.model import embeddings

pg_engine = PGEngine.from_engine(async_engine)


async def create_vector_store(fetch_k: int = 40, ef_search: int = 80) -> PGVectorStore:
    vector_store = await PGVectorStore.create(
        engine=pg_engine,
        embedding_service=embeddings,
        table_name="document_chunks",
        id_column="chunk_id",
        metadata_columns=["document_id"],
        metadata_json_column="meta",
        fetch_k=fetch_k,
        index_query_options=HNSWQueryOptions(ef_search=ef_search),
    )
    return vector_store


# 판례 검색을 위한 필터
class SearchFilter(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    case_numbers: list[str] | None = None


class StatuteFilter(BaseModel):
    titles: list[str] | None = None
    types: list[StatuteType] | None = None

    @property
    def is_empty(self) -> bool:
        return not bool(self.model_dump(exclude_none=True))


class PrecedentFilter(BaseModel):
    case_number: str | None = None
    start_date: date | None = None
    end_date: date | None = None

    @property
    def is_empty(self) -> bool:
        # None이 아닌 값이 하나라도 있으면 False (비어있지 않음)
        return not bool(self.model_dump(exclude_none=True))


# 법/판례 유사도 검색
async def legal_similarity_search(
        query_text: str,
        target: Literal["public_law", "precedent", "legal"] = "legal",
        statute_filter: StatuteFilter | None = None,
        precedent_filter: PrecedentFilter | None = None,
        k: int = 3,
        fetch_k: int = 40,
        ef_search: int = 80,
) -> list[LCDocument]:
    """
    법률 및 판례 유사도 검색을 수행합니다.

    Args:
        query_text (str): 검색할 쿼리 텍스트.
        target (Literal["public_law", "precedent", "legal"], optional): 검색 대상.
            "public_law"는 법령만, "precedent"는 판례만, "legal"은 법령과 판례 모두를 검색합니다.
            기본값은 "legal"입니다.
        statute_filter (StatuteFilter | None, optional): 법령 검색을 위한 필터.
        precedent_filter (PrecedentFilter | None, optional): 판례 검색을 위한 필터.
        k (int, optional): 최종적으로 반환할 문서 청크의 개수. 기본값은 3입니다.
        fetch_k (int, optional): 초기 검색에서 가져올 후보 문서 청크의 개수. 기본값은 40입니다.
        ef_search (int, optional): HNSW 인덱스 검색 시 ef_search 파라미터 값. 기본값은 80입니다.

    Returns:
        list[LCDocument]: 검색된 관련 문서 청크 목록. 각 청크는 Langchain의 Document 객체입니다.

    """
    query_vector = np.array(await embeddings.aembed_query(query_text))
    if precedent_filter and not precedent_filter.is_empty:
        target = "precedent"

    sql_query = select(DocumentChunk)
    match target:
        case "legal":
            if statute_filter is None or statute_filter.is_empty:
                sql_query = sql_query.where(
                    or_(
                        DocumentChunk.meta["법령명"].astext.is_not(None),
                        DocumentChunk.meta["사건번호"].astext.is_not(None),
                    )
                )
            else:
                if statute_filter.titles:
                    sql_query = sql_query.where(
                        or_(
                            DocumentChunk.meta["법령명"].astext.in_(
                                statute_filter.titles
                            ),
                            DocumentChunk.meta["사건번호"].astext.is_not(None),
                        )
                    )
                elif statute_filter.types:
                    sql_query = sql_query.where(
                        or_(
                            DocumentChunk.meta["법령타입"].astext.in_(
                                statute_filter.types
                            ),
                            DocumentChunk.meta["사건번호"].astext.is_not(None),
                        )
                    )
        case "public_law":
            if statute_filter is None or statute_filter.is_empty:
                sql_query = sql_query.where(
                    DocumentChunk.meta["법령명"].astext.is_not(None)
                )
            else:
                if statute_filter.titles:
                    sql_query = sql_query.where(
                        DocumentChunk.meta["법령명"].astext.in_(statute_filter.titles)
                    )
                elif statute_filter.types:
                    sql_query = sql_query.where(
                        DocumentChunk.meta["법령타입"].astext.in_(statute_filter.types),
                    )
        case "precedent":
            if precedent_filter is None or precedent_filter.is_empty:
                sql_query = sql_query.where(
                    DocumentChunk.meta["사건번호"].astext.is_not(None)
                )
            else:
                if precedent_filter.case_number:
                    sql_query = sql_query.where(DocumentChunk.meta["사건번호"].astext == precedent_filter.case_number)
                if precedent_filter.start_date:
                    sql_query = sql_query.where(
                        DocumentChunk.meta["선고일자"].astext
                        >= precedent_filter.start_date.strftime("%Y%m%d")
                    )
                if precedent_filter.end_date:
                    sql_query = sql_query.where(
                        DocumentChunk.meta["선고일자"].astext
                        <= precedent_filter.end_date.strftime("%Y%m%d")
                    )
    sql_query = sql_query.order_by(
        DocumentChunk.embedding.cosine_distance(query_vector)
    ).limit(fetch_k)
    relevant_chunks: list[LCDocument] = []
    async with get_db_session() as db:
        await db.exec(text(f"SET hnsw.ef_search = {ef_search}"))
        candidates: list[DocumentChunk] = (await db.exec(sql_query)).all()
        doc_embeddings = [chunk.embedding for chunk in candidates]
        selected_indices = maximal_marginal_relevance(
            query_embedding=query_vector,
            embedding_list=doc_embeddings,  # 후보군 fetch_k개의 벡터 리스트
            k=k,  # 최종적으로 뽑을 개수
            lambda_mult=0.5,  # 0~1 사이 (0.5가 기본, 낮을수록 다양성 중시)
        )
        # 4. 결과 매핑 (인덱스를 이용해 원본 내용 가져오기)
        for i in selected_indices:
            added_meta = candidates[i].meta.copy()
            added_meta.update({"document_id": candidates[i].document_id, "chunk_id": candidates[i].chunk_id})
            relevant_chunks.append(
                LCDocument(page_content=candidates[i].content, metadata=added_meta)
            )
    return relevant_chunks


async def fetch_target_ids(
        space_id: int | None = None,
) -> list[int]:
    """space_id에 속한 개인 문서 id 목록 반환."""
    async with get_db_session() as session:
        statement = select(ChatSpaceDocument.document_id).where(
            ChatSpaceDocument.space_id == space_id
        )
        target_doc_ids = (await session.exec(statement)).all()
    return target_doc_ids


async def query_in_target(
        query: str, target_doc_ids: Sequence[Row[Any] | RowMapping | Any], k: int = 5
) -> list[LCDocument]:
    """특정 document_id 범위 내에서 검색"""
    vector_store = await create_vector_store()
    relevant_chunks = await vector_store.asimilarity_search(
        query, k=k, filter={"document_id": {"$in": target_doc_ids}}
    )

    return relevant_chunks


async def find_law_by_article(
        statute_title: StatuteTitle | str, article: int
) -> list[LCDocument]:
    """법령을 법령명과 조 번호로 검색."""
    relevant_chunks = []
    async with get_db_session() as session:
        statement = (
            select(DocumentChunk)
            .where(DocumentChunk.meta["법령명"].astext == str(statute_title))
            .where(
                text(
                    "(SUBSTRING(meta ->> '조' FROM '제([0-9]+)조')::INT) = :article"
                ).params(article=article)
            )
            .order_by(DocumentChunk.chunk_id)
        )
        results = await session.exec(statement)
        raw_chunks = results.all()
        for chunk in raw_chunks:
            md = {k: v for k, v in chunk.meta.items() if v != "정보없음"}
            relevant_chunks.append(
                LCDocument(page_content=chunk.content,
                           metadata=md | {"chunk_id": chunk.chunk_id, "document_id": chunk.document_id}))

    return relevant_chunks


async def query_private_document(
        query_text: str,
        space_id: int,
        k: int = 5,
        fetch_k: int = 40,
        ef_search: int = 80,
) -> list[LCDocument]:
    target_doc_ids = await fetch_target_ids(space_id)
    # 질문 임베딩
    query_vector = await embeddings.aembed_query(query_text)

    sql_query = text(
"""
WITH semantic_search AS (SELECT chunk_id,
                                document_id,
                                content,
                                meta,
                                1.0 / (ROW_NUMBER() OVER (ORDER BY embedding <=> :embedding) + 60) AS score
                         FROM document_chunks
                         WHERE document_id = ANY (:target_doc_ids)
                         ORDER BY embedding <=> :embedding
                         LIMIT :fetch_k),
     keyword_search AS (SELECT d.file_name,
                               d.document_scope,
                               dc.chunk_id,
                               dc.document_id,
                               content,
                               meta,
                               -- 점수 계산 시에도 동일 함수 사용
                               GREATEST(
                                       similarity(d.file_name, :query_text),
                                       similarity((meta ->> 'title'), :query_text),
                                       similarity((meta ->> 'keyword'), :query_text)
                               )           AS sim_score,
                               -- 랭킹용 점수 계산
                               1.0 / (ROW_NUMBER() OVER (
                                   ORDER BY
                                       -- 1순위: 완전 일치 여부 (True가 False보다 위로)
                                       (meta ->> 'title') = :query_text DESC,
                                       GREATEST(
                                               similarity(d.file_name, :query_text),
                                               similarity((meta ->> 'title'), :query_text),
                                               similarity((meta ->> 'keyword'), :query_text)) DESC
                                   ) + 60) AS score
                        FROM document_chunks dc
                                 LEFT JOIN public.documents d ON d.document_id = dc.document_id
                        WHERE dc.document_id = ANY (:target_doc_ids)
                          AND (((d.file_name) % :query_text AND
                                d.document_scope = 'private'::documentscope)
                            OR
                               (((meta ->> 'title') % :query_text) AND (meta ->> 'title') IS NOT NULL)
                            OR
                               (((meta ->> 'keyword') LIKE '%' || :query_text || '%') AND
                                (meta ->> 'keyword') IS NOT NULL))
                        LIMIT :fetch_k)
SELECT COALESCE(s.chunk_id, k.chunk_id)              AS chunk_id,
       COALESCE(s.document_id, k.document_id)        AS document_id,
       COALESCE(s.content, k.content)                AS content,
       COALESCE(s.meta, k.meta)                      AS metadata,
       (COALESCE(s.score, 0) + COALESCE(k.score, 0)) AS final_score
FROM semantic_search s
         FULL OUTER JOIN keyword_search k ON s.chunk_id = k.chunk_id
ORDER BY (COALESCE(s.meta, k.meta) ->> 'title') = :query_text DESC,
         final_score DESC
LIMIT :k""")

    params = {"target_doc_ids": target_doc_ids, "embedding": str(query_vector), "query_text": query_text, "k": k,
              "fetch_k": fetch_k}
    async with get_db_session() as db:
        await db.exec(text(f"SET hnsw.ef_search = {ef_search}"))
        results = (await db.exec(sql_query, params=params)).all()

    return [
        LCDocument(page_content=r[2], metadata=(r[3] or {}) | {"chunk_id": r[0], "document_id": r[1]})
        for r in results
    ]
