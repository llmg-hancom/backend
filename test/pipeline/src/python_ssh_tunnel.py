from sshtunnel import SSHTunnelForwarder
from sqlmodel import create_engine, Session

SSH_HOST = "34.193.249.143"          # <-- ssh 대상은 IP 만
SSH_USER = "ubuntu"
SSH_PKEY = "/Users/yanghuiyeon/pem/hancom-prod-team1.pem"

DB_USER = "admin"
DB_PASS = "d4bca2ff7e99cfef0d8f"  # <- 이거 진짜 값으로 바꿔라
DB_NAME = "hwp_qna_db"

with SSHTunnelForwarder(
    (SSH_HOST, 22),
    ssh_username=SSH_USER,
    ssh_pkey=SSH_PKEY,
    remote_bind_address=("127.0.0.1", 5432),
    local_bind_address=("127.0.0.1", 5433)
) as tunnel:
    
    db_url = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@127.0.0.1:{tunnel.local_bind_port}/{DB_NAME}"
    
    engine = create_engine(db_url, echo=True)

    with Session(engine) as session:
        # 여기서 insert 실행
        print("✅ connected OK")
