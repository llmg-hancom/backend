import os
import requests
import psycopg2
import json
import re # NOTE: re 라이브러리를 사용하지 않는 로직을 구현했으나, clean_and_add_markdown_simple 내에서 최종 결합 시 re.sub가 일부 사용됩니다.
from pgvector.psycopg2 import register_vector 
from langchain_community.embeddings import OllamaEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from datetime import datetime
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from psycopg2.extensions import connection, cursor


# --- 환경 설정 ---
LIST_URL = "https://www.scourt.go.kr/portal/news/NewsListAction.work?gubun=4&type=5"
BASE_URL = "https://www.scourt.go.kr" 

OLLAMA_MODEL = "bge-m3:567m" 

DB_USER='admin'
DB_PASSWORD='d4bca2ff7e99cfef0d8f'
DB_NAME='hwp_qna_db'
DB_CONFIG={
    'database' : DB_NAME,
    'user': DB_USER,
    'password': DB_PASSWORD,
    'host': 'localhost',
    'port': 5432
}
def conn_embedding_model(local_host, local_port, ollama_local_port):
    """DB와 Ollama에 연결하고 커서 객체를 반환합니다."""
    
    OLLAMA_TUNNEL_URL = f"http://{local_host}:{ollama_local_port}/"
    
    embeddings = OllamaEmbeddings(
        model=OLLAMA_MODEL, 
        base_url=OLLAMA_TUNNEL_URL 
    )
    
    db_config_tunnel = DB_CONFIG.copy()
    db_config_tunnel['host'] = local_host
    db_config_tunnel['port'] = local_port
    
    conn = None
    try:
        conn = psycopg2.connect(**db_config_tunnel)
        conn.autocommit = False 
        register_vector(conn)
        cur = conn.cursor()
        return embeddings, conn, cur
    except Exception as e:
        print(f"[ERROR] DB 연결 실패: {e}")
        return embeddings, None, None 


def extract_case_number_from_contarea(soup):
    
    # 1. 원하는 요소 (td 클래스="contArea")를 찾습니다.
    cont_area_td = soup.select_one('td.contArea')
    
    if not cont_area_td:
        print("[ERROR] 'td.contArea' 영역을 찾을 수 없습니다.")
        return None

    # 2. contArea 내의 첫 번째 <p> 태그를 찾습니다.
    first_p_tag = cont_area_td.find('p')
    
    if not first_p_tag:
        print("[ERROR] 'td.contArea' 내에 첫 번째 <p> 태그를 찾을 수 없습니다.")
        return None
    raw_text = first_p_tag.get_text('\n\n', strip=True) 
    # ⭐️ get_text()는 특정 태그(여기서는 <p>)와 그 하위 태그들 내의 모든 텍스트 노드들을 
    # 하나로 합쳐서 반환합니다. 이때, 하나의 태그가 끝나고 다른 태그가 시작될 때 
    # 해당 인자(여기서는 공백 문자 ' ')를 넣어 텍스트를 분리해 줍니다.
    # 4. 공백을 기준으로 문자열을 나눕니다.
    # split()은 연속된 공백을 하나로 처리합니다.
    parts = raw_text.split()
    
    if parts:
        # 첫 번째 항목을 판례번호로 추출합니다. (예: '2024다298448')
        case_number = parts[0]
        
        print(f"추출된 raw 텍스트: '{raw_text}'")
        print(f"추출된 판례번호: {case_number}")
        return case_number
    else:
        print("[ERROR] 추출된 텍스트가 없습니다.")
        return None


def insert_document_and_get_id(cur, pdf_filename, pdf_url):
    """documents 테이블에 삽입하고 document_id를 RETURNING 받습니다."""
    
    insert_query = """
    INSERT INTO documents 
    (file_name, file_path, uploaded_by_user_id, document_scope, status)
    VALUES ( %s, %s, %s, %s, %s)
    RETURNING document_id; 
    """
    
    try:
        cur.execute(insert_query, (pdf_filename, pdf_url, 1, 'precedent', 'ready'))
        document_id = cur.fetchone()[0]
        return document_id
    except Exception as e:
        print(f"[ERROR] Documents 테이블에 삽입 실패: {e}")
        return None
