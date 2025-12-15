
# from functools import partial
# import json
# import logging
# from multiprocessing import Pool
# from modules.law_downloader import LawDownloader
# from sshtunnel import SSHTunnelForwarder
# import os
# import glob # JSON 파일 목록을 찾기 위해 glob 모듈 추가

# from modules.base.base_downloader import BaseDownloader
# from modules.base.base_loader import BaseLoader
# # 모든 로더 클래스를 명시적으로 import해야 globals().get()이 동작합니다.
# from modules.decc_loader import AdministrativeAppealLoader
# from modules.detc_loader import ConstitutionalDecisionLoader
# from modules.law_loader import LawLoader
# from modules.expc_loader import StatuteInterpretationLoader
# from modules.prec_loader import PrecedentLoader

# # 다운로더 클래스는 더 이상 사용되지 않으므로 제거하거나 주석 처리할 수 있습니다.
# from modules.decc_downloader import AdministrativeAppealDownloader
# from modules.detc_downloader import ConstitutionalDecisionDownloader
# from modules.law_downloader import LawDownloader
# from modules.expc_downloader import StatuteInterpretationDownloader
# from modules.prec_downloader import PrecedentDownloader




# OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL')
# OLLAMA_MODEL = os.getenv('OLLAMA_MODEL')
# # SSH 터널 설정
# SSH_HOST = '34.193.249.143'
# SSH_PORT = 22
# SSH_USERNAME = 'ubuntu'  # 예: ec2-user, ubuntu 등
# SSH_KEY_FILE = 'hancom-prod-team1.pem' # 실제 키 파일 경로로 수정 필요

# # 원격 PostgreSQL 서버 (최종 목적지) 정보
# REMOTE_DB_HOST = '127.0.0.1' 
# REMOTE_DB_PORT = 5432

# # Ollama 서비스 정보 추가
# OLLAMA_REMOTE_HOST = '127.0.0.1' 
# OLLAMA_REMOTE_PORT = 11434 # Ollama 기본 포트

# # 🔌 로컬 PC에 생성될 임시 포트 (0으로 설정하면 자동 선택)
# LOCAL_BIND_PORT = 0


# # 🔑 DB 접속 정보 (터널을 통해 접속할 최종 DB)
# POSTGRES_USER=os.getenv('POSTGRES_USER') # 실제 DB 사용자 이름으로 수정
# POSTGRES_PASSWORD=os.getenv('POSTGRES_PASSWORD') # 실제 DB 비밀번호로 수정
# POSTGRES_NAME=os.getenv('POSTGRES_NAME')
# POSTGRES_LOCAL_HOST = '127.0.0.1'

# # --- 로깅 설정 ---
# # main.py 상단 로깅 설정 부분
# LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
# os.makedirs(LOG_DIR, exist_ok=True)
# LOG_FILE = os.path.join(LOG_DIR, 'etl_pipeline.log')

# logging.basicConfig(
#     level=logging.INFO, 
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    
#     # ⭐️ 1. 핸들러 리스트 정의
#     handlers=[
#         # 2. 파일 핸들러 추가: 모든 로그를 파일에 저장
#         logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'),
#         # 3. 스트림 핸들러 유지: 터미널에도 실시간 출력
#         logging.StreamHandler()
#     ]
# )
# logger = logging.getLogger(__name__)

# # --- 이후의 모든 logger.info/error 호출은 파일과 콘솔에 동시에 기록됨 ---


# # 다운로더 작업자 함수는 더 이상 필요하지 않으므로 제거합니다.
# # def run_downloader_worker(downloader_class, output_dir):
# #     ... (기존 다운로더 함수 내용) ...
# #     pass

# def run_loader_worker(data_chunk, loader_class, db_port, ollama_port):
#     # 1. 로더 인스턴스 생성 (BaseLoader.__init__에서 friendly_name이 설정됨)
#     loader : BaseLoader = loader_class(db_port, ollama_port)
#     # 2. 로더의 친화적인 이름과 청크 개수 획득
#     friendly_name = getattr(loader, 'friendly_name', loader_class.__name__)
#     # ⭐️⭐️⭐️ 1. 작업 시작 로그 ⭐️⭐️⭐️
#     logger.info(f"✅ Worker Start: [{friendly_name}] 문서를 DB에 적재 시작.")
#     try:
#         loader.run_etl_pipeline(data_chunk)
#         return "Success"
#     except Exception as e:
#         logger.error(f"❌ Worker Error: [{friendly_name}] 오류 발생: {e}")
#         return f"Error: {e}"

# def split_data(data, num_chunks):
#     """데이터를 num_chunks 개수만큼 등분하는 함수"""
#     if not data:
#         return []
#     avg = len(data) / float(num_chunks)
#     out = []
#     last = 0.0
#     while last < len(data):
#         # last + avg가 리스트 길이를 초과하지 않도록 보장
#         end_index = min(int(last + avg), len(data))
#         out.append(data[int(last):end_index])
#         last += avg
#     return out


