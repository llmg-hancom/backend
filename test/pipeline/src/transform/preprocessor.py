import re
import glob
import os
import json # ⭐ json 모듈 추가
from typing import Any, Dict, List, Optional
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_core.documents import Document

def get_text(file_path: str) -> Optional[str]:
    """
    주어진 파일 경로에서 최종 텍스트를 반환합니다. (이전 대화에서 수정한 함수)
    """
    try:
        # 파일에서 텍스트 읽어오기 (읽기 모드 'r')
        with open(file_path, 'r', encoding='utf-8') as f:
            input_text = f.read()
    except Exception as e:
        print(f"[오류] 파일 읽기 실패 ({os.path.basename(file_path)}): {e}")
        return None

    lines = input_text.splitlines()
    return "\n".join(lines)

# 계층적 마크다운 헤더(##, ###, ####, #####)를 적용합니다.
def preprocess_law_text( text: str) -> str:
    """
    법률 텍스트에 계층적 마크다운 헤더(##, ###, ####, #####)를 적용합니다.
    """
    # 제1조, 제1조의2 (조) -> ##
    # (제목 포함 여부와 관계없이)
    text = re.sub(r"^(제\d+조(?:의\d+)?\s*\(.*?\))", r"]\n\n## \1", text, flags=re.MULTILINE)
    
    # ①, ② (항) -> ###
    text = re.sub(r"(①|②|③|④|⑤|⑥|⑦|⑧|⑨|⑩|⑪|⑫|⑬|⑭|⑮)", r"\n\n### \1", text, flags=re.MULTILINE)
    
    # 1., 2. (호) -> ####
    # 들여쓰기된 숫자(호)도 처리하도록 \s* 추가
    text = re.sub(r"^\s*(\d+\.)", r"#### \1", text, flags=re.MULTILINE)
    
    # 가., 나. (목) -> #####
    # 들여쓰기된 한글(목)도 처리하도록 \s* 추가
    text = re.sub(r"^\s*(가\.|나\.|다\.|라\.|마\.|바\.|사\.|아\.|자\.|차\.|카\.|타\.|파\.|하\.)", r"\n\n##### \1", text, flags=re.MULTILINE)
    
    return text


def get_txt_files_in_folder(target_folder: str) -> List[str]:
    """
    glob 모듈을 사용하여 폴더 내의 모든 .txt 파일의 전체 경로 리스트를 반환합니다.
    """
    search_path = os.path.join(target_folder, "*.txt")
    return glob.glob(search_path)

# ⭐⭐ Document 리스트를 JSON 파일로 저장하는 새로운 함수 ⭐⭐
def save_chunks_to_json(chunks: List[Document], output_filepath: str):
    """
    LangChain Document 객체 리스트를 JSON 파일로 저장합니다.
    
    Args:
        ⚠️ ⚠️ chunks: 저장할 Document 객체 리스트.
        output_filepath: 저장할 JSON 파일 경로.
    """
    # Document 객체를 JSON 직렬화가 가능한 딕셔너리 리스트로 변환
    serialized_chunks = []
    for chunk in chunks:
        serialized_chunks.append({
            "page_content": chunk.page_content,
            "metadata": chunk.metadata
        })
        
    try:
        # JSON 파일로 저장 (ensure_ascii=False로 한글 깨짐 방지, indent=4로 가독성 높임)
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(serialized_chunks, f, ensure_ascii=False, indent=4)
        
        print(f"\n[JSON 저장 완료] 총 {len(chunks)}개의 청크가 '{output_filepath}'에 저장되었습니다.")
        
    except Exception as e:
        print(f"\n[JSON 저장 오류] 파일을 저장하지 못했습니다: {e}")


