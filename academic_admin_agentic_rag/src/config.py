from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
SAMPLE_DOCUMENTS_DIR = DATA_DIR / "sample_documents"
PRIVATE_DOCUMENTS_DIR = DATA_DIR / "private_documents"
VECTOR_STORE_DIR = PROJECT_DIR / "vector_store"
COLLECTION_NAME = "academic_admin_documents"

CHAT_MODEL = os.getenv("ACADEMIC_RAG_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL = os.getenv("ACADEMIC_RAG_EMBEDDING_MODEL", "text-embedding-3-large")

CHUNK_SIZE = int(os.getenv("ACADEMIC_RAG_CHUNK_SIZE", "900"))
CHUNK_OVERLAP = int(os.getenv("ACADEMIC_RAG_CHUNK_OVERLAP", "120"))
RETRIEVAL_K = int(os.getenv("ACADEMIC_RAG_RETRIEVAL_K", "5"))
MIN_RELEVANT_DOCS = int(os.getenv("ACADEMIC_RAG_MIN_RELEVANT_DOCS", "1"))
ENABLE_WEB_SEARCH = os.getenv("ACADEMIC_RAG_ENABLE_WEB_SEARCH", "true").lower() == "true"
WEB_SEARCH_DOMAIN = os.getenv("ACADEMIC_RAG_WEB_SEARCH_DOMAIN", "kumoh.ac.kr")
WEB_SEARCH_MAX_RESULTS = int(os.getenv("ACADEMIC_RAG_WEB_SEARCH_MAX_RESULTS", "5"))
