from typing import Dict, Any, override

import logging

from pipeline.modules.base.base_downloader import BaseDownloader

# 로깅 설정
logger = logging.getLogger(__name__)
# 핸들러가 설정되어 있지 않다면 기본 스트림 핸들러를 추가합니다.
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# ----------------------------------------------------------------------
# 판례 다운로드 클래스
# ----------------------------------------------------------------------

class PrecedentDownloader(BaseDownloader):

    def __init__(self, output_dir):
        super().__init__(target='prec',
                         output_dir=output_dir
                         )

    def _request_api(self, url: str, params: Dict[str, Any]) -> Dict[str, Any] | None:
        return super()._request_api(url, params)

    @override
    def request_list_and_save(self) -> str | None:
        return super().request_list_and_save()

    @override
    def request_detail_and_save(self, list_file_path: str) -> str | None:
        return super().request_detail_and_save(list_file_path)

    # # ----------------------------------------------------------------------
    # # 헬퍼: 재개 기능을 위해 기존 데이터를 로드하는 함수 (요청하신 재개 로직 활용)
    # # ----------------------------------------------------------------------