# ----------------------------------------------------------------------
# Helper 3: HTML 본문 추출 및 마크다운 구조화
# ----------------------------------------------------------------------
def get_header_keys():
    # 💡 수정된 SYMBOL_PREFIXES 정의
    # 아라비아 숫자: 1부터 9까지 (f-string 사용)
    # 1. 아라비아 숫자 (1. ~ 9., 1) ~ 9))
    # numeric_dots = [ f'{i}.' for i in range(1, 10)]
    numeric_paren = [ f'{i})' for i in range(1, 10)]

    # # 2. 한글 순번 (가. ~ 하., 가) ~ 하))
    # hangul_dots = [f'{chr(i)}.' for i in range(ord('가'), ord('하') + 1)]
    # hangul_paren = [f'{chr(i)})' for i in range(ord('가'), ord('하') + 1)]

    # 3. 원문자 순번 (① ~ ⑩, ①. ~ ⑩.)
    circle_number_base = [chr(i) for i in range(0x2460, 0x2469 + 1)]
    circle_number_dots = [f'{c}.' for c in circle_number_base]

    # 4. 기타 기호
    other_symbols = ['◇', '☞','[']
    return list(numeric_paren + circle_number_dots + other_symbols)

def preprocess_text_to_markdown(text: str) -> str:
    header_keys: List[str] = get_header_keys()
    processed_text = text
    for key in header_keys:
        processed_text = processed_text.replace(key, f"\n## {key.strip()}\n", 1)
    return processed_text.strip()

def split_markdown_chunks_with_fallback(
    text: str,
    max_chunk_size: int = 500,
    chunk_overlap: int = 50,
    headers_to_split_on = [
        ("##", "Section_Level_2"), 
        ("###", "Section_Level_3")
],
) -> List[Dict]:

    full_text = re.sub(r'\n{3,}', '\n\n', text)
    print(f"    [청킹할 텍스트] {full_text[:300]}")

    # 1차 분할
    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on, strip_headers=False
    )
    first_split_documents = md_splitter.split_text(text)

    # 2차 분할 초기화
    recursive_splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
        length_function=len,
    )
    final_chunks = []

    for doc in first_split_documents:
        content = doc.page_content
        metadata = doc.metadata

        if len(content) > max_chunk_size:
            second_split_documents = recursive_splitter.create_documents([content])
            for sub_doc in second_split_documents:
                sub_doc.metadata.update(metadata)
                final_chunks.append(
                    {"page_content": sub_doc.page_content, "metadata": sub_doc.metadata}
                )
        else:
            final_chunks.append({"page_content": content, "metadata": metadata})


    return final_chunks

