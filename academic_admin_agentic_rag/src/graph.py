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

try:
    from duckduckgo_search import DDGS
except ImportError:  # pragma: no cover
    DDGS = None

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.config import (  # noqa: E402
    CHAT_MODEL,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    ENABLE_WEB_SEARCH,
    MIN_RELEVANT_DOCS,
    RETRIEVAL_K,
    VECTOR_STORE_DIR,
    WEB_SEARCH_DOMAIN,
    WEB_SEARCH_MAX_RESULTS,
)


class AgentState(TypedDict, total=False):
    question: str
    chat_history: list[dict[str, str]]
    rewritten_question: str
    documents: list[Document]
    web_results: list[dict[str, str]]
    answer: str
    needs_rewrite: bool
    used_web_search: bool
    attempts: int
    relevant_document_count: int


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
is useful for answering the user's question. Respond with only yes or no.

Answer yes only when the document contains concrete information that can help answer
the question. Answer no for unrelated, generic, or insufficient passages.""",
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
Use the previous conversation only when the current question depends on it.
Respond with only the rewritten Korean search question.""",
        ),
        ("human", "Previous conversation:\n{chat_history}\n\nCurrent question:\n{question}"),
    ]
)

answer_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """당신은 대학 학사행정 문서 질의응답 도우미입니다.
반드시 제공된 근거 문서, 웹검색 보조 근거, 이전 대화 맥락에 기반해 한국어로 답변하세요.
최종 사실 판단은 내부 학사행정 문서를 우선하고, 웹검색 결과는 내부 문서가 부족할 때 보조 근거로만 사용하세요.
근거가 부족하면 추측하지 말고 확인이 필요하다고 말하세요.
이전 대화 내용은 사용자의 후속 질문을 해석하는 용도로만 사용하세요.
답변 끝에는 참고한 문서 또는 웹 출처를 간단히 적으세요.""",
        ),
        (
            "human",
            "이전 대화:\n{chat_history}\n\n질문:\n{question}\n\n근거 문서:\n{context}\n\n웹검색 보조 근거:\n{web_context}",
        ),
    ]
)


def format_chat_history(chat_history: list[dict[str, str]] | None) -> str:
    if not chat_history:
        return "No previous conversation."

    formatted_messages = []
    for message in chat_history[-8:]:
        role = message.get("role", "unknown")
        content = message.get("content", "")
        formatted_messages.append(f"{role}: {content}")
    return "\n".join(formatted_messages)


def build_retrieval_question(state: AgentState) -> str:
    question = state.get("rewritten_question") or state["question"]
    chat_history = format_chat_history(state.get("chat_history"))
    if chat_history == "No previous conversation.":
        return question
    return f"Previous conversation:\n{chat_history}\n\nCurrent question:\n{question}"


def retrieve(state: AgentState) -> AgentState:
    question = build_retrieval_question(state)
    documents = retriever.invoke(question)
    return {
        **state,
        "documents": documents,
        "attempts": state.get("attempts", 0),
        "used_web_search": state.get("used_web_search", False),
    }


def grade_documents(state: AgentState) -> AgentState:
    question = build_retrieval_question(state)
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

    relevant_count = len(relevant_docs)
    return {
        **state,
        "documents": relevant_docs,
        "relevant_document_count": relevant_count,
        "needs_rewrite": relevant_count < MIN_RELEVANT_DOCS,
    }


def decide_after_grading(state: AgentState) -> Literal["rewrite", "web_search", "generate"]:
    if not state.get("needs_rewrite"):
        return "generate"
    if state.get("attempts", 0) < 1:
        return "rewrite"
    if ENABLE_WEB_SEARCH and not state.get("used_web_search", False):
        return "web_search"
    return "generate"


def rewrite_question(state: AgentState) -> AgentState:
    chain = rewrite_prompt | llm | StrOutputParser()
    rewritten = chain.invoke(
        {
            "question": state["question"],
            "chat_history": format_chat_history(state.get("chat_history")),
        }
    ).strip()
    return {
        **state,
        "rewritten_question": rewritten,
        "attempts": state.get("attempts", 0) + 1,
    }


def web_search(state: AgentState) -> AgentState:
    if DDGS is None:
        return {
            **state,
            "used_web_search": True,
            "web_results": [
                {
                    "title": "web search unavailable",
                    "href": "",
                    "body": "duckduckgo_search package is not installed.",
                }
            ],
        }

    question = state.get("rewritten_question") or state["question"]
    search_query = f"site:{WEB_SEARCH_DOMAIN} {question}"
    results: list[dict[str, str]] = []
    with DDGS() as ddgs:
        for item in ddgs.text(search_query, max_results=WEB_SEARCH_MAX_RESULTS):
            results.append(
                {
                    "title": item.get("title", ""),
                    "href": item.get("href", ""),
                    "body": item.get("body", ""),
                }
            )

    return {
        **state,
        "used_web_search": True,
        "web_results": results,
    }


def format_document_context(documents: list[Document]) -> str:
    if not documents:
        return "No sufficiently relevant internal document was found."
    return "\n\n".join(
        f"[source: {doc.metadata.get('source', 'unknown')}]\n{doc.page_content}"
        for doc in documents
    )


def format_web_context(web_results: list[dict[str, str]] | None) -> str:
    if not web_results:
        return "No web search was used."
    return "\n\n".join(
        f"[web: {result.get('title', 'untitled')}]\nURL: {result.get('href', '')}\n{result.get('body', '')}"
        for result in web_results
    )


def generate_answer(state: AgentState) -> AgentState:
    documents = state.get("documents", [])
    web_results = state.get("web_results", [])
    if not documents and not web_results:
        return {
            **state,
            "answer": "관련 학사행정 문서나 웹검색 보조 근거를 찾지 못했습니다. 문서를 추가로 적재하거나 질문을 더 구체화해 주세요.",
        }

    chain = answer_prompt | llm | StrOutputParser()
    answer = chain.invoke(
        {
            "question": state["question"],
            "context": format_document_context(documents),
            "web_context": format_web_context(web_results),
            "chat_history": format_chat_history(state.get("chat_history")),
        }
    )
    return {**state, "answer": answer}


def build_graph():
    graph_builder = StateGraph(AgentState)
    graph_builder.add_node("retrieve", retrieve)
    graph_builder.add_node("grade_documents", grade_documents)
    graph_builder.add_node("rewrite_question", rewrite_question)
    graph_builder.add_node("web_search", web_search)
    graph_builder.add_node("generate_answer", generate_answer)

    graph_builder.add_edge(START, "retrieve")
    graph_builder.add_edge("retrieve", "grade_documents")
    graph_builder.add_conditional_edges(
        "grade_documents",
        decide_after_grading,
        {
            "rewrite": "rewrite_question",
            "web_search": "web_search",
            "generate": "generate_answer",
        },
    )
    graph_builder.add_edge("rewrite_question", "retrieve")
    graph_builder.add_edge("web_search", "generate_answer")
    graph_builder.add_edge("generate_answer", END)
    return graph_builder.compile()


graph = build_graph()


def ask(question: str, chat_history: list[dict[str, str]] | None = None) -> str:
    result = graph.invoke({"question": question, "chat_history": chat_history or []})
    return result["answer"]
