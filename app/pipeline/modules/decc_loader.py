# administrative_appeal_loader.py

from typing import Any, override
from langchain_text_splitters import MarkdownTextSplitter, RecursiveCharacterTextSplitter
from pipeline.modules.base.base_loader import BaseLoader, logger


class AdministrativeAppealLoader(BaseLoader):
    # ⭐️ PrecedentLoader의 __init__ 및 DB/Embedding 초기화 로직을 그대로 사용

    def __init__(self, db_local_port: int, ollama_local_port: int):

        # 청킹 스플리터 초기화
        markdown_splitter = MarkdownTextSplitter(chunk_size=10000, chunk_overlap=0)
        recursive_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", " ", ""], chunk_size=1000, chunk_overlap=100
        )

        # ✅ BaseLoader.__init__ 호출 및 'decc' 타입 전달
        super().__init__('decc',
                         markdown_splitter=markdown_splitter,
                         recursive_splitter=recursive_splitter)

    @override
    def _prepare_document(self, decc_data: dict[str, Any]) -> dict[str, Any] | None:

        # '행정심판례일련번호'를 판례일련번호로 사용
        appeal_serial_id = decc_data.get("행정심판례일련번호")
        case_number = decc_data.get("사건번호", '미상')
        case_name = decc_data.get("사건명", '제목없음')

        if not appeal_serial_id or appeal_serial_id == "0":
            logger.warning(f"필수 필드(일련번호) 누락 또는 0: ID={appeal_serial_id}, 사건명={case_name}")
            return None

        # chunks 테이블의 meta 필드로 들어갈 정보
        metadata = {
            "행정심판례일련번호": appeal_serial_id,
            "사건번호": case_number,
            "사건명": case_name,
            "의결일자": decc_data.get("의결일자"),
            "재결청": decc_data.get("재결청"),
            "처분청": decc_data.get("처분청"),
            "재결례유형코드": decc_data.get("재결례유형코드"),
            "재결례유형명": decc_data.get("재결례유형명"),
        }

        # 2. 콘텐츠 조합 및 마크다운 헤더 적용

        content_fields = {
            "주문": decc_data.get("주문"),
            "청구취지": decc_data.get("청구취지"),
            "재결요지": decc_data.get("재결요지"),
            "이유": decc_data.get("이유")
        }

        combined_text = ""
        for field, content in content_fields.items():
            if content:
                # ⭐️ 기존 _add_markdown_headers_simplified 함수 재활용
                processed_content = self._add_markdown_headers_simplified(content, field)

                # 콘텐츠 시작 시 큰 헤더로 필드명을 명시 (예: # 주문)
                combined_text += f"# {field}\n\n{processed_content.strip()}\n\n"

        if not combined_text:
            logger.warning(f"콘텐츠 필드가 비어있어 문서 생성을 건너뜁니다: ID={appeal_serial_id}")
            return None

        # 3. documents 테이블 필드 설정
        MAX_VARCHAR_LENGTH = 255

        file_name = case_name[:MAX_VARCHAR_LENGTH]
        # file_path는 ON CONFLICT의 기준이 되므로 고유해야 함 (일련번호 기반)
        file_path = f"decc_{appeal_serial_id}_{case_number}"[:MAX_VARCHAR_LENGTH]

        return {
            "page_content": combined_text.strip(),
            "metadata": metadata,
            "precedent_serial_id": appeal_serial_id,
            "file_name": file_name,
            "file_path": file_path,
            "uploaded_by_user_id": 1,
            "document_scope": "precedent",  # 스코프 변경
            "status": "ready",
        }

    @override
    def run_etl_pipeline(self, decc_data: list[dict[str, Any]]):
        return super().run_etl_pipeline(decc_data)
