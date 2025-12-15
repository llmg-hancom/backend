import json
import pandas as pd
from typing import List, Dict, Union

def calculate_retrieval_metrics(data: List[Dict[str, Union[str, List[str]]]]) -> pd.DataFrame:
    """
    미리 준비된 데이터(Ground Truth Contexts 및 Retrieved Contexts)를 기반으로
    Context Recall과 Context Precision을 계산합니다.
    
    Args:
        data: 질문, Ground Truth Contexts (G), Retrieved Contexts (R)를 포함하는 딕셔너리 리스트.
    
    Returns:
        질문과 계산된 지표를 포함하는 Pandas DataFrame.
    """
    results = []

    for item in data:
        question = item['question']
        context_set = set(item.get('ground_truth_contexts', []))
        court_case_value = item.get('reference_court_case')
        if court_case_value:
            court_case_set = set([str(court_case_value).strip()])
        else:
            court_case_set = set()

        g_set = context_set | court_case_set

        if 'contexts' not in item: 
            continue
        if item['contexts'] == [] :
            continue
        
        r_list = item['contexts']
        r_set = set(r_list)


        intersection = r_set.intersection(g_set)
        
        # --- Context Recall (재현율) 계산 ---
        # 정답에 필요한 전체 컨텍스트 중 얼마나 많이 가져왔는가? ( |R ∩ G| / |G| )
        if len(g_set) == 0:
            recall = 1.0 # 정답에 필요한 컨텍스트가 없으면, 재현율은 1.0
        else:
            recall = len(intersection) / len(g_set)

        # --- Context Precision (정밀도) 계산 ---
        # 가져온 컨텍스트 중 얼마나 많이 정답에 필요한 것인가? ( |R ∩ G| / |R| )
        if len(r_set) == 0:
            precision = 0.0 # 가져온 컨텍스트가 없으면, 정밀도는 0.0
        else:
            precision = len(intersection) / len(r_set)

        results.append({
            'question': question,
            'contexts_retrieved_count': len(r_set),
            'contexts_ground_truth_count': len(g_set),
            'context_recall': recall,
            'context_precision': precision
        })

    return pd.DataFrame(results)

# --- 평가 데이터셋 (미리 준비된 데이터) ---
# 주의: ground_truths 필드는 IR 지표 계산에 직접 사용되지 않지만, 데이터셋 구조를 위해 남겨둡니다.
import pandas as pd
from typing import List, Dict, Any

def calculate_average_retrieval_metrics(data: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    주어진 평가 데이터셋(딕셔너리 리스트)에서 context_recall 및 context_precision의
    전체 평균값을 계산합니다.
    
    Args:
        data: 질문별 검색 성능 지표를 담은 딕셔너리 리스트.
        
    Returns:
        평균 context_recall과 평균 context_precision을 담은 딕셔너리.
    """
    if not data:
        return {
            'average_context_recall': 0.0,
            'average_context_precision': 0.0
        }

    # 1. Pandas DataFrame으로 변환하여 통계 계산을 용이하게 합니다.
    df = pd.DataFrame(data)

    # 2. 'context_recall'과 'context_precision' 컬럼만 선택하여 평균을 계산합니다.
    # 데이터가 float 형식이 아닐 수 있으므로 (특히 JSON 로드 시), 
    # .astype(float)를 사용하여 명시적으로 실수형으로 변환합니다.
    
    # ⚠️ 주의: JSON 파일을 읽어올 때 이미 'context_recall', 'context_precision'이 
    # 누락되었거나 NaN 값이 포함된 경우가 있을 수 있으므로, .mean()은 안전하게 NaN을 무시합니다.
    
    avg_recall = df['context_recall'].astype(float).mean()
    avg_precision = df['context_precision'].astype(float).mean()

    return {
        'average_context_recall': avg_recall,
        'average_context_precision': avg_precision
    }

# --- 예시 데이터셋 (실제 100개 데이터라고 가정) ---


if __name__ == "__main__":
# --- 함수 실행 및 결과 출력 ---
    evaluation_data = []
    with open('dataset.json','r',encoding='utf-8') as f:
      evaluation_data = json.load(f)
      
    evaluation_df = calculate_retrieval_metrics(evaluation_data)
    output_filename = 'evaluation_output.json'
    print("=== Context Recall 및 Precision 평가 결과 ===")
    print(evaluation_df)
    evaluation_df.to_json(
        output_filename,
        orient='records',
        force_ascii=False,
        indent=4
    )
    
    with open(output_filename,'r',encoding='utf-8') as f:
      evaluation_output = json.load(f)    
    # --- 함수 실행 ---
    average_metrics = calculate_average_retrieval_metrics(evaluation_output)

    print("=== RAG 검색 성능 전체 평균 ===")
    print(f"평균 Context Recall: {average_metrics['average_context_recall']:.4f}")
    print(f"평균 Context Precision: {average_metrics['average_context_precision']:.4f}")
