# law_expose_db_loader.py

import json
import os
import re
import logging
from typing import List, Dict, Any, Tuple, override
import psycopg
from pgvector.psycopg import register_vector
# LawLoader와 동일한 임베딩 및 DB 설정을 사용합니다.
from langchain_community.embeddings import OllamaEmbeddings 
from langchain_text_splitters import MarkdownTextSplitter, RecursiveCharacterTextSplitter
from tqdm import tqdm
from modules.base.base_loader import BaseLoader, logger

class StatuteInterpretationLoader(BaseLoader):
    
    # ⭐️ LawLoader의 설정 및 DB/Embedding 초기화 로직을 그대로 사용
    def __init__(self,
                 db_local_port: int,
                 ollama_local_port: int):
        
        # 청킹 스플리터 초기화
        markdown_splitter = MarkdownTextSplitter(chunk_size=10000, chunk_overlap=0)
        recursive_splitter = RecursiveCharacterTextSplitter(
            separators=["\n##", "\n\n", "\n", " ", ""], chunk_size=1500, chunk_overlap=200
        )
        
        # ✅ BaseLoader.__init__ 호출 및 'expc' 타입 전달
        super().__init__('expc', 
                         db_local_port,
                         ollama_local_port,
                         markdown_splitter,
                         recursive_splitter)
    
    
    @override
    def _prepare_document(self, data: Dict[str, Any]) -> Dict[str, Any] | None:
        """ 
        단일 법령해석례 상세 데이터를 documents 테이블 삽입을 위한 Dict 형식으로 변환합니다. 
        """
        # 1. 필수 필드 추출 및 콘텐츠 조합
        expc_id = data.get('법령해석례일련번호')
        expc_title = data.get('안건명', '제목없음')
        
        # 콘텐츠 조합: 질의요지 + 회답 + 이유
        content_parts = [
            data.get('질의요지', ''),
            data.get('회답', ''),
            data.get('이유', '')
        ]
        # 2. 내용 추출
        # ⭐️ 새로운 구조를 반영한 콘텐츠 생성
        expc_content_segments = []

        # 1. 질의요지 추가
        if content_parts[0]:
            expc_content_segments.append(f"##[질의요지] {content_parts[0].strip()}")

        # 2. 회답 추가
        if content_parts[1]:
            expc_content_segments.append(f"##[회답] {content_parts[1].strip()}")

        # 3. 이유 추가
        if content_parts[2]:
            expc_content_segments.append(f"## 이유] {content_parts[2].strip()}")
            
        # 최종 콘텐츠를 이중 줄바꿈으로 연결
        expc_content = "\n\n".join(expc_content_segments)
        
        if not expc_id or not expc_content: 
            logger.warning(f"필수 필드(ID 또는 Content) 누락: ID={expc_id}")
            logger.warning(expc_content[:100])
            return None

        # 2. 메타데이터 설정 (chunks 테이블의 meta 필드로 들어갈 정보)
        metadata = {
            "법령해석례일련번호": expc_id,
            "안건명": expc_title,
            "안건번호": data.get('안건번호'),
            "해석기관명": data.get('해석기관명'),
            "해석일자": data.get('해석일자'),
            "질의기관명": data.get('질의기관명'),
            "source_type": "law_expose", 
        }
        
        # 3. documents 테이블 필드 설정
        MAX_VARCHAR_LENGTH = 225
        file_name = f"{expc_title[:MAX_VARCHAR_LENGTH]}({expc_id})"
        file_path = f"expose_{expc_id}_{data.get('안건번호')}"[:MAX_VARCHAR_LENGTH] 
        
        return {
            "page_content": expc_content,
            "metadata": metadata ,
            "precedent_serial_id":expc_id,
            "file_name": file_name,
            "file_path": file_path,
            "uploaded_by_user_id": 1,    
            "document_scope": "precedent", 
            "status": "ready",       
        }

    
    @override
    def run_etl_pipeline(self, data_list : List[Dict[str,Any]]):
        # BaseLoader의 run_etl_pipeline을 그대로 재사용
        return super().run_etl_pipeline(data_list)