def get_new_precedent_urls(local_host, local_port, ollama_local_port):
    _, conn, cur = conn_embedding_model(local_host, local_port, ollama_local_port)
    
    if conn is None:
        return []
    
    # ⭐️ 1. DB에서 마지막 처리 날짜 가져오기 (precedent_date 기준)
    last_precedent_date = None
    try:
        cur.execute("SELECT MAX(precedent_date) FROM precedent_log;")
        result = cur.fetchone()[0]
        conn.close() 
        
        if result:
            last_precedent_date = result
            print(f"마지막 처리 날짜: {last_precedent_date.strftime('%Y-%m-%d')} 이후 데이터를 확인합니다.")
        else:
            print("처리 이력이 없습니다. 전체 목록을 확인합니다.")
    except Exception as e:
        print(f"[DB 오류] precedent_log 쿼리 실패: {e}")
        conn.close()
        return []

    # 2. 판례 목록 크롤링 및 날짜/링크 필터링
    try:
        response = requests.get(LIST_URL, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"크롤링 오류 발생: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    rows = soup.select('table.tableHor tr')
    all_candidate_urls = []
    
    for row in rows:
        link = row.select_one('td.tit a') 
        date_tag = row.select_one('td:nth-child(4)') 
        
        if link and date_tag and date_tag.text.strip():
            href = link.get('href') 
            date_str = date_tag.text.strip()
            
            try:
                precedent_date = datetime.strptime(date_str, '%Y-%m-%d').date() 
            except ValueError:
                continue 
            
            abs_url = requests.compat.urljoin(BASE_URL, href) 
            
            is_recent_enough = True
  
            if last_precedent_date:
                if precedent_date <= last_precedent_date:
                    is_recent_enough = False 
            
            if is_recent_enough and 'NewsViewAction.work' in abs_url:
                all_candidate_urls.append(abs_url)

    if not all_candidate_urls:
        print("날짜 필터링 후, 크롤링할 신규 URL이 없습니다.")
        return []
        
    new_urls = list(set(all_candidate_urls))
    print(f"날짜 필터링 후 최종 신규 판례 {len(new_urls)}개 발견. (상세 페이지 URL)")
    return new_urls

def extract_precedent_metadata(soup: BeautifulSoup, detail_url: str) -> Optional[Dict[str, Any]]:
 
    
    def get_text_after_th(th_text: str) -> str:
        """특정 <th> 태그 뒤의 <td> 텍스트를 안전하게 추출합니다."""
        th = soup.find('th', string=lambda t: t and th_text in t.strip())
        target_td = th.find_next_sibling('td') if th else None
        return target_td.text.strip() if target_td else f"{th_text} 없음"

    try:
        # 1. 메타데이터 추출
        precedent_title = get_text_after_th('제목')
        precedent_date_str = get_text_after_th('작성일')
        
        # 날짜가 추출되지 않았다면 현재 날짜 사용
        if "없음" in precedent_date_str:
            precedent_date_str = datetime.now().strftime('%Y-%m-%d')
            
        # PDF URL/파일명 추출 (로그 기록용)
        file_link_tag = soup.find('a', href=lambda href: href and href.lower().endswith('.pdf'))
        pdf_href = file_link_tag.get('href') if file_link_tag else detail_url
        pdf_filename = os.path.basename(pdf_href)
        
        # 판례번호 추출 (td.contArea의 첫 번째 <p> 가정)
        case_num = extract_case_number_from_contarea(soup) # 외부 함수 호출
        
        # 2. 본문 텍스트 추출 (raw_text)
        content_div = soup.find('td', class_='contArea') 
        # NOTE: 원본 코드의 \n\n 분리자를 유지하여 추출 (효율적)
        raw_text = content_div.get_text('\n\n', strip=True) if content_div else ""
        
        if not raw_text.strip():
            print("   [SKIP] 추출된 본문 텍스트가 없습니다.")
            return None

        # 3. 데이터 구조 반환
        return {
            'title': precedent_title,
            'date_str': precedent_date_str,
            'pdf_href': pdf_href,
            'pdf_filename': pdf_filename,
            'case_num': case_num,
            'raw_text': raw_text
        }
    except Exception as e:
        print(f"   [ERROR] 메타데이터 추출 중 오류 발생: {e}")
        return None


def insert_embeddings_and_log_chunks(
    document_id: int, 
    texts: List[Dict], 
    precedent_data: Dict[str, Any],
    embeddings: OllamaEmbeddings, 
    conn: connection, 
    cur: cursor
) -> int:
    """
    청크 리스트를 받아 임베딩을 생성하고 DB에 삽입합니다.
    청크 삽입 중 오류가 발생해도 다음 청크로 넘어가며, 성공한 청크 수를 반환합니다.
    
    Args:
        document_id (int): documents 테이블에서 얻은 고유 ID.
        texts (List[Dict]): 청킹된 텍스트 내용 리스트.
        precedent_data (Dict[str, Any]): 판례의 메타데이터 딕셔너리.
        embeddings (OllamaEmbeddings): 임베딩 생성 클라이언트.
        conn (connection): 활성화된 DB 연결 객체.
        cur (cursor): DB 커서 객체.
        
    Returns:
        int: 성공적으로 DB에 삽입된 청크의 개수.
    """
    total_chunks = len(texts)
    successful_chunks = 0
    embeded_texts = []
    try:
        # 1. 임베딩 생성
        for i, chunk in enumerate(texts):
            # 💡 수정: chunk['page_content']를 사용하여 텍스트 내용을 먼저 추출
            content = chunk['page_content'] 
            embeded_texts.append(content)
        texts = embeded_texts
        vectors = embeddings.embed_documents(texts)
    except Exception as e:
        print(f"   [ERROR] Ollama 임베딩 생성 실패: {e}. 청크 삽입을 건너뜀.")
        return 0
        
    # 2. Chunk 데이터 삽입 (document_chunks)
    insert_chunk_query = """
    INSERT INTO document_chunks 
    (document_id, content, embedding, meta)
    VALUES (%s, %s, %s, %s);
    """
    
    for i, (text, vector) in enumerate(zip(texts, vectors)):
        try:
            # pgvector 형식 문자열 변환
            vector_str = "[" + ",".join(map(str, vector)) + "]"
            
            # 메타데이터 구성 (기존 precedent_data를 기반으로)
            meta_data_json = {
                "case_num": precedent_data.get('case_num'),
                "source_url": precedent_data['pdf_href'],
                "precedent_title": precedent_data['title'],
                "attached_filename": precedent_data['pdf_filename'],
                "chunk_index": i
            }
            
            cur.execute(insert_chunk_query, (
                document_id,
                text,
                vector_str,
                json.dumps(meta_data_json, ensure_ascii=False)
            ))
            successful_chunks += 1
            
        except Exception as e:
            # 요구사항 반영: 청크 삽입 중 오류나면 중단하지 않고 다음 청크로 넘어감
            print(f"[WARNING] Chunk {i+1}/{total_chunks} 삽입 실패 (ID: {document_id}): {e}")
            continue

    return successful_chunks

def process_precedent_data(local_host, local_port, ollama_local_port, detail_url: str):
    
    embeddings, conn, cur =  conn_embedding_model(local_host, local_port, ollama_local_port)
    
    if conn is None:
        return
    
    # 1. 상세 페이지 접속
    try:
        response = requests.get(detail_url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"   [ERROR] 상세 페이지 접근/파싱 실패: {e}")
        conn.close()
        return

    # 2. 메타데이터 및 raw_text 추출 (새 함수 호출)
    precedent_data = extract_precedent_metadata(soup, detail_url)
    if precedent_data is None:
        conn.close()
        return
    
    # 3. 텍스트 전처리 및 분할
    full_text = preprocess_text_to_markdown(precedent_data['raw_text']) # 외부 함수 호출
    texts = split_markdown_chunks_with_fallback(full_text) # 외부 함수 호출
    # ----------------------------------------------------
    # 💡 수정된 로깅 코드: Dictionary 구조 참조 및 출력 강화
    # ----------------------------------------------------
    print(f"\n--- 청킹 결과 요약 ({len(texts)} chunks) ---")
    for i, chunk_dict in enumerate(texts):
        # 1. 'page_content' 키를 사용하여 텍스트 내용 추출
        content = chunk_dict.get('page_content', '[NO CONTENT]')
        
        # 2. 'metadata' 키를 사용하여 메타데이터 추출 (JSONB 삽입 전 디버깅)
        metadata = chunk_dict.get('metadata', {})
        
        # 3. 로그 출력 (내용 앞부분 100자와 메타데이터를 함께 출력)
        print(f"  [Chunk {i+1}] (Len: {len(content)}): ")
        print(f"    Content Start: '{content[:100].replace('\n', ' ')}...'")
        print(f"    Metadata: {metadata}") 
        
    print("-------------------------------------------\n")
    # 로그 출력 
    print(f"\n--- 청킹 결과 요약 ({len(texts)} chunks) ---")
    for i, chunk in enumerate(texts):
        # 💡 수정: chunk['page_content']를 사용하여 텍스트 내용을 먼저 추출
        content = chunk['page_content'] 
        print(f"  [Chunk {i+1}]: '{content[:100].replace('\n', ' ')}...'")
    print("-------------------------------------------\n")


    # 4. Document 테이블에 먼저 삽입 시도 및 ID 획득
    document_id = insert_document_and_get_id(cur, precedent_data['pdf_filename'], precedent_data['pdf_href'])

    if document_id is None:
        conn.close()
        return

    # 5. 청크 처리 및 DB 삽입 (새 함수 호출)
    successful_chunks = insert_embeddings_and_log_chunks(
        document_id, texts, precedent_data, embeddings, conn, cur
    )

    # 6. 로그 기록 및 트랜잭션 커밋
    if successful_chunks > 0:
        insert_log_query = """
        INSERT INTO precedent_log (precedent_url, precedent_date, title)
        VALUES (%s, %s, %s)
        ON CONFLICT (precedent_url) DO NOTHING;
        """
        try:
            # precedent_date_str을 datetime.date 객체로 변환하여 삽입
            precedent_date = datetime.strptime(precedent_data['date_str'], '%Y-%m-%d').date()
            cur.execute(insert_log_query, (detail_url, precedent_date, precedent_data['title']))
        except Exception as e:
            print(f"[ERROR] 로그 기록 실패: {e}")

        conn.commit()
        print(f"[SUCCESS] {successful_chunks} 청크 삽입 및 로그 완료.")
    else:
        conn.rollback()
        print("[WARNING] 청크 삽입 성공 건수 0. 트랜잭션 롤백.")

    conn.close()
    return f"Processed {detail_url}"
# ----------------------------------------------------------------------
# 5. 메인 워크플로우 (update_rag_index)
# ----------------------------------------------------------------------

def update_rag_index(local_host, local_port, ollama_local_port):
    """
    신규 URL 목록을 가져와 각 URL에 대해 처리 작업을 실행합니다.
    (Celery Worker의 Task가 호출할 수 있는 메인 함수)
    """
    print("\n--- RAG 데이터 최신화 작업 시작 ---")
    
    url_links = get_new_precedent_urls(local_host, local_port, ollama_local_port)
    
    if not url_links:
        print("신규 판례가 없어 작업을 종료합니다.")
        return
        
    for url in url_links:
        result = process_precedent_data(local_host, local_port, ollama_local_port, url)
        print(f"처리 요약: {result}")
    
    print("\n--- RAG 데이터 최신화 작업 완료 ---")
    return

if __name__ == "__main__":
    print("스크립트 실행을 위해서는 update_rag_index(host, port, ollama_port)를 호출해야 합니다.")