def process_and_chunk_all_laws(target_folder: str) -> List[Document]:
    #TXT -> Document list
    
    # 1. 분할 기준 정의 (LangChain MarkdownHeaderTextSplitter)
    headers_to_split_on = [
        ("##", "조"),      # Article (예: ## 제1조(목적))
        ("###", "항"),     # Paragraph (예: ### ①)
        ("####", "호"),    # Sub-paragraph (예: #### 1.)
        ("#####", "목")    # Item (예: ##### 가.)
    ]
    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        strip_headers=False # 헤더를 내용에 포함시켜 문맥 유지
    )

    # 2. 최종 재귀적 분할기 정의 (RecursiveCharacterTextSplitter)
    recursive_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, 
        chunk_overlap=100,
        length_function=len
    )
    
    all_final_chunks: List[Document] = []
    
    # 3. .txt 파일 목록 가져오기
    txt_files = get_txt_files_in_folder(target_folder)
    print(f"--- 폴더 '{target_folder}'에서 총 {len(txt_files)}개의 .txt 파일을 찾았습니다. ---")

    if not txt_files:
        print("경고: 처리할 .txt 파일이 없습니다.")
        return all_final_chunks

    # 4. 파일별로 처리 시작
    for file_path in txt_files:
        law_filename = os.path.basename(file_path)
        law_name = os.path.splitext(law_filename)[0] # 파일 이름 (예: 근로기준법)
        print(f"\n[처리 시작] 법령명: {law_name} ({law_filename})")
        
        # a. 텍스트 읽기 및 페이지 구분자 제거
        raw_text = get_text(file_path)
        if not raw_text:
            continue
        
        # b. 마크다운 헤더 전처리 적용
        markdown_text = preprocess_law_text(raw_text)
        
        # c. 1차 분할: 마크다운 헤더 기준 분할 (조, 항, 호, 목 단위 분할 시도)
        try:
            chunks_by_header = md_splitter.split_text(markdown_text)
            print(f"  [1차 분할]: 마크다운 헤더 기준으로 {len(chunks_by_header)}개의 청크 생성.")
        except Exception as e:
            print(f"  [오류]: {law_name}의 1차 분할 중 오류 발생: {e}")
            continue

        # d. 2차 분할 및 메타데이터 추가
        for chunk in chunks_by_header:
            
            # 메타데이터에 법령명 추가
            chunk.metadata["source_type"] = '법령'
            chunk.metadata["법령명"] = law_name
            # 메타데이터에 원본 파일명 추가 (선택 사항) 비 효율적
            # chunk.metadata["source"] = law_filename 

            # 청크 크기가 설정치(1000자)보다 큰지 확인
            if len(chunk.page_content) > 1000:
                # 너무 크면, 재귀적 분할기를 사용하여 세부 분할
                sub_chunks = recursive_splitter.create_documents(
                    [chunk.page_content],
                    metadatas=[chunk.metadata] # 부모의 메타데이터 상속
                )
                all_final_chunks.extend(sub_chunks)
                print(f"  [2차 분할]: 대형 청크({len(chunk.page_content)}자)를 {len(sub_chunks)}개로 추가 분할.")
            else:
                # 크기가 적당하면 그대로 추가
                all_final_chunks.append(chunk)

    print(f"\n--- 모든 파일 처리 완료! 최종적으로 총 {len(all_final_chunks)}개의 청크가 생성되었습니다. ---")
    return all_final_chunks


if __name__ == "__main__":
    # '/raw_data'로 시작하면 절대 경로로 인식될 수 있습니다.
    base_dir = os.path.dirname(__file__)
    target_folder_name = 'raw_data' 
    target_folder_path = os.path.join(base_dir, target_folder_name)

    # 2. 디렉토리 존재 확인 및 생성 로직 추가
    if not os.path.exists(target_folder_path):
        # 'exist_ok=True'는 이미 디렉토리가 있어도 오류를 발생시키지 않도록 합니다.
        # 'os.makedirs'는 필요한 경우 중간 디렉토리도 모두 생성해 줍니다.
        os.makedirs(target_folder_path, exist_ok=True)
        print(f"'{target_folder_path}' 디렉토리를 생성했습니다.")
    else:
        print(f"'{target_folder_path}' 디렉토리는 이미 존재합니다.")
    
    all_final_chunks = process_and_chunk_all_laws(target_folder_path)
    # ⭐️ 소스파일과 같은 디렉토리에 결과물 저장 
    save_chunks_to_json(all_final_chunks, target_folder_path)
    