# if __name__ == "__main__":
#     # --- 1. SSHTunnelForwarder로 터널 생성 ---
#     tunnel = SSHTunnelForwarder(
#         (SSH_HOST, SSH_PORT),
#         ssh_username=SSH_USERNAME,
#         ssh_pkey=SSH_KEY_FILE,
        
#         remote_bind_addresses=[
#         (REMOTE_DB_HOST, REMOTE_DB_PORT),    
#         (OLLAMA_REMOTE_HOST, OLLAMA_REMOTE_PORT)],
#         # 로컬 PC에 터널 입구 생성
#         local_bind_addresses=[
#         ('127.0.0.1', LOCAL_BIND_PORT),
#         ('127.0.0.1', LOCAL_BIND_PORT)
#     ]
#     )
#     with tunnel:
       
        
#         DB_LOCAL_PORT = tunnel.local_bind_ports[0]
#         OLLAMA_LOCAL_PORT = tunnel.local_bind_ports[1]

#         script_dir = os.path.dirname(os.path.abspath(__file__))
#         data_root_dir = os.path.join(script_dir, 'downloaded_data')
        
#         # --- 2. 로더 작업을 위한 최종 데이터 준비 (JSON 파일 검색) ---
#         LOADER_TASKS = []
        
#         # downloaded_data 폴더 내의 모든 .json 파일을 재귀적으로 검색합니다.
#         json_files = glob.glob(os.path.join(data_root_dir, '**', 'law_details.json'), recursive=True)
        
#         if not json_files:
#             logger.error(f"❌ '{data_root_dir}' 폴더 및 하위 폴더에서 JSON 파일을 찾을 수 없습니다. 다운로드가 완료되었는지 확인해 주세요.")
#             exit()

#         logger.info(f"✅ 총 {len(json_files)}개의 JSON 파일을 발견했습니다. 로드 작업을 준비합니다.")

#         # 파일 이름과 로더 클래스를 매핑
#         for file_path in json_files:
#             try:
#                 # 폴더 이름에서 다운로더 이름을 추론 (예: downloaded_data/Law_Data/detail.json)
#                 # 파일 경로를 분석하여 적절한 로더 클래스 이름을 결정
#                 # (예: Law_Data -> LawDownloader -> LawLoader)
#                 dir_name = os.path.basename(os.path.dirname(file_path)) # 예: Law_Data
                
#                 # 'Data'를 제거하고 'Loader'를 붙여 로더 클래스 이름 추론 (예: LawLoader)
#                 base_name = dir_name.replace("_Data", "") # 예: Law
#                 loader_cls_name = f"{base_name}Loader" # 예: LawLoader

#                 loader_cls = globals().get(loader_cls_name) 

#                 if loader_cls:
#                     # 파일 로드
#                     with open(file_path, 'r', encoding='utf-8') as f:
#                         full_data = json.load(f)[465:]
                        
#                     # 파일에 데이터가 없는 경우 건너뛰기
#                     if not full_data:
#                         logger.warning(f"⚠️ 파일 '{file_path}'에 데이터가 없습니다. 건너뜁니다.")
#                         continue
                        
#                     LOADER_TASKS.append({
#                         "name": base_name, # 예: Law
#                         "file_path": file_path,
#                         "loader_cls": loader_cls,
#                         "full_data": full_data,
#                     })
#                 else:
#                     logger.error(f"❌ 폴더 이름 '{dir_name}'에 매핑되는 로더 클래스 ({loader_cls_name})를 찾을 수 없습니다.")

#             except Exception as e:
#                 logger.error(f"❌ 파일 로드 중 오류 발생 - '{file_path}': {e}")
                
#         if not LOADER_TASKS:
#             logger.error("❌ 처리할 유효한 로더 작업이 없습니다. 스크립트를 종료합니다.")
#             exit()
            
#         # --- 3. Loader 병렬 실행 ---
#         NUM_WORKERS = 4 # DB 로드를 위한 프로세스 개수 (Ollama 성능 고려)

#         for task in LOADER_TASKS:
#             logger.info(f"\n🚀 [START] {task['name']} DB 적재 처리 시작 (파일: {os.path.basename(task['file_path'])})...")
            
#             # 데이터 분할
#             chunks = split_data(task['full_data'], NUM_WORKERS)
#             logger.info(f"✂️ 데이터를 {len(chunks)}개의 청크로 분할했습니다. 총 항목 수: {len(task['full_data'])}")

#             # 작업자 함수 설정
#             worker_func = partial(run_loader_worker, 
#                                 loader_class=task['loader_cls'], 
#                                 db_port=DB_LOCAL_PORT, 
#                                 ollama_port=OLLAMA_LOCAL_PORT)

#             # 멀티프로세싱 실행
#             with Pool(processes=NUM_WORKERS) as pool:
#                 # pool.map은 worker_func의 결과를 기다립니다.
#                 results = pool.map(worker_func, chunks)

#             logger.info(f"✅ [DONE] {task['name']} DB 적재 완료. 결과: {results}")

#         logger.info("\n--- 모든 로더 파이프라인 작업 완료 ---")

