# base_downloader.py
from abc import ABC, abstractmethod
import json
import os
import time
from typing import Dict, Any, List, Optional, Set, Tuple
import logging
from tqdm import tqdm

import requests
# ⭐️ TARGET 값에 따른 공통 정보 매핑 테이블 정의
SAVE_INTERVAL = 100 # 100건마다 중간 저장
API_CONFIGS = {
    # 1. 일반 판례 (대법원 및 하급심)
    "prec": {
        "list_root": "PrecSearch", 
        "data_root":'prec',
        "detail_root": "PrecService", 
        "filename_prefix": "prec",
        "detail_param": "ID",            
        "serial_key": "판례일련번호"  ,     # 목록에서 상세 ID 추출 시 사용
        "friendly_name": "일반 판례" # ⭐️ 추가
    },
    
    # 2. 헌재 결정례 (헌법재판소)
    "detc": {
        "list_root": "DetcSearch", 
        "data_root":"Detc",
        "detail_root": "DetcService", 
        "filename_prefix": "detc",
        "detail_param": "ID",
        "serial_key": "헌재결정례일련번호",
        "friendly_name": "헌재 결정례" # ⭐️ 추가
    },
    
    # 3. 행정 심판례 (국민권익위원회 등 재결례)
    "decc": {
        "list_root": "Decc", 
        "data_root":"decc",
        "detail_root": "PrecService",  # 행정심판례 상세 응답은 'PrecService' 키를 사용함
        "filename_prefix": "decc",
        "detail_param": "ID",
        "serial_key": "행정심판재결례일련번호",
        "friendly_name": "행정 심판례" # ⭐️ 추가
    },
    
    # 4. 현행 법령 (법령 본문)
    "eflaw": {
        "list_root": "LawSearch", 
        "data_root":"law",
        "detail_root": "법령",           # 법령 상세 응답은 '법령' 키를 사용함
        "filename_prefix": "eflaw",
        "detail_param": "MST",           # 법령 상세 조회 시 '법령일련번호'를 'MST' 파라미터로 사용
        "serial_key": "법령일련번호",
        "friendly_name": "현행 법령" # ⭐️ 추가
    },
    
    # 5. 법령 해석례 (법제처 법령 해석)
    "expc": {
        "list_root": "Expc", 
        "data_root":"expc",
        "detail_root": "ExpcService", 
        "filename_prefix": "expc",
        "detail_param": "ID",
        "serial_key": "법령해석례일련번호",
        "friendly_name": "법령 해석례" # ⭐️ 추가
    }
}
# 공통 기본 URL 설정
DEFAULT_LIST_API_URL = "http://www.law.go.kr/DRF/lawSearch.do"
DEFAULT_DETAIL_API_URL = "http://www.law.go.kr/DRF/lawService.do"
# ----------------------------------------------------------------------
import logging

# 1. 로거 객체 정의 (현재 모듈 이름 사용)
logger = logging.getLogger(__name__)

# 2. 로깅 레벨 설정 (INFO 레벨 이상 메시지 출력)
logger.setLevel(logging.INFO)

