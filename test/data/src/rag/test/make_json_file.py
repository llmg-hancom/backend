import json
import os
from pathlib import Path
from typing import List, Dict, Any

# --- 설정 변수 ---
INPUT_FOLDER = 'testfiles'  # JSON 파일이 저장된 폴더 경로
OUTPUT_FILE = 'testset.json' # 최종 병합 파일명
# ------------------

def make_json_file(input_dir: str, output_file: str):
    """
    지정된 폴더 내의 모든 JSON 파일을 읽어 컬럼명을 변경하고 하나의 JSON 파일로 병합합니다.
    """
    
    input_path = Path(input_dir)
    merged_data: List[Dict[str, Any]] = []
    processed_count = 0
    prior_data_count = 0
    if not input_path.is_dir():
        print(f"❌ 오류: 입력 경로 '{input_dir}'가 존재하지 않거나 폴더가 아닙니다.")
        return

    print(f"🔍 폴더 '{input_dir}'에서 JSON 파일 검색 시작...")

    # 폴더 내의 모든 JSON 파일을 순회
    for file_path in input_path.glob('*.json'):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                item = json.load(f)

            # --- 핵심: 컬럼 이름 변경 ---
            
            # 1. answer -> ground_truths
            if 'answer' in item:
                item['ground_truths'] = [item.pop('answer')] # RAGAS 요구 형식: 리스트
            
            # 2. commentary -> ground_truth_contexts
            if 'reference_rules' in item:
                # 텍스트를 문맥 리스트로 처리 (문맥 청크 리스트 형태)
                # 단일 문맥이므로 리스트에 담아 처리
                item['ground_truth_contexts'] = [item.pop('reference_rules')]
            # llm 입력을 넣을 곳 
            item['contexts'] = []
            # 응답 데이터 
            # RAGAS 호환성을 위해 불필요하거나 중복되는 필드는 제거하지 않고 유지합니다.
            
            merged_data.append(item)
            processed_count += 1
            
            prior_data = []
            if 'reference_court_case' is not None:
                prior_data.append(item)
                prior_data_count += 1
                print(f'판례를 참조한 데이터를 우선적으로 추가함 {prior_data_count}')
                
            

        except json.JSONDecodeError:
            print(f"⚠️ 경고: 파일 '{file_path}'에서 JSON 디코딩 오류가 발생했습니다. 이 파일을 건너뜁니다.")
        except Exception as e:
            print(f"⚠️ 경고: 파일 '{file_path}' 처리 중 알 수 없는 오류 발생: {e}. 이 파일을 건너뜁니다.")

    if processed_count == 0:
        print("🔍 처리할 JSON 파일을 찾지 못했습니다.")
        return

    # --- 2. 최종 결과를 하나의 JSON 파일로 저장 ---
    try:
        # with open(output_file, 'w', encoding='utf-8') as f:
        #     # indent=4를 사용하여 사람이 읽기 쉬운 형태로 저장
        #     json.dump(merged_data, f, ensure_ascii=False, indent=4)
        
        # print(f"\n✅ 성공적으로 {processed_count}개의 파일을 병합했습니다.")
        # print(f"결과 파일: '{output_file}'")
        
        with open(f"prior_{output_file}",'w', encoding='utf-8') as f:
            json.dump(prior_data, f, ensure_ascii=False, indent=4)
 
    except Exception as e:
        print(f"❌ 최종 파일 저장 중 오류 발생: {e}")
    
    

def count():
    with open('dataset.json','r') as f:
        data_list = json.load(f)
        print(f'dataset 길이 {len(data_list)}')
if __name__ == "__main__":
    # 이 코드를 실행하기 전에 'llm_test' 폴더를 현재 스크립트와 같은 위치에 생성하고
    # 그 안에 2만 개의 JSON 파일을 넣어주세요.
    
    # 🚨 참고: 'answer'와 'commentary'를 RAGAS 평가에서 요구하는 형식인
    # 리스트([value]) 형태로 변환하여 'ground_truths'와 'ground_truth_contexts'에 저장했습니다.
    make_json_file(INPUT_FOLDER, OUTPUT_FILE)
    count()