from __future__ import annotations

import sys
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.config import (  # noqa: E402
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    PRIVATE_DOCUMENTS_DIR,
    SAMPLE_DOCUMENTS_DIR,
    VECTOR_STORE_DIR,
)


SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}


def _load_file(path: Path) -> list[Document]:
    if path.suffix.lower() == ".pdf":
        return PyPDFLoader(str(path)).load()

    loader = TextLoader(str(path), encoding="utf-8")
    return loader.load()


def load_documents() -> list[Document]:
    documents: list[Document] = []
    for directory in (SAMPLE_DOCUMENTS_DIR, PRIVATE_DOCUMENTS_DIR):
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            for doc in _load_file(path):
                doc.metadata["source"] = str(path.relative_to(directory.parent))
                documents.append(doc)
    return documents


def ingest_documents() -> int:
    documents = load_documents()
    if not documents:
        raise RuntimeError(
            "No documents found. Add .txt, .md, or .pdf files under data/sample_documents "
            "or data/private_documents."
        )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(documents)

    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(VECTOR_STORE_DIR),
    )
    vector_store.reset_collection()
    vector_store.add_documents(chunks)
    return len(chunks)


if __name__ == "__main__":
    count = ingest_documents()
    print(f"Ingested {count} document chunks into {VECTOR_STORE_DIR}")
