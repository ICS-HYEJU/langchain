from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.graph import graph  # noqa: E402


st.set_page_config(page_title="학사행정 Agentic RAG", page_icon="🎓")
st.title("대학 학사행정 문서 질의응답")

with st.sidebar:
    st.caption("대화 기록은 현재 브라우저 세션에서 유지됩니다.")
    if st.button("대화 초기화", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

question = st.chat_input("예: 졸업하려면 최소 몇 학점을 이수해야 하나요?")

if question:
    chat_history = list(st.session_state.messages)
    st.session_state.messages.append({"role": "user", "content": question})

    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("학사행정 문서를 검색하고 답변을 생성하는 중입니다..."):
            result = graph.invoke(
                {
                    "question": question,
                    "chat_history": chat_history,
                }
            )
            answer = result["answer"]
            st.write(answer)

            with st.expander("검색/재작성 상태"):
                st.write(
                    {
                        "rewritten_question": result.get("rewritten_question"),
                        "document_count": len(result.get("documents", [])),
                        "relevant_document_count": result.get("relevant_document_count", 0),
                        "attempts": result.get("attempts", 0),
                        "used_web_search": result.get("used_web_search", False),
                        "web_result_count": len(result.get("web_results", [])),
                        "web_search_error": result.get("web_search_error", ""),
                        "sufficiency_reason": result.get("sufficiency_reason", ""),
                        "remembered_messages": len(chat_history),
                    }
                )

    st.session_state.messages.append({"role": "assistant", "content": answer})
