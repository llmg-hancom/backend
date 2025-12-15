from typing import List, Dict, Any, override
from langchain_text_splitters import MarkdownTextSplitter, RecursiveCharacterTextSplitter

from pipeline.modules.base.base_loader import BaseLoader


class PrecedentLoader(BaseLoader):

    def __init__(self):
        # 청킹 스플리터 초기화
        markdown_splitter = MarkdownTextSplitter(chunk_size=10000, chunk_overlap=0)
        recursive_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", " ", ""], chunk_size=1000, chunk_overlap=100
        )
        # ✅ BaseLoader.__init__ 호출 및 'prec' 타입 전달
        super().__init__(loader_type="prec",
                         markdown_splitter=markdown_splitter,
                         recursive_splitter=recursive_splitter
                         )

    @override
    def _prepare_document(self, precedent: Dict[str, Any]) -> Dict[str, Any] | None:
        """ 단일 판례 데이터를 documents 테이블 삽입을 위한 Dict 형식으로 변환하고 텍스트를 준비합니다. """
        # ... (기존 _prepare_document 로직 유지) ...
        metadata = {k: v for k, v in precedent.items() if k not in ["판시사항", "판결요지", "판례내용"]}

        combined_text = ""
        for field in ["판시사항", "판결요지", "판례내용"]:
            if precedent.get(field):
                # ⭐️ BaseLoader의 _add_markdown_headers_simplified 호출
                combined_text += self._add_markdown_headers_simplified(precedent[field], field) + "\n\n"
        # ... (나머지 로직 유지) ...
        MAX_VARCHAR_LENGTH = 255
        raw_file_name = precedent.get('사건번호', '미상') or precedent.get('사건명', '미상')
        file_name = raw_file_name[:MAX_VARCHAR_LENGTH]
        prec_serial_num = precedent.get('판례정보일련번호', "정보없음")
        prec_num = precedent.get('사건번호', "정보없음")  # 이 변수는 그대로 유지해도 무방합니다.

        # --- 파일 경로 구성 변경 ---
        # 1. 고유 ID와 판례일련번호를 사용하여 파일 경로를 구성합니다.
        # 2. MAX_VARCHAR_LENGTH로 자를 필요가 거의 없지만, 혹시 모를 상황을 대비해 그대로 둡니다.

        raw_file_path = f"prec_{prec_serial_num}_{prec_num}"
        file_path = raw_file_path[:MAX_VARCHAR_LENGTH]  # 길이가 짧아질 것이므로 truncation 위험 감소

        return {
            "page_content": combined_text.strip(),
            "metadata": metadata,
            "file_name": file_name,
            "file_path": file_path,
            "uploaded_by_user_id": 1,
            "document_scope": "precedent",
            "status": "ready",
        }

    @override
    def run_etl_pipeline(self, precedent_data: List[Dict[str, Any]]):
        # ✅ BaseLoader의 run_etl_pipeline을 그대로 재사용
        return super().run_etl_pipeline(precedent_data)
