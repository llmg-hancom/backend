import os

from langchain_community.document_loaders import PyPDFLoader


# PDF to Text 변환 및 정제 함수
def pdf_to_text(pdf_path, output_path):
    # PyPDFLoader를 사용하여 PDF를 로드하고 텍스트로 추출하여 저장합니다.

    if not os.path.exists(pdf_path):
        print(f" 오류: PDF 파일 경로를 찾을 수 없습니다: {pdf_path}")
        return

    print(f" PDF 파일 로드 시작: {pdf_path}")

    try:
        # 1. PyPDFLoader 초기화 및 PDF 로드
        # PDF 파일의 각 페이지는 별도의 Document 객체로 로드됩니다.
        loader = PyPDFLoader(pdf_path)
        pages = loader.load()

        if not pages:
            print(" 로드된 페이지가 없습니다. 파일이 비어 있거나 손상되었을 수 있습니다.")
            return

        # 2. 모든 페이지의 텍스트 콘텐츠를 하나의 문자열로 합치기
        all_text = ""
        for page in pages:
            # Document 객체의 'page_content' 속성에 텍스트가 담겨 있습니다.
            all_text += page.page_content[2:] + "\n\n"
            # 페이지 컨텐츠 로그 

        # 3. 텍스트 파일로 저장
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(all_text)

        print(f" 텍스트 추출 완료! 총 {len(pages)} 페이지의 내용이 '{output_path}'에 저장되었습니다.")

    except Exception as e:
        print(f" 텍스트 추출 중 예상치 못한 오류 발생: {e}")


def process_pdf_files(target_folder, output_base_folder):
    # 1. 주어진 폴더 경로의 유효성 검사
    if not os.path.isdir(target_folder):
        print(f"오류: '{target_folder}'는 유효한 폴더 경로가 아닙니다.")
        return
    # 출력폴더가 없으면 생성
    os.makedirs(output_base_folder, exist_ok=True)
    print(f"--- 폴더 '{target_folder}' 내 PDF 파일 처리 시작 ---")

    processed_count = 0

    # 2. 폴더 내 모든 파일 및 폴더 순회
    file_list = os.listdir(target_folder)
    for filename in file_list:
        # 3. 파일의 전체 경로 생성
        file_path = os.path.join(target_folder, filename)
        # 4. 파일인지 확인하고 확장자가 '.pdf'인지 확인
        # os.path.isfile()로 파일인지 확인
        if os.path.isfile(file_path) and filename.lower().endswith('.pdf'):
            try:
                print(f"처리 중: {filename}")
                # --- ⭐[수정] 올바른 .txt 출력 경로 생성 로직 ---
                base_name = os.path.splitext(filename)[0]
                output_filename = base_name + '.txt'
                output_path = os.path.join(output_base_folder, output_filename)  # output_base_folder 사용
                # ⭐️ txt 파일로 저장 
                pdf_to_text(file_path, output_path)

                # 결과 사용 (예: 출력하거나 저장)
                #
                # print(f"  추출된 텍스트 일부: {text_content[:100]}...")

                processed_count += 1

            except Exception as e:
                print(f"  [오류]: 파일 '{filename}' 처리 중 예외 발생: {e}")

    print(f"--- 총 {processed_count}개의 PDF 파일 처리가 완료되었습니다. ---")
