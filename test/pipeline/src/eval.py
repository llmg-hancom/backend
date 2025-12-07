import os
import pandas as pd
import ast
import json
from dotenv import load_dotenv
from datasets import Dataset
from pathlib import Path

# Ragas 및 LangChain Components (V0.2.X API 반영)
from ragas.testset import TestsetGenerator # 💡 V0.2.X: Generator는 일반 클래스입니다.
from ragas import evaluate
from ragas.metrics import (
    answer_relevancy,
    faithfulness,
    context_recall,
    context_precision,
)

# LangChain 모델 및 도구
from langchain_openai import ChatOpenAI 
from langchain_community.llms import Ollama 
from langchain_community.embeddings import OllamaEmbeddings 
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
# 💡 V0.2.X: Docstore 관련 라이브러리는 Ragas 내부에서 처리되거나 더 이상 노출되지 않습니다.



# --- 1. 설정 및 전역 구성 요소 초기화 ---
load_dotenv()

# 상수 설정
TEST_SIZE = 10
GENERATOR_LLM_MODEL = "gpt-4o-mini"
CRITIC_LLM_MODEL = "gpt-4o-mini"

OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL') 
OLLAMA_EMBEDDING_MODEL = os.getenv('OLLAMA_MODEL') 

# 🚨 경로 설정 (프로젝트 루트 기준)
try:
    BASE_DIR = Path(__file__).resolve().parents[3] 
except IndexError:
    BASE_DIR = Path(__file__).resolve().parent

JSON_FILE_PATH = BASE_DIR / "test" / "DATA" / "src" / "downloaded_data" / "Precedent_Data" / "prec_details.json"
CONTENT_COLUMN = "전문"
METADATA_COLUMN = ["판례정보일련번호", "사건번호", "법원명", "사건명", "선고일자"]

if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")

# 🚨 전역 LLM/Embedding 초기화 (한 번만!)
OLLAMA_EMBEDDINGS = OllamaEmbeddings(model=OLLAMA_EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL)
OPENAI_GENERATOR = ChatOpenAI(model=GENERATOR_LLM_MODEL, temperature=0.1)
OPENAI_CRITIC = ChatOpenAI(model=CRITIC_LLM_MODEL, temperature=0.1)
OLLAMA_RAG_LLM = Ollama(model=OLLAMA_RAG_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)


# --- 2. 데이터 로드 함수 (JSON 파일 로드) ---

def load_documents_from_json(file_path: Path, content_col, meta_cols):
    """JSON 파일을 로드하여 LangChain Document 리스트로 변환합니다."""
    
    if not file_path.exists():
        print(f"오류: JSON 파일 '{file_path}'를 찾을 수 없습니다.")
        return []
    
    documents = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if not isinstance(data, list):
            if isinstance(data, dict) and 'cases' in data:
                data = data['cases']
            else:
                print("오류: JSON 파일의 최상위 구조가 예상한 리스트 형태가 아닙니다.")
                return []

        for idx, item in enumerate(data):
            if not isinstance(item, dict): continue
            
            content = item.get(content_col, "")
            metadata = {}
            for col in meta_cols:
                metadata[col] = str(item.get(col, "N/A"))
            
            metadata['source'] = metadata.get(meta_cols[0], f"row_{idx}")

            if content.strip():
                documents.append(Document(page_content=content, metadata=metadata))
                
        print(f"JSON 파일에서 총 {len(documents)}개의 Document를 성공적으로 로드했습니다.")
        return documents

    except Exception as e:
        print(f"JSON 파일 로드 중 오류 발생: {e}")
        return []


# --- 3. 테스트셋 생성 함수 (V0.2.X API 적용) ---

