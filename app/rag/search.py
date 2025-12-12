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
from models import ChatSpaceDocument, Document, DocumentChunk
from models.document import DocumentScope

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
    case_numbers: list[str] | None = None
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
    k: int = 5,
    fetch_k: int = 20,
    ef_search: int = 40,
) -> list[LCDocument]:
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
                if precedent_filter.case_numbers:
                    sql_query = sql_query.where(
                        DocumentChunk.meta["사건번호"].astext.in_(
                            precedent_filter.case_numbers
                        )
                    )
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
    document_scope: DocumentScope,
    space_id: int | None = None,
    search_filter: SearchFilter | None = None,
) -> list[int]:
    """query 검색 범위 설정. 법령, 개인 문서의 경우 항상 해당하는 document_id 반환.
    판례의 경우 search_filter가 존재하면 해당 조건을 만족하는 chunk_id 반환,
    search_filter가 존재하지 않으면 판례가 **아닌** document_id 반환."""
    async with get_db_session() as session:
        match document_scope:
            # 법령 검색의 경우 법령인 document id를 반환
            case DocumentScope.public_law:
                statement = select(Document.document_id).where(
                    Document.document_scope == DocumentScope.public_law
                )
            # 판례 검색
            case DocumentScope.precedent:
                # search_filter가 존재하는 경우 범위 내 chunk_id 반환
                if search_filter:
                    statement = select(DocumentChunk.chunk_id)
                    if search_filter.start_date:
                        statement = statement.where(
                            DocumentChunk.meta["선고일자"].astext
                            >= search_filter.start_date.strftime("%Y%m%d")
                        )
                    if search_filter.end_date:
                        statement = statement.where(
                            DocumentChunk.meta["선고일자"].astext
                            <= search_filter.end_date.strftime("%Y%m%d")
                        )
                    if search_filter.case_numbers:
                        statement = statement.where(
                            DocumentChunk.meta["사건번호"].astext.in_(
                                search_filter.case_numbers
                            )
                        )
                # search_filter가 존재하지 않는 경우 판례가 **아닌** 범위의 document_id 반환
                else:
                    statement = select(Document.document_id).where(
                        Document.document_scope != DocumentScope.precedent
                    )
            # 개인 문서 검색의 경우 space_id에 속한 document_id 반환
            case DocumentScope.private:
                statement = select(ChatSpaceDocument.document_id).where(
                    ChatSpaceDocument.space_id == space_id
                )
        results = await session.exec(statement)
        target_doc_ids = results.all()
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


# 결과 반환용 Pydantic 모델 (검색 결과는 Score가 포함되므로 별도 모델 권장)


@deprecated("Use `legal_similarity_search` for legal search instead.")
async def fetch_private_ids() -> list[int]:
    async with get_db_session() as session:
        statement = select(Document.document_id).where(
            Document.document_scope == DocumentScope.private
        )
        results = await session.exec(statement)
        target_doc_ids = results.all()
    return target_doc_ids


@deprecated("Use `legal_similarity_search` for legal search instead.")
async def query_in_precedent(
    query: str,
    query_filter: SearchFilter | None = None,
    k: int = 5,
) -> list[LCDocument]:
    """판례 검색. query_filter가 존재하는 경우 chunk_id로 필터링,
    존재하지 않는 경우 제외된 document_id로 필터링"""
    vector_store = await create_vector_store(40, 64)
    header = ""
    # 검색 조건이 존재하는 경우 chunk id로 필터링
    if query_filter:
        included_chunk_ids = await fetch_target_ids(
            DocumentScope.precedent, search_filter=query_filter
        )
        if query_filter.case_numbers:
            header = f"[사건번호] {' '.join(query_filter.case_numbers)}\n"
        search_filter: dict = {"chunk_id": {"$in": included_chunk_ids}}
    # 검색 조건이 없는 경우 성능을 위해 판례가 아닌 범위의 document_id로 필터링
    else:
        excluded_doc_ids = await fetch_target_ids(DocumentScope.precedent)
        search_filter: dict = {"document_id": {"$nin": excluded_doc_ids}}
    relevant_chunks: list[LCDocument] = await vector_store.asimilarity_search(
        query, k=k, filter=search_filter
    )
    if query_filter.case_numbers and len(query_filter.case_numbers) == 1:
        header += f"[판결요지] {relevant_chunks[0].metadata.get('판결요지', '없음')}\n"
        header += f"[판시시항] {relevant_chunks[0].metadata.get('판시사항', '없음')}\n"
    return relevant_chunks


@deprecated("deprecated")
async def query_excluding_target(
    query: str,
    excluded_doc_ids: Sequence[Row[Any] | RowMapping | Any],
    k: int = 5,
) -> list[LCDocument]:
    """특정 document_id 범위 밖에서 검색"""
    vector_store = await create_vector_store()
    relevant_chunks = await vector_store.asimilarity_search(
        query, k=k, filter={"document_id": {"$nin": excluded_doc_ids}}
    )
    return relevant_chunks