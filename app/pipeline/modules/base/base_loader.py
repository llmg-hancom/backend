from abc import ABC, abstractmethod
import json
import re
from typing import Any
from pgvector.psycopg import register_vector
import psycopg
import logging

from tqdm import tqdm

from core.config import settings
from rag.model import embeddings

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
API_CONFIGS = {
    # 1. 일반 판례 (대법원 및 하급심)
    "prec": {
        "list_root": "PrecSearch",
        "data_root": 'prec',
        "detail_root": "PrecService",
        "filename_prefix": "prec",
        "detail_param": "ID",
        "serial_key": "판례일련번호",  # 목록에서 상세 ID 추출 시 사용
        "friendly_name": "일반 판례"  # ⭐️ 추가
    },

    # 2. 헌재 결정례 (헌법재판소)
    "detc": {
        "list_root": "DetcSearch",
        "data_root": "Detc",
        "detail_root": "DetcService",
        "filename_prefix": "detc",
        "detail_param": "ID",
        "serial_key": "헌재결정례일련번호",
        "friendly_name": "헌재 결정례"  # ⭐️ 추가
    },

    # 3. 행정 심판례 (국민권익위원회 등 재결례)
    "decc": {
        "list_root": "Decc",
        "data_root": "decc",
        "detail_root": "PrecService",  # 행정심판례 상세 응답은 'PrecService' 키를 사용함
        "filename_prefix": "decc",
        "detail_param": "ID",
        "serial_key": "행정심판재결례일련번호",
        "friendly_name": "행정 심판례"  # ⭐️ 추가
    },

    # 4. 현행 법령 (법령 본문)
    "eflaw": {
        "list_root": "LawSearch",
        "data_root": "law",
        "detail_root": "법령",  # 법령 상세 응답은 '법령' 키를 사용함
        "filename_prefix": "eflaw",
        "detail_param": "MST",  # 법령 상세 조회 시 '법령일련번호'를 'MST' 파라미터로 사용
        "serial_key": "법령일련번호",
        "friendly_name": "현행 법령"  # ⭐️ 추가
    },

    # 5. 법령 해석례 (법제처 법령 해석)
    "expc": {
        "list_root": "Expc",
        "data_root": "expc",
        "detail_root": "ExpcService",
        "filename_prefix": "expc",
        "detail_param": "ID",
        "serial_key": "법령해석례일련번호",
        "friendly_name": "법령 해석례"  # ⭐️ 추가
    }
}


