import os
from typing import Any, Dict, override

from .base.base_downloader import BaseDownloader

# ----------------------------------------------------------------------
# 현행법령 다운로드 클래스
# ----------------------------------------------------------------------

class LawDownloader(BaseDownloader):

    def __init__(self, output_dir: str):
        # 스크립트 파일의 절대 경로를 기준으로 폴더 생성 (src/Law_Data)
        super().__init__(
            target='eflaw',
            output_dir=output_dir
            )
    @override
    def _request_api(self, url: str, params: Dict[str, Any]) -> Dict[str, Any] | None:
        return super()._request_api(url,params)
    
    @override
    def request_list_and_save(self) -> str | None:
        return super().request_list_and_save()
    
    @override
    def request_detail_and_save(self, list_file_path: str) -> str | None:
        return super().request_detail_and_save(list_file_path)


