import json
import os
import time
import requests
from typing import List, Dict, Any
from tqdm import tqdm

from pipeline.modules.base.base_downloader import BaseDownloader

# --- 설정 상수 ---
# 제공해주신 API 접근 코드(OC)를 사용합니다.
OC_CODE = "huiyeony888"
TARGET = "expc"  # 법령해석례 타겟
LIST_API_URL = "http://www.law.go.kr/DRF/lawSearch.do"
DETAIL_API_URL = "http://www.law.go.kr/DRF/lawService.do"

LIST_OUTPUT_FILENAME = "expc_list.json"
DETAIL_OUTPUT_FILENAME = "expc_details.json"
OUTPUT_DIR = "./EXPC_Data"


# ----------------------------------------------------------------------
# 법령해석례 다운로드 클래스
# ----------------------------------------------------------------------

class StatuteInterpretationDownloader(BaseDownloader):

    def __init__(self, output_dir: str):
        super().__init__(target='expc',
                         output_dir=output_dir)

    def _request_api(self, url: str, params: Dict[str, Any]) -> Dict[str, Any] | None:
        return super()._request_api(url, params)

    def request_list_and_save(self) -> str | None:
        return super().request_list_and_save()

    def request_detail_and_save(self, list_file_path: str) -> str | None:
        return super().request_detail_and_save(list_file_path)
