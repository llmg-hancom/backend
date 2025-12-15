import requests

BASE_URL = "https://llmg-frontend.vercel.app/api/chat/sessions"
SESSION_ID = 31
access_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxNSIsImlhdCI6MTc2NTI2ODA1MCwiZXhwIjoxNzY1MzU0NDUwfQ.j6t_vgqlxueW5NU79eXemi4UK0ettS8CsN0aF6ROIRM"
QUERY_DATA = {
    "query": "무면허인데다가 술이 취한 상태에서 차량을 운전한 경우, 무면허운전행위와 음주운전행위의 양 죄는 어떤 관계에 있나요?",
    "include_law": True,
    "include_precedent": True
}

ENDPOINT_URL = f"{BASE_URL}/{SESSION_ID}/stream"
headers = {
    "Content-Type": "application/json",
    "Cookie": f"access_token={access_token}"
}

try:
    # stream=True 를 설정하여 스트리밍 응답을 처리할 수 있게 합니다.
    response = requests.post(
    ENDPOINT_URL,
    headers=headers
)
    
    # HTTP 에러 확인
    response.raise_for_status() 

    print("--- 스트리밍 응답 수신 중 ---")
    
    # 응답 내용을 라인 단위로 반복하여 읽습니다.
    for line in response.iter_lines():
        if line:
            # Server-Sent Events (SSE) 형식으로 가정하고 처리 (data: ...)
            decoded_line = line.decode('utf-8')
            # 'data: ' 접두사를 제거하고 실제 내용을 출력하거나 처리
            if decoded_line.startswith("data: "):
                content = decoded_line[6:]
                print(content, end="", flush=True) # flush=True 로 실시간 출력
    
    print("\n--- 스트리밍 완료 ---")

except requests.exceptions.RequestException as e:
    print(f"요청 중 오류 발생: {e}")