# ABC를 상속받아야 추상 클래스로 기능합니다.
class BaseLoader(ABC):

    # ... (기존 __init__, connect_db 등 구현 메서드 유지) ...
    # ⭐️ 모든 Loader가 공통으로 사용하는 DB/Ollama 초기화 및 연결 로직
    def __init__(self, loader_type, markdown_splitter, recursive_splitter):
        self.loader_type = loader_type
        self.markdown_splitter = markdown_splitter
        self.recursive_splitter = recursive_splitter
        self.embeddings = embeddings

        config = API_CONFIGS[loader_type]
        self.friendly_name = config['friendly_name']

    def connect_db(self) -> psycopg.Connection | None:
        # Postgres 연결을 초기화하고 연결 객체를 반환합니다. """
        conn = None
        try:
            conn = psycopg.connect(settings.database_url)
            register_vector(conn)
            logger.info("PostgreSQL DB 연결 성공.")
            return conn
        except Exception as e:
            logger.error(f"[심각 오류] DB 연결 실패: {e}")
            return None

    def _add_markdown_headers_simplified(self, text: str, field_name) -> str:
        """
        판례 텍스트에 주요 구분자(【】, 가.나.다., ①②③)를 찾아 
        계층 없이 모두 ## 마크다운 헤더를 적용합니다.
        """
        # 원본 텍스트에 필드명 헤더 추가
        processed_text = text

        # 1. 【...】 헤더 (전문/재판부 정보 등) -> ##
        # (주의: 이미 앞에 ##가 붙어있을 수 있으므로 앞에 붙은 헤더를 제거하고 다시 붙입니다.)
        processed_text = re.sub(r"\s*(\【[^\】]+\】)\s*", r"\n\n## \1", processed_text, flags=re.MULTILINE)

        # 2. ①, ② (항/호 구분자) -> ##
        # 계층을 무시하고 ##를 적용합니다.
        # (앞에 붙은 ##나 공백을 무시하고 \n\n##를 적용합니다.)
        processed_text = re.sub(r"\s*(\①|\②|\③|\④|\⑤|\⑥|\⑦|\⑧|\⑨|\⑩|\⑪|\⑫|\⑬|\⑭|\⑮)", r"\n\n## \1", processed_text,
                                flags=re.MULTILINE)

        # 3. 가., 나. (목 구분자) -> ##
        # (주의: 줄 시작 부분의 들여쓰기된 한글(가., 나.) 구분자를 찾습니다.)
        # 사용자 코드의 패턴: ^\s*(가\.|나\.|...|)
        processed_text = re.sub(r"^\s*(가\.|나\.|다\.|라\.|마\.|바\.|사\.|아\.|자\.|차\.|카\.|타\.|파\.|하\.)", r"\n\n## \1",
                                processed_text, flags=re.MULTILINE)

        # 4. 숫자(1., 2.) 또는 한글(가., 나.) (판시사항/판결요지의 주요 구분자) -> ##
        # 사용자 코드의 패턴을 활용하되, 계층 없이 ##를 적용합니다.
        # ^\s*(\d+\.) 와 ^\s*(가\.|나\.|...)를 합쳐서 사용합니다.
        processed_text = re.sub(r"^\s*(\d+\.)", r"\n\n## \1", processed_text, flags=re.MULTILINE)
        # ⭐️ 5. TODO 채우기: [1], [2] 구분자 추가 -> ##
        # ^\s* : 줄 시작 부분의 공백을 허용
        # (\[\d+\]) : [ 숫자 ] 패턴을 캡처 그룹으로 지정
        processed_text = re.sub(r"\s*(\[\s*\d+\s*\])", r"\n\n## \1", processed_text, flags=re.MULTILINE)
        # --- 최종 정리 ---

        # 5. 불필요한 중복된 헤더를 정리 (예: ## ## 1. -> ## 1.)
        processed_text = re.sub(r"##\s*##", r"##", processed_text, flags=re.MULTILINE)

        # 6. 연속된 줄바꿈 정리
        processed_text = re.sub(r'\n\s*\n', '\n\n', processed_text)

        return processed_text

    @abstractmethod
    def _prepare_document(self, data: dict[str, Any]) -> dict[str, Any] | None:
        logger.info(f"Received Data Sample: {list(data.keys())[:10]}")

    def run_etl_pipeline(self, raw_data_list: list[dict[str, Any]]):
        # ⭐️ 모든 Loader가 공통으로 사용하는 ETL 파이프라인 뼈대
        # (DELETE, INSERT, COPY, COMMIT 트랜잭션 로직 포함)

        """
        메인 ETL 파이프라인: documents 테이블 스키마에 맞추어 삽입하고 
        1️⃣ document_id를 받아 chunks 테이블에 삽입합니다.
        2️⃣ 문서별로 커밋을 수행하여 안정성을 높입니다.
        3️⃣ (문서가 이미 존재하면 삭제 후 재삽입)
        """
        # run_loader_worker가 파일 경로에서 데이터를 읽어 리스트 형태로 변환하여 전달해 주어야 합니다.

        with self.connect_db() as conn:
            try:
                config = API_CONFIGS[self.loader_type]
                friendly_name = config.get('friendly_name')
                if not raw_data_list: raise Exception(f"No {friendly_name} data provided.")

                documents_to_insert = [self._prepare_document(p) for p in raw_data_list]
                documents_to_insert = [d for d in documents_to_insert if d is not None]

                if not documents_to_insert: raise Exception("No valid documents could be prepared for insertion.")

                cur = conn.cursor()

                # --- 쿼리 정의 ---

                # 1. 기존 문서 ID 조회 쿼리 (삭제/재삽입용)
                select_existing_id_query = "SELECT document_id FROM documents WHERE file_path = %s;"

                # 2. 문서 및 청크 삭제 쿼리
                delete_document_query = "DELETE FROM documents WHERE document_id = %s;"

                # 3. 문서 삽입 쿼리 (삭제 후이므로 ON CONFLICT는 필요 없습니다.)
                insert_doc_query = """
                                   INSERT INTO documents (file_name, file_path, uploaded_by_user_id, document_scope, status)
                                   VALUES (%s, %s, %s, %s, %s)
                                   RETURNING document_id; \
                                   """

                # 4. 청크 삽입 쿼리
                insert_chunks_query = """
                                      INSERT INTO document_chunks (document_id, content, embedding, meta)
                                      VALUES (%s, %s, %s, %s); \
                                      """
                # ----------------

                processed_doc_count = 0
                inserted_chunk_count = 0

                for doc in tqdm(documents_to_insert, desc="Processing Documents"):
                    try:
                        doc_tuple = (
                            doc['file_name'],
                            doc['file_path'],
                            doc['uploaded_by_user_id'],
                            doc['document_scope'],
                            doc['status']
                        )

                        # 1. 기존 문서 확인 및 삭제
                        cur.execute(select_existing_id_query, (doc['file_path'],))
                        existing_result = cur.fetchone()

                        if existing_result:
                            existing_doc_id = existing_result[0]
                            # cascade delete를 가정하지 않고 documents 테이블만 명시적으로 삭제.
                            # document_chunks 테이블도 삭제되어야 합니다.
                            # (DB 스키마에 따라 document_chunks의 document_id에 ON DELETE CASCADE가 걸려있어야 합니다.)
                            cur.execute(delete_document_query, (existing_doc_id,))
                            logger.info(
                                f"기존 Document ID {existing_doc_id} ('{doc['file_name']}') 삭제 완료 (file_path 중복).")

                        # 2. 새로운 documents 테이블 삽입 및 document_id 획득
                        cur.execute(insert_doc_query, doc_tuple)
                        inserted_result = cur.fetchone()

                        if not inserted_result:
                            # 이 경우는 발생하지 않아야 하지만, 안전을 위해 체크
                            logger.error(f"Document 삽입 실패: {doc['file_name']}")
                            conn.rollback()
                            continue

                        document_id = inserted_result[0]
                        logger.debug(f"Document ID {document_id} 삽입 완료. 청크 분할 시작.")

                        # 3. 청크 분할 및 임베딩 생성
                        full_content = doc["page_content"]
                        metadata = doc["metadata"]

                        initial_chunks = self.markdown_splitter.split_text(full_content)

                        all_chunks_for_doc: list[tuple] = []
                        chunk_index = 0

                        for chunk in initial_chunks:
                            sub_chunks = self.recursive_splitter.split_text(chunk) if len(chunk) > 1000 else [chunk]

                            for sub_chunk in sub_chunks:
                                # 임베딩 벡터 생성
                                embedding_vector = self.embeddings.embed_query(sub_chunk)

                                # 청크 메타데이터 준비 (meta 필드로 들어갈 JSONB)
                                chunk_meta = metadata.copy()

                                logger.debug(
                                    f"[Chunk] DOC ID={document_id}, Index={chunk_index}: "
                                    f"Length={len(sub_chunk)}, Content='{sub_chunk[:50]}...'"
                                )
                                # chunks 테이블 삽입 튜플 준비 (document_id, content, embedding, meta)
                                all_chunks_for_doc.append((
                                    document_id,
                                    sub_chunk,
                                    str(embedding_vector),
                                    json.dumps(chunk_meta, ensure_ascii=False),
                                ))
                                chunk_index += 1

                        # (구) 4. document_chunks 테이블에 청크 데이터 일괄 삽입 (현재 문서 청크만)
                        # 4. document_chunks 테이블에 청크 데이터 일괄 삽입 (COPY 사용)
                        if all_chunks_for_doc:
                            count_current_doc = len(all_chunks_for_doc)
                            logger.info(f"Document ID {document_id}에 대해 총 {count_current_doc}개의 청크를 일괄 삽입합니다.")

                            # ⭐️⭐️⭐️ [수정된 부분] psycopg 3 표준 COPY 방식 ⭐️⭐️⭐️
                            # 별도의 import 없이 cursor 객체의 copy 메서드를 사용합니다.
                            with cur.copy(
                                    "COPY document_chunks (document_id, content, embedding, meta) FROM STDIN") as copy:
                                for chunk in all_chunks_for_doc:
                                    copy.write_row(chunk)

                            # 5. 현재 문서 삽입 및 청크 삽입을 커밋 (문서별 커밋)
                            conn.commit()
                            processed_doc_count += 1
                            logger.info(f"✅ Document ID {document_id} 및 청크 삽입/커밋 완료.")
                        else:
                            logger.warning(f"Document ID {document_id}의 청크 데이터가 없어 document_chunks 삽입을 건너뜁니다.")
                            conn.commit()
                            processed_doc_count += 1

                    except Exception as doc_error:
                        logger.error(
                            f"Document '{doc.get('file_name', 'Unknown')}' 처리 중 오류 발생: {doc_error}. 해당 문서는 롤백됩니다.")
                        conn.rollback()  # 현재 문서에 대한 모든 작업 롤백
                        continue  # 다음 문서로 이동

                    logger.info(
                        f"=== ETL 파이프라인 최종 요약: {processed_doc_count}개의 {self.friendly_name} 문서 처리 완료, 총 {inserted_chunk_count}개의 청크 삽입/갱신 완료. ===")
                    cur.close()

            except Exception as e:
                logger.error(f"FATAL ETL ERROR (전체 파이프라인): {e}")
                conn.rollback()  # 전체 파이프라인 시작 전 오류나 최악의 경우 롤백

            finally:
                logger.info("=== ETL 파이프라인 종료.")
