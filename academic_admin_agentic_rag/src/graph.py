from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal, TypedDict
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

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
    needs_web_search: bool
    used_web_search: bool
    web_search_error: str
    attempts: int
    relevant_document_count: int
    sufficiency_reason: str


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
is topically relevant to the user's question. Respond with only yes or no.

Answer yes when the passage is about the same academic administration topic.
Answer no for unrelated or generic passages.""",
        ),
        ("human", "Question:\n{question}\n\nDocument:\n{document}"),
    ]
)

context_sufficiency_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You decide whether the provided internal university documents are sufficient
to answer the user's question without web search.

Respond in this exact format:
decision: yes|no
reason: short reason

Use decision: yes only when the documents contain enough concrete information to answer
the specific question. Use decision: no when the documents are only loosely related,
outdated for the question, missing the requested detail, or when the question asks about
current notices, schedules, URLs, forms, announcements, or information likely to change.""",
        ),
        (
            "human",
            "Previous conversation:\n{chat_history}\n\nQuestion:\n{question}\n\nInternal documents:\n{context}",
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
반드시 제공된 내부 문서, 웹검색 보조 근거, 이전 대화 맥락에 기반해 한국어로 답변하세요.
최종 사실 판단은 내부 학사행정 문서를 우선하고, 웹검색 결과는 내부 문서가 부족할 때 보조 근거로 사용하세요.
웹검색을 사용했다면 답변에 웹검색 근거를 사용했다는 점을 자연스럽게 밝히세요.
근거가 부족하면 추측하지 말고 확인이 필요하다고 말하세요.
이전 대화 내용은 사용자의 후속 질문을 해석하는 용도로만 사용하세요.
답변 끝에는 참고한 문서 또는 웹 출처를 간단히 적으세요.""",
        ),
        (
            "human",
            "이전 대화:\n{chat_history}\n\n질문:\n{question}\n\n내부 근거 문서:\n{context}\n\n웹검색 보조 근거:\n{web_context}",
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


def decide_after_grading(state: AgentState) -> Literal["rewrite", "web_search", "assess_context"]:
    if not state.get("needs_rewrite"):
        return "assess_context"
    if state.get("attempts", 0) < 1:
        return "rewrite"
    if ENABLE_WEB_SEARCH and not state.get("used_web_search", False):
        return "web_search"
    return "assess_context"


def assess_context_sufficiency(state: AgentState) -> AgentState:
    documents = state.get("documents", [])
    if should_force_web_search(state["question"]):
        return {
            **state,
            "needs_web_search": ENABLE_WEB_SEARCH and not state.get("used_web_search", False),
            "sufficiency_reason": (
                "Question asks for department-specific, current, or web-published information; "
                "web search is required even if internal documents are topically related."
            ),
        }

    if not documents:
        return {
            **state,
            "needs_web_search": ENABLE_WEB_SEARCH and not state.get("used_web_search", False),
            "sufficiency_reason": "No relevant internal documents after grading.",
        }

    chain = context_sufficiency_prompt | llm | StrOutputParser()
    response = chain.invoke(
        {
            "question": state["question"],
            "context": format_document_context(documents),
            "chat_history": format_chat_history(state.get("chat_history")),
        }
    )
    normalized = response.strip().lower()
    is_sufficient = "decision: yes" in normalized
    return {
        **state,
        "needs_web_search": ENABLE_WEB_SEARCH
        and not is_sufficient
        and not state.get("used_web_search", False),
        "sufficiency_reason": response.strip(),
    }


def decide_after_assessment(state: AgentState) -> Literal["web_search", "generate"]:
    if state.get("needs_web_search"):
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


def should_force_web_search(question: str) -> bool:
    department_terms = ("학과", "전공", "전자공학", "전자공학과", "전자정보", "컴퓨터", "기계", "신소재")
    graduation_terms = ("졸업학점", "졸업 학점", "이수학점", "전공학점", "졸업요건", "교육과정")
    current_terms = ("최신", "현재", "공지", "일정", "신청기간", "URL", "링크", "홈페이지", "양식")

    asks_department_graduation = any(term in question for term in department_terms) and any(
        term in question for term in graduation_terms
    )
    asks_current_web_info = any(term in question for term in current_terms)
    return asks_department_graduation or asks_current_web_info


def web_search(state: AgentState) -> AgentState:
    question = state.get("rewritten_question") or state["question"]
    search_queries = build_web_search_queries(question)

    results: list[dict[str, str]] = []
    errors: list[str] = []

    if DDGS is not None:
        ddg_results, ddg_errors = search_duckduckgo(search_queries)
        results.extend(ddg_results)
        errors.extend(ddg_errors)
    else:
        errors.append("duckduckgo_search package is not installed.")

    if len(results) < WEB_SEARCH_MAX_RESULTS:
        bing_results, bing_errors = search_bing(search_queries)
        results.extend(bing_results)
        errors.extend(bing_errors)

    if len(results) < WEB_SEARCH_MAX_RESULTS:
        direct_results, direct_errors = search_candidate_pages(question)
        results.extend(direct_results)
        errors.extend(direct_errors)

    results = dedupe_web_results(results)[:WEB_SEARCH_MAX_RESULTS]

    return {
        **state,
        "used_web_search": True,
        "web_search_error": "" if results else "; ".join(errors) or "No web results found.",
        "web_results": results,
    }


def build_web_search_queries(question: str) -> list[str]:
    base_query = f"site:{WEB_SEARCH_DOMAIN} {question}"
    queries = [base_query]

    if any(keyword in question for keyword in ("전자공학", "전자공학과", "전자정보")):
        queries.extend(
            [
                "금오공과대학교 전자공학과 졸업 학점",
                "금오공과대학교 전자공학과 졸업요건",
                "site:kumoh.ac.kr 전자공학과 졸업 학점",
                "site:kumoh.ac.kr 졸업학점 전공필수 전자공학과",
            ]
        )

    if "졸업" in question and "학점" in question:
        queries.append(f"금오공과대학교 {question} 교육과정 졸업요건")

    return list(dict.fromkeys(queries))


def search_duckduckgo(queries: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    results: list[dict[str, str]] = []
    errors: list[str] = []
    for query in queries:
        for backend in ("html", "lite", "auto"):
            try:
                with DDGS() as ddgs:
                    items = ddgs.text(query, backend=backend, max_results=WEB_SEARCH_MAX_RESULTS)
                results.extend(normalize_search_item(item) for item in items)
                if results:
                    return results, errors
            except Exception as exc:  # pragma: no cover - depends on search provider
                errors.append(f"DuckDuckGo {backend} failed for '{query}': {type(exc).__name__}: {exc}")
    return results, errors


def search_bing(queries: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    results: list[dict[str, str]] = []
    errors: list[str] = []
    for query in queries:
        try:
            response = requests.get(
                "https://www.bing.com/search",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=12,
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for item in soup.select("li.b_algo"):
                title = item.find("h2")
                link = title.find("a") if title else None
                snippet = item.find("p")
                href = link.get("href", "") if link else ""
                if not href:
                    continue
                results.append(
                    {
                        "title": title.get_text(" ", strip=True) if title else href,
                        "href": href,
                        "body": snippet.get_text(" ", strip=True) if snippet else "",
                    }
                )
            if results:
                return results, errors
        except Exception as exc:  # pragma: no cover - depends on network/search provider
            errors.append(f"Bing failed for '{query}': {type(exc).__name__}: {exc}")
    return results, errors


def search_candidate_pages(question: str) -> tuple[list[dict[str, str]], list[str]]:
    candidate_urls = [
        "https://www.kumoh.ac.kr/",
        "https://eng.kumoh.ac.kr/",
        "https://cic.kumoh.ac.kr/",
    ]
    results: list[dict[str, str]] = []
    errors: list[str] = []
    keywords = [token for token in ("전자공학", "졸업", "학점", "교육과정", "전자정보") if token in question]

    for url in candidate_urls:
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            text = soup.get_text(" ", strip=True)
            if keywords and not any(keyword in text for keyword in keywords):
                continue
            results.append(
                {
                    "title": soup.title.get_text(" ", strip=True) if soup.title else urlparse(url).netloc,
                    "href": url,
                    "body": text[:500],
                }
            )
        except Exception as exc:  # pragma: no cover
            errors.append(f"Direct page failed for '{url}': {type(exc).__name__}: {exc}")
    return results, errors


def normalize_search_item(item: dict[str, str]) -> dict[str, str]:
    return {
        "title": item.get("title", ""),
        "href": item.get("href", ""),
        "body": item.get("body", ""),
    }


def dedupe_web_results(results: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for result in results:
        href = result.get("href", "")
        key = href or result.get("title", "")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(result)
    return deduped


def format_document_context(documents: list[Document]) -> str:
    if not documents:
        return "No sufficiently relevant internal document was found."
    return "\n\n".join(
        f"[source: {doc.metadata.get('source', 'unknown')}]\n{doc.page_content}"
        for doc in documents
    )


def format_web_context(web_results: list[dict[str, str]] | None) -> str:
    if not web_results:
        return "No web search results were found."
    return "\n\n".join(
        f"[web: {result.get('title', 'untitled')}]\nURL: {result.get('href', '')}\n{result.get('body', '')}"
        for result in web_results
    )


def generate_answer(state: AgentState) -> AgentState:
    documents = state.get("documents", [])
    web_results = state.get("web_results", [])
    if not documents and not web_results:
        web_error = state.get("web_search_error")
        detail = f" 웹검색도 수행했지만 실패했습니다: {web_error}" if web_error else ""
        return {
            **state,
            "answer": f"관련 학사행정 문서나 웹검색 보조 근거를 찾지 못했습니다.{detail} 문서를 추가로 적재하거나 질문을 더 구체화해 주세요.",
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
    graph_builder.add_node("assess_context_sufficiency", assess_context_sufficiency)
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
            "assess_context": "assess_context_sufficiency",
        },
    )
    graph_builder.add_conditional_edges(
        "assess_context_sufficiency",
        decide_after_assessment,
        {
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