# 3. 기본 설정 (핸들러가 없는 경우 콘솔 출력 기본 설정)
# 이 코드는 다른 곳에서 로깅 설정을 하지 않았을 때만 기본 포맷과 핸들러를 추가합니다.
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
class BaseDownloader(ABC):
    
    def __init__(self, 
                 target: str,  
                 output_dir: str, 
                 list_url: str = DEFAULT_LIST_API_URL, 
                 detail_url: str = DEFAULT_DETAIL_API_URL,
                 oc_code: str = "huiyeony888",
                 rows_per_page: int = 100,
                 api_request_delay: float = 0.1):

    
        config = API_CONFIGS[target]
        self.LIST_ROOT_KEY = config["list_root"]
        self.DATA_LIST_KEY = config["data_root"]
        self.DETAIL_ROOT_KEY = config["detail_root"]
        self.SERIAL_KEY_NAME = config["serial_key"]
        self.DETAIL_PARAM_KEY = config["detail_param"]
        self.FRIENDLY_NAME = config["friendly_name"] # ⭐️ 추가된 속성
        
        list_output_filename = f"{config['filename_prefix']}_list.json"
        detail_output_filename = f"{config['filename_prefix']}_details.json"
        
        # ⭐️ 필수 인자 초기화
        self.TARGET = target
        self.LIST_OUTPUT_FILENAME = list_output_filename
        self.DETAIL_OUTPUT_FILENAME = detail_output_filename
        
        # ⭐️ 기본값이 있는 인자 초기화
        self.LIST_API_URL = list_url
        self.DETAIL_API_URL = detail_url
        self.OC_CODE = oc_code
        self.ROWS_PER_PAGE = rows_per_page
        self.API_REQUEST_DELAY = api_request_delay

        # 경로 설정 및 폴더 생성 (스크립트 경로 기준 폴더 생성 로직은 main.py에서 처리하고, 
        # 여기서는 전달받은 output_dir을 그대로 사용합니다.)
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.list_output_path = os.path.join(self.output_dir, self.LIST_OUTPUT_FILENAME)
        self.detail_output_path = os.path.join(self.output_dir, self.DETAIL_OUTPUT_FILENAME)
        
        # 🚨 이 클래스 내부에 _request_api, request_list_and_save, request_detail_and_save 
        # 등의 공통 로직이 구현되어 있어야 합니다.  
    def _request_api(self, url: str, params: Dict[str, Any]) -> Dict[str, Any] | None:
        """ API 요청 처리 및 예외 처리 """
        try:
            response = requests.get(url, params=params, timeout=20) 
            response.raise_for_status() 
            
            # API 응답이 JSON 형식이 아닐 경우 오류 발생 가능
            return response.json()
        except requests.exceptions.HTTPError as e:
            # 4xx, 5xx 오류 처리 (예: 429 토큰 초과)
            logger.error(f"❌ HTTP 오류 {e.response.status_code} 발생: {e}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 요청 오류 발생: {e}")
            return None
        except json.JSONDecodeError:
            logger.error(f"❌ JSON 디코딩 오류: 응답이 JSON 형식이 아닙니다.")
            return None
        except Exception as e:
            logger.error(f"❌ 알 수 없는 오류 발생: {e}")
            return None

    @abstractmethod
    def request_list_and_save(self) -> str | None:
        # ⭐️ 공통 목록 조회/Pagination 로직
        """
        판례 목록 API를 totalCnt를 기반으로 반복 호출하고 결과를 JSON 파일에 통합 저장합니다.
        """
        all_items: List[Dict[str, Any]] = []
        page_no = 1
        total_pages = 1
        
        logger.info(f"\n--- 1단계: {self.FRIENDLY_NAME} 전체 목록 조회 시작 ---")
        
        while page_no <= total_pages:
            params = {
                "target": self.TARGET, "OC": self.OC_CODE, "type": "JSON", 
                "display": str(self.ROWS_PER_PAGE), "page": str(page_no),
           
                
            }
            target_info = API_CONFIGS[self.TARGET] 

            # ⭐️ 원하는 값을 키(Key)로 명시하여 추출합니다.
            list_root_key = target_info["list_root"] # (예)PrecSearch)
            detail_root_key = target_info["detail_root"] # 예)PrecService
            serial_key_name = target_info["serial_key"] # 훨씬 직관적입니다.(예) 판례일련번호)
            data_list_key = target_info["data_root"] # prec,Detc 
  
            data = self._request_api(self.LIST_API_URL, params)
            
            # ⭐️ 응답 구조 확인: 최상위 키가 'Prec'이고 목록이 'prec' 리스트에 담겨있다고 가정
            if not data or list_root_key not in data:
                logger.error(f"❌ 목록 조회 실패 (페이지 {page_no}). 파이프라인 중단.")
                break
            
            prec_data = data[list_root_key]
            item_list = prec_data.get(data_list_key, [])
            
            if page_no == 1:
                try:
                    total_count = int(prec_data.get('totalCnt', 0))
                except ValueError:
                    total_count = 0
                
                if total_count == 0:
                    logger.info(f"❌ 조회된 {self.FRIENDLY_NAME} 가 없습니다.")
                    return None
                    
                total_pages = (total_count + self.ROWS_PER_PAGE - 1) // self.ROWS_PER_PAGE
                logger.info(f"총 {total_count}건, {total_pages} 페이지를 발견했습니다.")

            if isinstance(item_list, list) and item_list:
                all_items.extend(item_list)
                logger.info(f"페이지 {page_no}/{total_pages} 로드 완료. 현재까지 {len(all_items)}건 수집.")
            elif page_no > 1 and not item_list:
                logger.info(f"페이지 {page_no}에서 항목이 없어 조기 종료합니다.")
                break

            page_no += 1
            time.sleep(self.API_REQUEST_DELAY) # 딜레이 적용
            
        if not all_items:
            return None
            
        # 3. JSON 파일로 저장
        try:
            with open(self.list_output_path, 'w', encoding='utf-8') as f:
                json.dump(all_items, f, indent=4, ensure_ascii=False)
            logger.info(f"🎉 전체 {self.FRIENDLY_NAME} 목록 데이터 ({len(all_items)}건) 저장 성공! 파일명: {self.list_output_path}")
            return self.list_output_path
        except Exception as e:
            logger.error(f"❌ 최종 파일 저장 중 오류 발생: {e}")
            return None
        pass
    @abstractmethod
    def request_detail_and_save(self, list_file_path: str) -> str | None:
        # ⭐️ 공통 상세 조회 및 중간 저장 로직
        """
        목록 파일에서 일련번호를 추출하여 상세 API를 호출하고 통합 저장합니다.
        (다운로드 재개 기능 포함)
        """
        try:
            with open(list_file_path, 'r', encoding='utf-8') as f:
                index_list: List[Dict[str, Any]] = json.load(f)
        except Exception as e:
            logger.error(f"❌ {self.FRIENDLY_NAME} 목록 파일 로드 실패: {list_file_path} - {e}")
            return None

        # 1. 기존 데이터 로드 및 기존 ID 확인
        existing_precedents, existing_serial_ids = self._load_existing_data()
        # ⭐️ 로깅 메시지 완성: 로드된 기존 데이터 개수 및 다음 단계 보고
        logger.info(
            f"📥 기존 데이터 로드 완료. 총 {len(existing_precedents)}건의 상세 정보 확인됨."
        )
        

        config = API_CONFIGS[self.TARGET] 

        # ⭐️ 원하는 값을 키(Key)로 명시하여 추출합니다.
        list_root_key = config["list_root"] # (예)PrecSearch)
        detail_root_key = config["detail_root"] # 예)PrecService
        serial_key_name = config["serial_key"] # 훨씬 직관적입니다.(예) 판례일련번호, 행정심판재결례일련번호)
        detail_param_key = config['detail_param']
        # 2. 미처리 항목만 필터링
        pending_items = [
            item for item in index_list 
            if item.get(serial_key_name) and str(item.get(serial_key_name)) not in existing_serial_ids 
        ]
        
        total_count = len(index_list)
        pending_count = len(pending_items)

        if pending_count == 0:
            logger.info("🎉 모든 상세 정보가 이미 기존 파일에 존재합니다. 작업을 종료합니다.")
            return self.detail_output_path
            
        logger.info(f"\n--- 2단계: 상세 정보 ({total_count}건 중 {pending_count}건 미처리) 조회 시작 ---")

        for item in tqdm(pending_items, desc="Requesting Remaining Details"):
            # ⭐️ '판례일련번호'를 ID로 사용
            prec_id = item.get(serial_key_name)
            
            if not prec_id:
                continue

            params = {
                "target": self.TARGET,
                "OC": self.OC_CODE,
                "type": "JSON",
                detail_param_key : prec_id
            }

            detail_data = self._request_api(self.DETAIL_API_URL, params)

            # ⭐️ 응답 구조: {'PrecService': {...}}
            if detail_data and detail_root_key in detail_data:
                # { '법령': ~~ }
                detail_item = detail_data[detail_root_key] 
                # 🔸 현행 법령 을 위한 예외 코드 
                if self.TARGET == 'eflaw':
                    filtered_item = {}
                    if '기본정보' in detail_item:
                        filtered_item['기본정보'] = detail_item['기본정보']
                    if '조문' in detail_item:
                        filtered_item['조문'] = detail_item['조문']
                        
                    detail_item = filtered_item # 필터링된 딕셔너리로 교체
                    
                if detail_item and isinstance(detail_item, dict):
                    # 새로운 데이터를 기존 데이터에 추가
                    existing_precedents.append(detail_item)
                    logger.info(f"현재까지 {len(existing_precedents)}개 데이터가 추가되었습니다.")
                # ------------------------------------------------------------------
                # ⭐️⭐️⭐️ 수정된 중간 저장 로직 (처리된 문서 개수 기준) ⭐️⭐️⭐️
                # ------------------------------------------------------------------
                else: # ⭐️ 상세 데이터가 유효하지 않을 때의 로깅 추가
                    log_msg = f"❌ {self.FRIENDLY_NAME} ID {prec_id}: 상세 데이터 구조 오류 또는 누락."
                    if detail_item is None:
                        log_msg += " (추출된 데이터가 None)"
                    elif isinstance(detail_item, dict) and not detail_item:
                        log_msg += " (추출된 딕셔너리가 비어 있음)"
                    elif not isinstance(detail_item, dict):
                        log_msg += f" (추출된 데이터 타입: {type(detail_item).__name__})"
                        
                    logger.error(log_msg)
                # existing_precedents의 길이가 SAVE_INTERVAL의 배수가 되었을 때 저장합니다.
                if len(existing_precedents) % SAVE_INTERVAL == 0:
                    logger.info(f"   [Checkpoint] {len(existing_precedents)}건 저장 중... (파일 덮어쓰기)")
                    try:
                        with open(self.detail_output_path, 'w', encoding='utf-8') as f:
                            json.dump(existing_precedents, f, indent=4, ensure_ascii=False)
                    except Exception as e:
                        logger.error(f"❌ {self.FRIENDLY_NAME} ID {prec_id}: 중간 파일 저장 중 오류 발생 - {e}")
                        # 파일 저장 실패는 치명적이므로, 여기서 오류 발생 시 다운로드를 중단하는 것이 안전합니다.
                        break # 루프를 빠져나갑니다.
                        
            time.sleep(self.API_REQUEST_DELAY) # 딜레이 적용
        # 3. 마지막으로 남은 데이터 최종 저장 (100개 단위에 도달하지 않은 나머지 데이터)
        # 현재 총 데이터 개수(len(existing_precedents))가 SAVE_INTERVAL(100)의 배수가 아닐 경우
        try:
            with open(self.detail_output_path, 'w', encoding='utf-8') as f:
                json.dump(existing_precedents, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"❌ {self.FRIENDLY_NAME} ID {prec_id}: 중간 파일 저장 중 오류 발생 - {e}")
            # 파일 저장 실패는 치명적이므로, 여기서 오류 발생 시 다운로드를 중단하는 것이 안전합니다.
             # 루프를 빠져나갑니다.
        logger.info(f"\n✅ 모든 {self.FRIENDLY_NAME} 상세 데이터({len(existing_precedents)}건)를 {self.detail_output_path}에 저장했습니다.")
        return self.detail_output_path
    
    def _load_existing_data(self) -> Tuple[List[Dict[str, Any]], Set[str]]:
        
        existing_precedents: List[Dict[str, Any]] = []
        existing_serial_ids: Set[str] = set()
        
        if os.path.exists(self.detail_output_path):
            try:
                with open(self.detail_output_path, 'r', encoding='utf-8') as f:
                    existing_precedents = json.load(f)
                    existing_serial_ids = {
                        str(item.get(self.SERIAL_KEY_NAME)) 
                        for item in existing_precedents if item.get(self.SERIAL_KEY_NAME) is not None
                    }
                logger.info(f"💾 기존 파일에서 {len(existing_precedents)}건의 {self.FRIENDLY_NAME} 를 로드했습니다. 재개합니다.")
            except Exception as e:
                logger.error(f"❌ 기존 파일 로드 중 오류 발생 ({self.detail_output_path}). 새롭게 시작합니다. 오류: {e}")
                existing_precedents = []
        
        return existing_precedents, existing_serial_ids
