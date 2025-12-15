# administrative_appeal_downloader.py

from typing import Dict, Any
from modules.base.base_downloader import BaseDownloader


# ----------------------------------------------------------------------
# 행정심판례 다운로드 클래스
# ----------------------------------------------------------------------

class AdministrativeAppealDownloader(BaseDownloader):

    def __init__(self, output_dir :str):
        super().__init__(target='decc',
                         output_dir=output_dir,
                         )

    def _request_api(self, url: str, params: Dict[str, Any]) -> Dict[str, Any] | None:
        return super()._request_api(url,params)

    def request_list_and_save(self) -> str | None:
       return super().request_list_and_save()         
   
    def request_detail_and_save(self, list_file_path: str) -> str | None:
       return super().request_detail_and_save(list_file_path)