def create_synthetic_testset(docs):
    """
    로드된 Document를 기반으로 Ragas 합성 테스트셋을 생성합니다. (Ragas V0.2.X)
    """
    print("\n=== 3. 합성 테스트셋 생성 시작 (Ragas V0.2.X) ===")
    
    if not docs:
        print("로드된 문서가 없어 테스트셋 생성을 중단합니다.")
        return pd.DataFrame()

    # 💡 V0.2.X: Generator 초기화 (Docstore 대신 Retriever를 사용하게 됩니다.)
    # V0.2.X에서는 LangchainLLMWrapper, LangchainEmbeddingsWrapper 등의 Wrapper가 필요하지 않습니다.
    generator = TestsetGenerator(
        generator_llm=OPENAI_GENERATOR, 
        critic_llm=OPENAI_CRITIC, 
        embeddings=OLLAMA_EMBEDDINGS, # Ollama 임베딩 직접 전달
    )

    # 💡 V0.2.X: 질문 진화 유형을 generation_config 딕셔너리로 정의
    generation_config = {
        "simple": TEST_SIZE * 0.5, 
        "reasoning": TEST_SIZE * 0.3, 
        "multi_context": TEST_SIZE * 0.2
    }
    
    # 💡 V0.2.X: generate() 메서드 사용 및 텍스트 분할기 전달
    try:
        testset = generator.generate(
            documents=docs, # 문서 목록
            test_size=TEST_SIZE, # 생성할 질문 수
            generation_config=generation_config, # 진화 유형 설정
            chunk_size=1000, # V0.2.X는 generate() 인자로 청크 크기 설정
            chunk_overlap=100, 
        )
        
        print(f"✅ 테스트셋 생성 완료. 총 {len(testset.to_pandas())}개 질문 생성.")
        return testset.to_pandas()
    
    except Exception as e:
        print(f"⚠️ 테스트셋 생성 실패. {e}")
        return pd.DataFrame()


# --- 4. RAG 파이프라인 구축 및 평가 실행 (이전과 동일) ---

def evaluate_rag_pipeline(test_df):
    """
    Ollama 기반 RAG 파이프라인을 구축하고 생성된 테스트셋으로 평가를 실행합니다.
    """
    if test_df.empty:
        print("평가를 위한 테스트셋이 없습니다. 종료합니다.")
        return
        
    print("\n=== 4. RAG 파이프라인 구축 및 평가 시작 ===")

    test_dataset = Dataset.from_pandas(test_df)
    
    def convert_contexts_field(example):
        try:
            # ast.literal_eval을 사용하려면 'contexts'가 문자열이어야 합니다.
            # V0.2.X 생성 결과는 이미 리스트일 수 있으므로 안전하게 처리
            contexts = example["contexts"]
            if isinstance(contexts, str):
                contexts = ast.literal_eval(contexts)
            return {"contexts": contexts}
        except Exception:
            return example

    test_dataset = test_dataset.map(convert_contexts_field)
    
    # RAG 파이프라인 구축
    rag_embeddings = OLLAMA_EMBEDDINGS # 전역 Ollama 임베딩 사용
    
    documents_for_faiss = [Document(page_content=c) for contexts in test_dataset["contexts"] for c in contexts]
    if not documents_for_faiss:
        print("문서 청크를 가져올 수 없어 FAISS 구축 불가.")
        return
        
    vectorstore = FAISS.from_documents(documents_for_faiss, rag_embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

    rag_prompt = PromptTemplate.from_template(
        """You are an assistant for question-answering tasks. Use the following retrieved context to answer the question in Korean.
        If you don't know the answer, just say that you don't know.
        CONTEXT: {context}
        QUESTION: {question}
        ANSWER:"""
    )

    rag_chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | rag_prompt
        | OLLAMA_RAG_LLM # 전역 Ollama LLM 사용
        | StrOutputParser()
    )

    print("Ollama RAG Chain을 사용하여 답변을 생성 중...")
    answers = rag_chain.batch(test_dataset["question"])
    
    if "answer" in test_dataset.column_names:
         test_dataset = test_dataset.remove_columns(["answer"])
    test_dataset = test_dataset.add_column("answer", answers)
    
    print("✅ 답변 생성 완료 및 데이터셋 업데이트 완료.")

    # RAGAS 평가 실행
    print("\n=== 5. RAGAS 평가 실행 중 ===")
    
    result = evaluate(
        dataset=test_dataset,
        metrics=[context_precision, faithfulness, answer_relevancy, context_recall],
    )

    print("\n\n=== RAGAS 평가 최종 결과 ===")
    print(result)
    print("✅ RAGAS 평가 워크플로우 성공적으로 완료.")


# --- 5. 메인 실행 블록 ---

if __name__ == "__main__":
    
    # 1. 데이터 로드
    docs = load_documents_from_json(JSON_FILE_PATH, CONTENT_COLUMN, METADATA_COLUMN)

    # 2. 합성 테스트셋 생성
    test_df = create_synthetic_testset(docs)

    # 3. RAG 파이프라인 구축 및 평가 실행
    evaluate_rag_pipeline(test_df)