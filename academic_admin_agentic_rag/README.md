# 대학 학사행정 문서 질의응답을 위한 LangGraph 기반 Agentic RAG 시스템

이 폴더는 대학 학사행정 문서(학칙, 수강신청 안내, 장학 규정, 졸업 요건, 휴복학 안내 등)를 기반으로 질문에 답하는 Agentic RAG 시스템을 개발하기 위한 독립 작업 공간입니다.

## 목표

- 학사행정 문서를 벡터 DB에 적재
- 사용자 질문과 관련된 문서 검색
- 검색 결과의 관련성 평가
- 검색이 부족하면 질문 재작성 후 재검색
- 근거 문서 기반 답변 생성
- Streamlit UI로 질의응답 확인
- 현재 브라우저 세션의 과거 대화 내용을 기억하고 후속 질문에 반영

## Graph 구조

LangGraph 노드 흐름은 아래 문서에서 확인할 수 있습니다.

- [대학 학사행정 Agentic RAG Graph](../docs/graph_diagrams/academic_admin_agentic_rag.md)

## 폴더 구조

```text
academic_admin_agentic_rag/
  data/
    sample_documents/      # 테스트용 샘플 문서
    private_documents/     # 실제 학사행정 문서 위치, Git 제외
  src/
    app.py                 # Streamlit 앱
    config.py              # 모델/경로 설정
    graph.py               # LangGraph Agentic RAG 그래프
    ingest.py              # 문서 적재 스크립트
  run_cli.py               # 터미널 질의응답 실행
```

## 실행 준비

루트 프로젝트 폴더에서 실행합니다.

```powershell
cd C:\Users\hyeju\projects\inflearn-langgraph-agent
$env:OPENAI_API_KEY="your_openai_api_key_here"
```

## 1. 문서 적재

샘플 문서를 벡터 DB에 적재합니다.

```powershell
.\.venv-codex312\Scripts\python.exe .\academic_admin_agentic_rag\src\ingest.py
```

실제 문서는 아래 폴더에 넣으면 됩니다.

```text
academic_admin_agentic_rag/data/private_documents/
```

지원 형식: `.txt`, `.md`, `.pdf`

`private_documents/`에 실제 문서가 있으면 기본적으로 샘플 문서는 제외하고 실제 문서만 적재합니다.
샘플 문서까지 함께 적재하려면 `--include-sample` 옵션을 사용합니다.

## 2. 터미널에서 질문하기

```powershell
.\.venv-codex312\Scripts\python.exe .\academic_admin_agentic_rag\run_cli.py "졸업하려면 최소 몇 학점을 이수해야 해?"
```

## 3. Streamlit 앱 실행

```powershell
.\.venv-codex312\Scripts\streamlit.exe run .\academic_admin_agentic_rag\src\app.py
```

브라우저에서 `http://localhost:8501`로 접속하면 됩니다.

## 실제 문서 넣는 방법

1. 학교 학사행정 PDF/텍스트 문서를 `data/private_documents/`에 넣습니다.
2. `ingest.py`를 다시 실행합니다.
3. 앱에서 질문합니다.

민감한 내부 문서나 API 키는 Git에 올리지 않도록 주의하세요.
