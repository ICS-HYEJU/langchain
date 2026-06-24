from __future__ import annotations

import sys
from argparse import ArgumentParser
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


def _iter_supported_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return [
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]


def load_documents(include_sample: bool = False) -> list[Document]:
    documents: list[Document] = []
    private_files = _iter_supported_files(PRIVATE_DOCUMENTS_DIR)
    sample_files = _iter_supported_files(SAMPLE_DOCUMENTS_DIR)

    files = private_files
    if include_sample or not private_files:
        files = [*files, *sample_files]

    for path in files:
        directory = PRIVATE_DOCUMENTS_DIR if path.is_relative_to(PRIVATE_DOCUMENTS_DIR) else SAMPLE_DOCUMENTS_DIR
        try:
            for doc in _load_file(path):
                doc.metadata["source"] = str(path.relative_to(directory.parent))
                documents.append(doc)
        except Exception as exc:
            raise RuntimeError(f"Failed to load {path}") from exc
    return documents


def ingest_documents(include_sample: bool = False) -> int:
    documents = load_documents(include_sample=include_sample)
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


def main() -> None:
    parser = ArgumentParser(description="Ingest academic administration documents.")
    parser.add_argument(
        "--include-sample",
        action="store_true",
        help="Include sample documents together with private documents.",
    )
    args = parser.parse_args()

    count = ingest_documents(include_sample=args.include_sample)
    print(f"Ingested {count} document chunks into {VECTOR_STORE_DIR}")


if __name__ == "__main__":
    main()
