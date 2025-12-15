from typing import Any, override
from langchain_text_splitters import MarkdownTextSplitter, RecursiveCharacterTextSplitter
from pipeline.modules.base.base_loader import logger
from pipeline.modules.base.base_loader import BaseLoader


# ----------------------------------------------------------------------
# PrecedentLoader 클래스
# ----------------------------------------------------------------------

class ConstitutionalDecisionLoader(BaseLoader):

    def __init__(self, db_local_port: int, ollama_local_port: int):

        # 청킹 스플리터 초기화
        markdown_splitter = MarkdownTextSplitter(chunk_size=10000, chunk_overlap=0)
        recursive_splitter = RecursiveCharacterTextSplitter(
            separators=["\n\n", "\n", " ", ""], chunk_size=1000, chunk_overlap=100
        )

        # ✅ BaseLoader.__init__ 호출 및 'detc' 타입 전달
        super().__init__('detc',
                         markdown_splitter=markdown_splitter,
                         recursive_splitter=recursive_splitter)

    @override
    def _prepare_document(self, detc_data: dict[str, Any]) -> dict[str, Any] | None:
        """ 
        단일 헌재결정례 데이터를 documents 테이블 삽입을 위한 dict 형식으로 변환하고 텍스트를 준비합니다.
        """
        super()._prepare_document(detc_data)
        # 1. 헌재결정례 고유 필드 추출 및 메타데이터 준비

        # '헌재결정례일련번호'를 판례일련번호로 사용
        detc_serial_id = detc_data.get("헌재결정례일련번호")
        case_number = detc_data.get("사건번호", '미상')
        case_name = detc_data.get("사건명", '제목없음')

        if not detc_serial_id or not case_number:
            logger.warning(f"필수 필드(ID 또는 사건번호) 누락: ID={detc_serial_id}, 사건번호={case_number}")
            return None

        # chunks 테이블의 meta 필드로 들어갈 정보
        metadata = {
            "헌재결정례일련번호": detc_serial_id,
            "사건번호": case_number,
            "사건명": case_name,
            "종국일자": detc_data.get("종국일자"),
            "재판부구분코드": detc_data.get("재판부구분코드"),
            "심판대상조문": detc_data.get("심판대상조문"),
            "참조판례": detc_data.get("참조판례"),
            "참조조문": detc_data.get("참조조문"),
        }

        # 2. 콘텐츠 조합 및 마크다운 헤더 적용

        content_fields = {
            "판시사항": detc_data.get("판시사항"),
            "결정요지": detc_data.get("결정요지"),
            "전문": detc_data.get("전문")  # 헌재결정례의 상세 내용
        }

        combined_text = ""
        for field, content in content_fields.items():
            if content:
                # ⭐️ 기존 _add_markdown_headers_simplified 함수 재활용
                # 이 함수는 【...】 및 1., 가. 등의 구분자를 ##로 변환함
                processed_content = self._add_markdown_headers_simplified(content, field)

                # 콘텐츠 시작 시 큰 헤더로 필드명을 명시 (예: # 판시사항)
                combined_text += f"# {field}\n\n{processed_content.strip()}\n\n"

        if not combined_text: return None

        # 3. documents 테이블 필드 설정
        MAX_VARCHAR_LENGTH = 255

        # file_name 및 file_path는 고유 ID를 포함하여 생성
        file_name = case_name[:MAX_VARCHAR_LENGTH]
        # file_path는 ON CONFLICT의 기준이 되므로 고유해야 함
        file_path = f"detc_{detc_serial_id}_{case_number}"[:MAX_VARCHAR_LENGTH]

        return {
            "page_content": combined_text.strip(),
            "metadata": metadata,
            "precedent_serial_id": detc_serial_id,  # 기존 필드명 유지
            "file_name": file_name,
            "file_path": file_path,
            "uploaded_by_user_id": 1,
            "document_scope": "precedent",  # 스코프 변경
            "status": "ready",
        }
