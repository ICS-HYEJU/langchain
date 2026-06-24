from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal, TypedDict

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.graph import END, START, StateGraph

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.config import (  # noqa: E402
    CHAT_MODEL,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    RETRIEVAL_K,
    VECTOR_STORE_DIR,
)


class AgentState(TypedDict, total=False):
    question: str
    rewritten_question: str
    documents: list[Document]
    answer: str
    needs_rewrite: bool
    attempts: int


def _build_vector_store() -> Chroma:
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(VECTOR_STORE_DIR),
    )


llm = ChatOpenAI(model=CHAT_MODEL, temperature=0)
vector_store = _build_vector_store()
retriever = vector_store.as_retriever(search_kwargs={"k": RETRIEVAL_K})


retrieval_grader_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You grade whether a retrieved university academic administration document
is useful for answering the user's question. Respond with only yes or no.""",
        ),
        (
            "human",
            "Question:\n{question}\n\nDocument:\n{document}",
        ),
    ]
)

rewrite_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You rewrite user questions for retrieval over Korean university academic
administration documents. Preserve the user's intent and expand abbreviations when useful.
Respond with only the rewritten Korean search question.""",
        ),
        ("human", "{question}"),
    ]
)

answer_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """당신은 대학 학사행정 문서 질의응답 도우미입니다.
반드시 제공된 근거 문서에 기반해 한국어로 답변하세요.
근거가 부족하면 추측하지 말고 확인이 필요하다고 말하세요.
답변 끝에는 참고한 문서 출처를 간단히 적으세요.""",
        ),
        (
            "human",
            "질문:\n{question}\n\n근거 문서:\n{context}",
        ),
    ]
)


def retrieve(state: AgentState) -> AgentState:
    question = state.get("rewritten_question") or state["question"]
    documents = retriever.invoke(question)
    return {
        **state,
        "documents": documents,
        "attempts": state.get("attempts", 0),
    }


def grade_documents(state: AgentState) -> AgentState:
    question = state.get("rewritten_question") or state["question"]
    chain = retrieval_grader_prompt | llm | StrOutputParser()

    relevant_docs: list[Document] = []
    for doc in state.get("documents", []):
        grade = chain.invoke(
            {
                "question": question,
                "document": doc.page_content[:2500],
            }
        ).strip().lower()
        if grade.startswith("y"):
            relevant_docs.append(doc)

    return {
        **state,
        "documents": relevant_docs,
        "needs_rewrite": not relevant_docs,
    }


def decide_after_grading(state: AgentState) -> Literal["rewrite", "generate"]:
    if state.get("needs_rewrite") and state.get("attempts", 0) < 1:
        return "rewrite"
    return "generate"


def rewrite_question(state: AgentState) -> AgentState:
    chain = rewrite_prompt | llm | StrOutputParser()
    rewritten = chain.invoke({"question": state["question"]}).strip()
    return {
        **state,
        "rewritten_question": rewritten,
        "attempts": state.get("attempts", 0) + 1,
    }


def generate_answer(state: AgentState) -> AgentState:
    documents = state.get("documents", [])
    if not documents:
        return {
            **state,
            "answer": "관련 학사행정 문서를 찾지 못했습니다. 문서를 추가로 적재하거나 질문을 더 구체화해 주세요.",
        }

    context = "\n\n".join(
        f"[source: {doc.metadata.get('source', 'unknown')}]\n{doc.page_content}"
        for doc in documents
    )
    chain = answer_prompt | llm | StrOutputParser()
    answer = chain.invoke(
        {
            "question": state["question"],
            "context": context,
        }
    )
    return {**state, "answer": answer}


def build_graph():
    graph_builder = StateGraph(AgentState)
    graph_builder.add_node("retrieve", retrieve)
    graph_builder.add_node("grade_documents", grade_documents)
    graph_builder.add_node("rewrite_question", rewrite_question)
    graph_builder.add_node("generate_answer", generate_answer)

    graph_builder.add_edge(START, "retrieve")
    graph_builder.add_edge("retrieve", "grade_documents")
    graph_builder.add_conditional_edges(
        "grade_documents",
        decide_after_grading,
        {
            "rewrite": "rewrite_question",
            "generate": "generate_answer",
        },
    )
    graph_builder.add_edge("rewrite_question", "retrieve")
    graph_builder.add_edge("generate_answer", END)
    return graph_builder.compile()


graph = build_graph()


def ask(question: str) -> str:
    result = graph.invoke({"question": question})
    return result["answer"]
