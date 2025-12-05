import requests
import json
import logging
from tqdm import tqdm
from typing import List, Dict, Any

# --- 설정 변수 ---
# 로깅 설정
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# API 정보
BASE_URL = "https://apis.data.go.kr/9750000/PrecedentInfomationService/getKorPrcdntList"
SERVICE_KEY = "582ed3ff5c909c242fb9dd6e87d9572ef9996a24680ea3dadf6fa8619f91db03"
OUTPUT_FILENAME = "all_precedents.json"

# 요청 범위
START_PAGE = 1
END_PAGE = 74 # 1부터 74까지 요청
NUM_OF_ROWS = 1000

# ----------------------------------------------------------------------
# 메인 함수
# ----------------------------------------------------------------------

def download_all_pages_to_single_file():
    """
    API를 페이지별로 호출하여 모든 결과를 하나의 리스트로 합친 후 JSON 파일로 저장합니다.
    """
    all_precedents: List[Dict[str, Any]] = []
    
    # 74페이지까지 반복
    for page_no in tqdm(range(START_PAGE, END_PAGE + 1), desc="Downloading Precedent List Pages"):
        
        params = {
            'serviceKey': SERVICE_KEY, 
            'pageNo': page_no, 
            'numOfRows': NUM_OF_ROWS, 
            'type': 'json'
        }
        
        try:
            # API 요청
            response = requests.get(BASE_URL, params=params, timeout=20)
            response.raise_for_status() # HTTP 오류가 발생하면 예외 발생

            data = response.json()
            
            # API 응답 구조에 맞게 항목(item) 추출
            # 응답 구조: response -> body -> items -> item
            items = data.get('body', {}).get('items', {}).get('item')
            
            if items is None:
                logger.warning(f"페이지 {page_no}: 'item' 필드를 찾을 수 없거나 데이터가 없습니다.")
                continue
                
            # 단일 항목인 경우 리스트로 변환 (API마다 응답 방식이 다를 수 있음)
            if isinstance(items, dict):
                items = [items]
            elif not isinstance(items, list):
                logger.warning(f"페이지 {page_no}: 예상치 못한 데이터 형식 ({type(items)})을 건너뜁니다.")
                continue

            # 수집된 데이터를 전체 리스트에 추가
            all_precedents.extend(items)
            logger.info(f"페이지 {page_no} 완료. 현재까지 {len(all_precedents)}건 수집.")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"페이지 {page_no} 요청 오류 발생: {e}")
        except json.JSONDecodeError:
            logger.error(f"페이지 {page_no} JSON 디코딩 오류. 응답 내용 확인 필요.")
        except Exception as e:
            logger.error(f"페이지 {page_no} 처리 중 알 수 없는 오류 발생: {e}")

    # 모든 요청이 완료된 후, 결과를 단일 파일로 저장
    if all_precedents:
        try:
            with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
                json.dump(all_precedents, f, indent=4, ensure_ascii=False)
            
            logger.info(f"\n🎉 모든 페이지 다운로드 완료. 총 {len(all_precedents)}건의 데이터를 '{OUTPUT_FILENAME}'에 저장했습니다.")
        except Exception as e:
            logger.error(f"최종 파일 저장 중 오류 발생: {e}")
    else:
        logger.warning("\n❌ 수집된 데이터가 없어 파일 저장을 건너뜁니다.")

if __name__ == "__main__":
    download_all_pages_to_single_file()