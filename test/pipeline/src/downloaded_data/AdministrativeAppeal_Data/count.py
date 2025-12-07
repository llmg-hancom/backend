import json
import os


if __name__ == '__main__':
    base_dir = os.path.dirname(__file__)
    path = os.path.join(base_dir, 'decc_details.json')
    with open(path,'r',encoding='utf-8') as f:
        # **개선된 부분:** json.load()를 사용하여 파일을 파이썬 객체로 로드합니다.
        data_object = json.load(f) 
        
        # data_object는 이제 파이썬의 리스트 또는 딕셔너리 형태입니다.
        # len() 함수는 이 객체(예: 리스트)의 요소 개수를 반환합니다.
        print(f'{len(data_object)} 개의 법률 상세 데이터를 수집했습니다.')