from datetime import date
from typing import Any, Sequence

from langchain_core.documents import Document as LCDocument
from langchain_postgres import PGEngine, PGVectorStore
from langchain_postgres.v2.indexes import HNSWQueryOptions
from pydantic import BaseModel

from models.statute import StatuteType
from rag.context_manager import get_db_session
from rag.law_category import LawName
from rag.model import embeddings
from sqlalchemy import Row, RowMapping, text
from sqlmodel import select, SQLModel

from db.session import async_engine
from models import ChatSpaceDocument, DocumentChunk
from models.document import Document, DocumentScope

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


def format_doc(doc: LCDocument, excluded_keys: list[str]) -> str:
    """llm에게 줄 정보 제한 및 추출"""

    # 2. 값이 제외되지 않은 경우에만 "키: 값" 문자열 생성 (None이나 빈 문자열은 제외)
    meta_parts = [
        f"'{k}': {v}"
        for k, v in doc.metadata.items()
        if (k not in excluded_keys)
        and v
        != "정보없음"  # 값이 존재하고(None 아님) 빈 문자열이나 "정보없음"도 아닌 경우
    ]

    # 3. 메타데이터와 본문 결합
    meta_str = ", ".join(meta_parts)
    return f"Source: {meta_str}\nContent: {doc.page_content}"


async def fetch_target_ids(
    document_scope: DocumentScope,
    space_id: int | None = None,
    search_filter: SearchFilter | None = None,
):
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


async def fetch_private_ids() -> list[int]:
    async with get_db_session() as session:
        statement = select(Document.document_id).where(
            Document.document_scope == DocumentScope.private
        )
        results = await session.exec(statement)
        target_doc_ids = results.all()
    return target_doc_ids


async def query_in_target(
    query: str, target_doc_ids: Sequence[Row[Any] | RowMapping | Any], k: int = 5
):
    """특정 document_id 범위 내에서 검색"""
    vector_store = await create_vector_store()
    relevant_chunks = await vector_store.asimilarity_search(
        query, k=k, filter={"document_id": {"$in": target_doc_ids}}
    )
    serialized = "\n\n".join(
        f"Source: {doc.metadata}\nContent: {doc.page_content}"
        for doc in relevant_chunks
    )
    return serialized, relevant_chunks


async def query_excluding_target(
    query: str,
    excluded_doc_ids: Sequence[Row[Any] | RowMapping | Any],
    excluded_meta_keys: list[str] | None = None,
    k: int = 5,
):
    """특정 document_id 범위 밖에서 검색"""
    vector_store = await create_vector_store()
    relevant_chunks = await vector_store.asimilarity_search(
        query, k=k, filter={"document_id": {"$nin": excluded_doc_ids}}
    )

    if excluded_meta_keys is None:
        excluded_meta_keys = []

    serialized = "\n\n".join(
        format_doc(doc, excluded_meta_keys) for doc in relevant_chunks
    )
    return serialized, relevant_chunks


EXCLUDED_PRECEDENT_KEYS = [
    "사건요지",
    "판례상세링크",
    "법원종류코드",
    "사건종류코드",
    "판례정보일련번호",
    "document_id",
]


async def query_in_precedent(
    query: str,
    query_filter: SearchFilter | None = None,
    k: int = 5,
) -> tuple[str, list[LCDocument]]:
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
    serialized = header + "\n\n".join(
        format_doc(doc, EXCLUDED_PRECEDENT_KEYS) for doc in relevant_chunks
    )
    return serialized, relevant_chunks


async def find_law_by_article(
    law_type: LawName, article: int
) -> tuple[str, list[LCDocument]]:
    """법령을 법령명과 조 번호로 검색."""
    relevant_chunks = []
    async with get_db_session() as session:
        statement = (
            select(DocumentChunk)
            .where(DocumentChunk.meta["법령명"].astext == str(law_type))
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
    serialized = f"법령명: {law_type}\n" + "\n".join(
        doc.page_content for doc in relevant_chunks
    )
    return serialized, relevant_chunks


# 결과 반환용 Pydantic 모델 (검색 결과는 Score가 포함되므로 별도 모델 권장)
class SearchResult(SQLModel):
    id: int
    title: str
    content: str
    score: float


async def search_statutes_filtered(
    query_text: str,
    statute_type: StatuteType | None = None,  # 법령구분명 용 필터
    limit: int = 5,
) -> list[SearchResult]:
    # 질문 임베딩
    query_vector = await embeddings.asembed_query(query_text)
    # 필터 조건문 생성
    filter_clause = ""
    if statute_type:
        filter_clause = "WHERE statute_type = :statute_type AND embedding IS NOT NULL"

    sql_query = text(f"""
WITH semantic_search AS (SELECT id,
                                title,
                                content,
                                1.0 / (ROW_NUMBER() OVER (ORDER BY embedding <=> :embedding) + 60) AS score
                         FROM statutes
                         {filter_clause}
                         ORDER BY embedding <=> :embedding
                         LIMIT 20),
     keyword_search AS (SELECT id,
                               title,
                               -- 점수 계산 시에도 동일 함수 사용
                               GREATEST(
                                       similarity(title, :query_text),
                                       similarity(immutable_array_to_string(alias::TEXT[], ' '), :query_text)
                               )           AS sim_score,
                               -- 랭킹용 점수 계산
                               1.0 / (ROW_NUMBER() OVER (
                                   ORDER BY GREATEST(similarity(title, :query_text),
                                                     (similarity(immutable_array_to_string(alias::TEXT[], ' '),
                                                                 :query_text))) DESC
                                   ) + 60) AS score
                        FROM statutes
                        WHERE (title % :query_text)
                           OR
                           -- [핵심] 인덱스 정의와 똑같은 함수를 써야 인덱스를 탑니다!
                            (immutable_array_to_string(alias::TEXT[], ' ') % :query_text)
                        LIMIT 20)
SELECT COALESCE(s.id, k.id)                          AS id,
       COALESCE(s.title, k.title)                    AS title,
       (COALESCE(s.score, 0) + COALESCE(k.score, 0)) AS final_score
FROM semantic_search s
         FULL OUTER JOIN keyword_search k ON s.id = k.id
ORDER BY final_score DESC
LIMIT :limit;
""")

    params = {"embedding": query_vector, "query_text": query_text, "limit": limit}
    if statute_type:
        params["statute_type"] = statute_type.value  # Enum의 실제 값("대통령령") 전달
    async with get_db_session() as db:
        results = (await db.exec(sql_query, params=params)).all()

    return [SearchResult(id=r.id, title=r.title, content=r.content, score=r.final_score) for r in results]
