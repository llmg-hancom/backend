
import json
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import MarkdownTextSplitter, RecursiveCharacterTextSplitter
import psycopg
from tqdm import tqdm
from typing import List, Dict, Any, Tuple, override
from pgvector.psycopg import register_vector
import logging
from pydantic import BaseModel, Field

from modules.base.base_loader import BaseLoader
# ✅ 조 항 호 목 -> 목 청크 삽입하는 로직 추가
#  로깅 파일에 기록되도록 추가 Processing list element
# ✅ 조항내용, 항내용, 호내용이 리스트일때 예외 처리 추가 
# 연속된 공백을 삭제하고 깨끗한 텍스트를 넣는 로직

# -----------------------------------------------------------------

# --- 설정 변수 및 로깅 설정 ---
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------
class LawLoader(BaseLoader):
    
    def __init__(self, db_local_port, ollama_local_port):
        # 청킹 스플리터 초기화
        markdown_splitter = MarkdownTextSplitter(chunk_size=10000, chunk_overlap=0)
        recursive_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", " ", ""], chunk_size=1000, chunk_overlap=100
        )
        
        return super().__init__('eflaw',
                                db_local_port,
                                ollama_local_port,
                                markdown_splitter=markdown_splitter,
                                recursive_splitter=recursive_splitter)

    
 
    @override
    def _prepare_document(self, law_data: Dict[str, Any]) -> Dict[str, Any] | None:
        """
        법령 상세 데이터(API 응답값)에서 청크를 추출하고,
        documents 테이블 삽입에 필요한 메타데이터와 청크 리스트를 포함하는
        단일 딕셔너리 구조를 반환합니다.
        """
           # 콘텐츠 값을 문자열로 변환하는 헬퍼 함수
        
        # 1. 문서 기본 정보 추출 및 접근 경로 수정
        # law_data가 이미 API 응답의 루트 데이터라고 가정하고, '법령' 키를 건너뛰고 접근합니다.
        base_info = law_data.get("기본정보", {})
        
        # 필수 키 안전 추출 (법령키 -> 법령ID로 수정)
        law_serial_id = base_info.get("법령ID") # law_data.get("법령", {}).get("법령키") -> base_info.get("법령ID")
        law_name = base_info.get("법령명_한글", "알수없음")
        
        # '법종구분'은 딕셔너리 안에 'content' 키가 있으므로, 예전 코드를 유지합니다.
        law_type = base_info.get("법종구분", {}).get("content", "법률") 
        enforce_date = base_info.get("시행일자", "")
        
        if not law_serial_id or law_name == "알수없음":
            # logger.warning(f"필수 법령 정보 누락: ID={law_serial_id}, Name={law_name}")
            return None

        # 2. documents 테이블 메타데이터 (file_path, file_name)
        file_name = f"{law_name} ({enforce_date})"
        file_path = f"eflaw_{law_serial_id}_{enforce_date}"
        
        
        # 3. 청크 분할 및 메타데이터 생성
        all_chunks_data: List[Tuple[str, Dict]] = []
        
        # '조문' 키의 접근 경로 수정 (law_data.get("법령", {}) -> law_data)
        jo_list = law_data.get("조문", {}).get("조문단위", [])
        
        # API 응답에서 단일 조문일 경우 dict로 올 수 있으므로 리스트로 변환
        if isinstance(jo_list, dict):
            jo_list = [jo_list]
        elif jo_list is None:
            jo_list = []

        for jo in jo_list:
            jo_no = jo.get("조문번호", "")
            jo_title = jo.get("조문제목", "")
            jo_content = jo.get("조문내용", "")
            if isinstance(jo_content, list):
                jo_content = jo_content[0][0]
            
            # 3-1. 조문 자체 청크 생성 (항/호가 없는 경우)
            if jo_content and jo_content != f"제{jo_no}조 삭제": # 삭제 조문 제외
                meta_jo = {
                    'source': "현행법령",
                    '법령명':law_name,
                    '법령타입': law_type,
                    '조': f"제{jo_no}조",
                    '항': "정보없음",
                    '호': "정보없음"
                }
                # 청크 텍스트는 조문제목 + 내용으로 구성
                chunk_text = f"[{jo_title}] {jo_content}" if jo_title else jo_content
                all_chunks_data.append((chunk_text, meta_jo))

            # 3-2. 항 순회
            hang_list = jo.get("항", [])
            if isinstance(hang_list, dict):
                hang_list = [hang_list] # API 응답이 단일 항목을 dict로 줄 수 있음
                
            for hang in hang_list:
                # 항이 딕셔너리 형태일 때만 처리
                if not isinstance(hang, dict):
                    continue
                    
                hang_no = hang.get("항번호", "정보없음")
                hang_content = hang.get("항내용", "")
                if isinstance(hang_content, list):
                    hang_content = hang_content[0][0]
                
                # 항 자체 청크 생성 (호가 없는 경우)
                # '호' 키가 딕셔너리 내부에 직접 존재하지 않는 경우에만 항 자체를 청크로 만듭니다.
                if hang_content and '호' not in hang: 
                    meta_hang = {
                        'source': "현행법령",
                        '법령명':law_name,
                        '법령타입':law_type,
                        '조':f"제{jo_no}조",
                        '항': hang_no,
                        '호': "정보없음"
                    }
                    # 항번호를 내용에 붙여 청크 텍스트 생성
                    chunk_content = f"[{hang_no}] {hang_content}"
                    all_chunks_data.append((chunk_content, meta_hang))
                
                # 3-3. 호 순회 (가장 구체적인 단위)
                ho_list = hang.get("호", [])
                if isinstance(ho_list, dict):
                    ho_list = [ho_list]
                elif ho_list is None:
                    ho_list = []
                    
                for ho in ho_list:
                    # 호가 딕셔너리 형태일 때만 처리
                    if not isinstance(ho, dict):
                        continue
                        
                    ho_no = ho.get("호번호", "정보없음")
                    ho_content = ho.get("호내용", "")
                    if isinstance(ho_content,list):
                        ho_content = ho_content[0][0]
                    
                    if ho_content:
                        meta_ho = {
                            'source':"현행법령",
                            '법령명':law_name,
                            '법령타입':law_type,
                            '조':f"제{jo_no}조",
                            '항':hang_no,
                            '호':ho_no
                        }
                        # 호번호를 내용에 붙여 청크 텍스트 생성
                        chunk_text = f"{ho_no} {ho_content}"
                        all_chunks_data.append((chunk_text, meta_ho))
                        
                    # --- [추가된 부분: 목 순회 로직] ---
                    mok_list = ho.get("목", [])
                    if isinstance(mok_list, dict):
                        mok_list = [mok_list]
                    elif mok_list is None:
                        mok_list = []
                    
                    for mok in mok_list:
                        if not isinstance(mok, dict):
                            continue
                            
                        mok_no = mok.get("목번호", "정보없음")
                        mok_content = mok.get("목내용", "") # 중첩 리스트 처리된 내용
                        if isinstance(mok_content, list):
                            mok_content = mok_content[0][0]
                        if mok_content:
                            meta_mok = {
                                'source':"현행법령",
                                '법령명':law_name,
                                '법령타입':law_type,
                                '조':f"제{jo_no}조",
                                '항':hang_no,
                                '호':ho_no,
                                '목':mok_no # '목' 메타데이터 추가
                            }
                            # 목번호를 내용에 붙여 청크 텍스트 생성
                            # (예: 가. 요양급여 \n 1) 진료비... \n 2) 세부내역서...)
                            chunk_text = f"{mok_no} {mok_content}"
                            all_chunks_data.append((chunk_text, meta_mok))
                    # --- [추가된 부분 끝] ---
        
        # 4. 최종 반환 구조 생성
        return {
            'chunks': all_chunks_data,
            'file_name': file_name,
            'file_path': file_path,
            'uploaded_by_user_id': 1,
            'document_scope': 'public_law',
            'status': 'ready'
        }

    # ----------------------------------------------------------------------
    # ⭐️ run_etl_pipeline 메서드 (법령 데이터 특성에 맞게 재구성)
    # ----------------------------------------------------------------------

    def run_etl_pipeline(self, law_data_list: List[Dict[str, Any]]):
        """
        메인 ETL 파이프라인: 법령 상세 데이터를 기반으로 청크를 생성하고 DB에 일괄 삽입합니다.
        문서가 이미 존재하면 삭제 후 재삽입합니다 (COPY 사용).
        """
        
        conn = self.connect_db()
        if not conn: return
        
        try:
            if not law_data_list: raise Exception("No law data provided.")
            
            # 법령 데이터 리스트를 개별 문서 구조로 변환
            documents_to_process = [self._prepare_document(d) for d in law_data_list]
            documents_to_process = [d for d in documents_to_process if d is not None]

            if not documents_to_process: raise Exception("No valid documents could be prepared for insertion.")
            
            cur = conn.cursor()
            
            # --- 쿼리 정의 ---
            select_existing_id_query = "SELECT document_id FROM documents WHERE file_path = %s;"
            delete_document_query = "DELETE FROM documents WHERE document_id = %s;"
            insert_doc_query = """
                INSERT INTO documents (file_name, file_path, uploaded_by_user_id, document_scope, status)
                VALUES (%s, %s, %s, %s, %s) 
                RETURNING document_id;
            """
            copy_sql = "COPY document_chunks (document_id, content, embedding, meta) FROM STDIN"
            # ----------------
            
            processed_doc_count = 0
            inserted_chunk_count = 0
            
            for doc in tqdm(documents_to_process, desc="Processing Law Documents"):
                try:
                    doc_tuple = (
                        doc['file_name'], 
                        doc['file_path'], 
                        doc['uploaded_by_user_id'], 
                        doc['document_scope'], 
                        doc['status']
                    )

                    # 1. 기존 문서 확인 및 삭제 (재삽입 로직)
                    cur.execute(select_existing_id_query, (doc['file_path'],))
                    existing_result = cur.fetchone()
                    
                    if existing_result:
                        existing_doc_id = existing_result[0]
                        cur.execute(delete_document_query, (existing_doc_id,))
                        logger.info(f"기존 Document ID {existing_doc_id} ('{doc['file_name']}') 삭제 완료 (file_path 중복).")
                        
                    # 2. 새로운 documents 테이블 삽입 및 document_id 획득
                    cur.execute(insert_doc_query, doc_tuple)
                    inserted_result = cur.fetchone()
                    
                    if not inserted_result:
                        logger.error(f"Document 삽입 실패: {doc['file_name']}")
                        conn.rollback() 
                        continue

                    document_id = inserted_result[0]
                    logger.debug(f"Document ID {document_id} 삽입 완료. 청크 임베딩 시작.")
                    
                    # 3. 청크 텍스트 및 메타데이터 준비
                    chunks_with_meta: List[Tuple[str, Dict]] = doc['chunks']
                    chunk_texts = [content for content, meta in chunks_with_meta]
                    
                    # 4. 임베딩 벡터 생성 (일괄 처리)
                    embeddings_list = self.embeddings.embed_documents(chunk_texts)
                    
                    # 5. DB 삽입 튜플 리스트 최종 생성
                    all_chunks_for_doc: List[Tuple] = []
                    
                    for i, (content, meta) in enumerate(chunks_with_meta):
                        # ⭐️ pgvector를 위한 str 변환 적용
                        embedding_vector_str = str(embeddings_list[i]) 
                        
                        all_chunks_for_doc.append((
                            document_id,
                            content,
                            embedding_vector_str,
                            json.dumps(meta, ensure_ascii=False), # JSONB 문자열로 변환
                        ))

                    # 6. document_chunks 테이블에 청크 데이터 일괄 삽입 (COPY 사용)
                    if all_chunks_for_doc:
                        count_current_doc = len(all_chunks_for_doc)
                        logger.info(f"Document ID {document_id}에 대해 총 {count_current_doc}개의 청크를 일괄 삽입합니다 (COPY).")
                        
                        # ⭐️⭐️⭐️ psycopg 3 표준 COPY 방식 ⭐️⭐️⭐️
                        with cur.copy(copy_sql) as copy:
                            for chunk in all_chunks_for_doc:
                                copy.write_row(chunk)
                        
                        inserted_chunk_count += count_current_doc
                        
                        # 7. 현재 문서 삽입 및 청크 삽입을 커밋
                        conn.commit()
                        processed_doc_count += 1
                        logger.info(f"✅ Document ID {document_id} 및 청크 삽입/커밋 완료.")
                    else:
                        logger.warning(f"Document ID {document_id}의 청크 데이터가 없어 document_chunks 삽입을 건너뜁니다.")
                        conn.commit() 
                        processed_doc_count += 1 

                except Exception as doc_error:
                    logger.error(f"Document '{doc.get('file_name', 'Unknown')}' 처리 중 오류 발생: {doc_error}. 해당 문서는 롤백됩니다.")
                    conn.rollback() 
                    continue
            
            logger.info(f"=== ETL 파이프라인 최종 요약: {processed_doc_count}개의 문서 처리 완료, 총 {inserted_chunk_count}개의 청크 삽입/갱신 완료. ===")
            cur.close()

        except Exception as e:
            logger.error(f"FATAL ETL ERROR (전체 파이프라인): {e}")
            conn.rollback() 
            
        finally:
            if conn: conn.close()
            if self.ssh_tunnel:
                self.ssh_tunnel.stop()
                logger.info("SSH Tunnel closed.")