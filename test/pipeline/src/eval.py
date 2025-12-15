import os
import json
import pandas as pd
import psycopg
from dotenv import load_dotenv

# LangChain & Ragas 관련 임포트
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from langchain_ollama import OllamaEmbeddings
from ragas.testset import TestsetGenerator
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from datasets import Dataset

# --- 1. 설정 (환경 변수 및 DB 정보) ---
load_dotenv()

# DB 연결 정보 (사용자 환경에 맞게 수정)
DB_CONFIG = {
    "dbname": "hwp_qna_db",
    "user": "admin",
    "password": "d4bca2ff7e99cfef0d8f",
    "host": "34.193.249.143",
    "port": 5432
}

# 모델 설정
OLLAMA_HOST = "http://34.193.249.143:11434" # Ollama 서버
TEST_SIZE = 5  # 생성할 질문 개수 (테스트용으로 작게 시작)

# --- 2. DB에서 청크 데이터 가져오기 ---
def fetch_chunks_from_db(limit=50):
    """
    PostgreSQL에서 이미 청킹된 데이터를 가져와 LangChain Document로 변환합니다.
    """
    print(f"\n🔌 [Step 1] DB({DB_CONFIG['host']})에 연결하여 데이터 조회 중...")
    
    documents = []
    conn = None
    try:
        conn = psycopg.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # document_chunks 테이블에서 content와 meta를 가져옵니다.
        # 테스트를 위해 LIMIT을 걸어두는 것이 좋습니다.
        query = """
            SELECT content, meta 
            FROM document_chunks 
            LIMIT %s;
        """
        cur.execute(query, (limit,))
        rows = cur.fetchall()
        
        print(f"📥 DB에서 {len(rows)}개의 청크를 가져왔습니다. 변환을 시작합니다.")

        for content, meta in rows:
            # meta가 JSON 문자열이면 딕셔너리로 변환, 이미 딕셔너리(JSONB)면 그대로 사용
            if isinstance(meta, str):
                meta = json.loads(meta)
            
            # LangChain Document 객체 생성
            doc = Document(page_content=content, metadata=meta)
            documents.append(doc)
            
        print(f"✅ 총 {len(documents)}개의 Document 객체로 변환 완료!")
        return documents

    except Exception as e:
        print(f"❌ DB 연결 또는 조회 중 오류 발생: {e}")
        return []
    finally:
        if conn: conn.close()

# --- 3. 합성 테스트셋 생성 및 평가 ---
def run_simple_pipeline():
    # 1. DB 데이터 로드
    docs = fetch_chunks_from_db(limit=20) # 테스트용으로 20개만 로드
    if not docs:
        print("❌ 문서가 없어 종료합니다.")
        return

    print("\n🤖 [Step 2] Ragas용 모델 초기화 (Wrapper 적용)")
    
    # ⭐️ 중요: OpenAI 모델에 JSON 모드 강제 적용 (마크다운 오류 방지)
    generator_llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.1,
        model_kwargs={"response_format": {"type": "json_object"}} 
    )
    
    # 임베딩 모델
    embedding_model = OllamaEmbeddings(
        model="bge-m3:567m",
        base_url=OLLAMA_HOST
    )

    # ⭐️ Ragas V0.2 필수: LangChain 객체를 Wrapper로 감싸기
    ragas_llm = LangchainLLMWrapper(generator_llm)
    ragas_emb = LangchainEmbeddingsWrapper(embedding_model)

    print("\n🧪 [Step 3] 합성 테스트셋(질문-답변) 생성 시작...")
    
    try:
        generator = TestsetGenerator(llm=ragas_llm, embedding_model=ragas_emb)
        


        testset = generator.generate_with_langchain_docs(
            documents=docs,
            testset_size=TEST_SIZE
        )
        
        # Pandas DataFrame으로 변환
        test_df = testset.to_pandas()
        print(f"✅ 테스트셋 생성 완료! ({len(test_df)}개 질문)")
        
        # 중간 저장 (혹시 평가에서 터질 때를 대비)
        test_df.to_csv("simple_testset_raw.csv", index=False, encoding='utf-8-sig')

    except Exception as e:
        print(f"❌ 테스트셋 생성 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n⚖️ [Step 4] Ragas 평가(Evaluation) 시작...")
    
    # 컬럼 이름 매핑 (Ragas V0.2 -> 표준 이름)
    rename_map = {
        'user_input': 'question',
        'reference': 'ground_truth',
        'reference_contexts': 'contexts' # 생성 시 참고한 문맥을 그대로 평가에 사용 (가장 단순한 형태)
    }
    
    # 컬럼 변경 및 필수 컬럼 확인
    eval_df = test_df.rename(columns=rename_map)
    required_cols = ['question', 'contexts', 'ground_truth']
    
    if not all(col in eval_df.columns for col in required_cols):
        print(f"❌ 평가에 필요한 컬럼이 부족합니다. 현재 컬럼: {eval_df.columns.tolist()}")
        return

    # Dataset 변환
    eval_dataset = Dataset.from_pandas(eval_df)

    try:
        # 평가 실행
        result = evaluate(
            dataset=eval_dataset,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            llm=ragas_llm,        # 위에서 만든 Wrapper 재사용
            embeddings=ragas_emb  # 위에서 만든 Wrapper 재사용
        )

        print("\n🎉 [Step 5] 최종 평가 결과")
        print(result)

        # 결과 저장
        result_df = result.to_pandas()
        result_df.to_csv("simple_eval_result.csv", index=False, encoding='utf-8-sig')
        print("💾 결과가 'simple_eval_result.csv'에 저장되었습니다.")

    except Exception as e:
        print(f"❌ 평가 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_simple_pipeline()