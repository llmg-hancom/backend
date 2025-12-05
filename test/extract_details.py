import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

import requests
from tqdm import tqdm

# --- 설정 및 상수 ---
BASE_DETAIL_API_URL = "https://apis.data.go.kr/9750000/PrecedentInfomationService/getKorPrcdntDetail"
BASE_LIST_API_URL = "https://apis.data.go.kr/9750000/PrecedentInfomationService/getKorPrcdntList"
# NOTE: 서비스 키는 보안상 노출을 최소화해야 하지만, 여기서는 예시로 사용합니다.
SERVICE_KEY = "582ed3ff5c909c242fb9dd6e87d9572ef9996a24680ea3dadf6fa8619f91db03"
API_REQUEST_DELAY = 0.2
OUTPUT_LIST_FILE = 'hunje_precident_list.json'
OUTPUT_DETAIL_FILE = 'all_precedents(details).json'

# --- 로깅 설정 ---
logger = logging.getLogger(__name__)
# 핸들러가 설정되어 있지 않다면 기본 스트림 핸들러를 추가합니다.
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# ----------------------------------------------------------------------
# HunjeDownloader 클래스
# ----------------------------------------------------------------------
class HunjeDownloader:    
    
    def __init__(self, output_dir: str = "./API_Data"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        # 클래스 내에서 사용할 파일 경로 미리 정의
        self.list_path = os.path.join(self.output_dir, OUTPUT_LIST_FILE)
        self.detail_path = os.path.join(self.output_dir, OUTPUT_DETAIL_FILE)
        
    def request_list_and_save(self)-> str:
        """
        헌법재판소 API를 호출하여 판례 목록을 가져와 JSON 파일로 저장합니다.
        """
        logger.info("--- ⭐️ 헌법재판소 판례 목록 조회 API 호출 시작 ---")
        
        # 요청 파라미터
        params = {
            "serviceKey": SERVICE_KEY, 
            "numOfRows": '1000',
            "type":'json',
            'page': 1  # 1페이지부터 시작
        }
        
        try:
            # 1. API 요청 (verify=False는 SSL 문제 시에만 사용 권장)
            response = requests.get(BASE_LIST_API_URL, params=params, timeout=10)
            response.raise_for_status() # HTTP 오류가 발생하면 예외 발생

            # 2. JSON 데이터 변환 및 item 추출
            data = response.json()
            items = data.get('body', {}).get('items', {}).get('item', [])
            
            if isinstance(items, list):
                logger.info(f"총 {len(items)}건의 판례 목록을 수집했습니다.")
            
            # 3. JSON 파일로 저장
            with open(self.list_path, 'w', encoding='utf-8') as f:
                json.dump(items, f, indent=4, ensure_ascii=False)
                
            logger.info(f"🎉 데이터 저장 성공! 파일명: {self.list_path}")
            
            return self.list_path

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 요청 오류 발생: {e}")
        except json.JSONDecodeError:
            logger.error("❌ JSON 디코딩 오류: 응답이 JSON 형식이 아닙니다 (인증키 오류 가능성).")
        except Exception as e:
            logger.error(f"❌ 알 수 없는 오류 발생: {e}")
        
        return "" # 오류 발생 시 빈 문자열 반환

    def request_detail(self, index_list: List[Dict[str, Any]]) -> str:
        """
        일련번호 리스트에서 eventNum을 추출하여 API 호출 후 변환된 데이터를 JSON 파일로 저장합니다.
        """
        precedent_ids = [item.get("eventNum") for item in index_list if item.get("eventNum")]
        logger.info(f"총 {len(precedent_ids)}개의 판례일련번호를 추출했습니다. 상세 데이터 다운로드 시작.")
        all_transformed_data: List[Dict[str, Any]] = []
        
        for event_num in tqdm(precedent_ids, desc="Downloading Precedents from API"):
            params = {
                'serviceKey': SERVICE_KEY,
                'type': 'json', 
                'eventNum': event_num, 
                'panreType': '01'
                }
            try:
                # ⭐️ 일련번호로 상세 조회 ⭐️
                response = requests.get(BASE_DETAIL_API_URL, params=params, timeout=10)
                response.raise_for_status() 
                api_data = response.json()
                
                item_list = api_data.get('body', {}).get('items', {}).get('item')
                
                if item_list and isinstance(item_list, list) and item_list[0]:
                    transformed_item = self.transform_response(item_list[0])
                    all_transformed_data.append(transformed_item)
                else:
                    logger.warning(f"판례일련번호 {event_num}: API 응답에서 'item' 데이터를 찾을 수 없습니다.")
                
            except requests.RequestException as e:
                logger.error(f"판례일련번호 {event_num}: API 요청 실패 - {e}")
            except Exception as e:
                logger.error(f"판례일련번호 {event_num}: 데이터 처리 중 오류 발생 - {e}")
            
            time.sleep(API_REQUEST_DELAY) 
            
        # 출력 파일 경로를 클래스 변수로 사용
        with open(self.detail_path, 'w', encoding='utf-8') as f:
            json.dump(all_transformed_data, f, ensure_ascii=False, indent=4)
        
        logger.info(f"✅ 총 {len(all_transformed_data)}개의 판례 데이터를 {self.detail_path}에 저장했습니다.")
        return self.detail_path
    
    def clean_precedent_text(self, text: Optional[str]) -> str:
        """
        텍스트에서 <br/> 태그를 제거하고, 연속된 공백(줄바꿈 포함)을 단일 공백으로 정리합니다.
        """
        if not text:
            return ""
        
        # 1. <br/> 태그 제거 (대소문자 무시)
        text = re.sub(r'<br\s*\/?>', ' ', text, flags=re.IGNORECASE)
        
        # 2. 연속된 공백 문자(줄바꿈, 탭, 여러 칸의 띄어쓰기)를 단일 띄어쓰기로 치환
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def transform_response(self, api_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        API 응답의 'item' 객체를 DB 적재를 위한 스키마로 변환합니다.
        """
        # 판례 내용을 조합
        content_parts = [
            api_item.get("event"), api_item.get("textOfDecision"), 
            api_item.get("reason"), api_item.get("judgement"), 
            api_item.get("pansiMatt"), api_item.get("decisionGst"), 
            api_item.get("adjobtTxt"),
        ]
        
        combined_content = "\n\n".join(filter(None, [part.strip() for part in content_parts if part]))
        combined_content = self.clean_precedent_text(combined_content)
        
        # 최종 스키마에 맞게 변환
        transformed_data = {
            "판례일련번호": api_item.get("eventNum"),
            "사건번호": api_item.get("eventNo"),
            "사건명": api_item.get("eventNm"),
            "판례유형": api_item.get("panreType"),
            "재판부": api_item.get("jgdmtCort"),
            "선고일자": api_item.get("rstaDate"),
            "판시사항": api_item.get("pansiMatt", "") or api_item.get("panreTitle", ""), 
            "판결요지": api_item.get("decisionGst", "") or api_item.get("eventSummary", ""), 
            "판례내용": combined_content
        }
        
        return transformed_data
        
    # ----------------------------------------------------------------------
    # 스크립트 실행 진입점 (가장 단순화된 파이프라인)
    # ----------------------------------------------------------------------


    def run_download_pipeline(self, list_file_path):

        # # --- 1. 판례 목록 다운로드 ---
        # list_file_path = downloader.request_list_and_save()

        # if not list_file_path:
        #     logger.error("❌ 목록 파일 다운로드에 실패하여 작업을 중단합니다.")
        #     exit(1)
        
        data_list: List[Dict[str, Any]] = []
        
        # --- 2. 다운로드된 목록 파일 로드 ---
        try:
            logger.info(f"'{list_file_path}' 파일에서 판례 인덱스 로드 시작...")
            with open(list_file_path, 'r', encoding='utf-8') as f:
                data_list = json.load(f)
            logger.info(f"☑️ 총 {len(data_list)}개의 판례 인덱스 로드 완료.")
            
        except FileNotFoundError:
            logger.error(f"❌ 파일을 찾을 수 없습니다: '{list_file_path}'")
            exit(1)
        except json.JSONDecodeError:
            logger.error(f"❌ JSON 파일 디코딩 오류: '{list_file_path}' 파일 내용 확인 필요.")
            exit(1)
        
        # --- 3. 상세 데이터 요청 및 저장 ---
        if not data_list:
            logger.warning("⚠️ 로드된 판례 인덱스가 없습니다. 상세 데이터 다운로드를 건너뜁니다.")
        else:
            try:
                result_path = self.request_detail(data_list)
                logger.info(f"🚀 전체 작업 완료: 상세 데이터가 '{result_path}'에 성공적으로 저장되었습니다.")
                
            except Exception as e:
                logger.error(f"❌ 상세 데이터 다운로드 중 오류 발생: {e}")
if __name__ == "__main__":
    loader = HunjeDownloader()
    loader.run_download_pipeline('all_precedents.json')