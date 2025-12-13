from datetime import date
from typing import Any, Sequence, Literal
from warnings import deprecated

import numpy as np
from langchain_core.documents import Document as LCDocument
from langchain_core.vectorstores.utils import maximal_marginal_relevance
from langchain_postgres import PGEngine, PGVectorStore
from langchain_postgres.v2.indexes import HNSWQueryOptions
from pydantic import BaseModel

from models.statute import StatuteType
from rag.context_manager import get_db_session
from rag.law_category import StatuteTitle
from rag.model import embeddings
from sqlalchemy import Row, RowMapping, text
from sqlmodel import select, or_

from db.session import async_engine
from models import ChatSpaceDocument, DocumentChunk

pg_engine = PGEngine.from_engine(async_engine)


async def create_vector_store(fetch_k: int = 20, ef_search: int = 40) -> PGVectorStore:
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
            added_meta["document_id"] = candidates[i].document_id
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
            relevant_chunks.append(LCDocument(page_content=chunk.content, metadata=md))

    return relevant_chunks
