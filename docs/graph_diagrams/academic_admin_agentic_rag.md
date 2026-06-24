# 대학 학사행정 Agentic RAG Graph

KHU 대학행정 매뉴얼 PDF 등 학사행정 문서를 검색하고, 문서가 관련되어 있더라도 질문에 답하기에 충분하지 않으면 KHU 도메인 웹검색을 보조 근거로 검토하는 흐름입니다.

## Graph Diagram

```mermaid
flowchart TD
    START([START])
    RETRIEVE["retrieve<br/>문서 검색"]
    GRADE["grade_documents<br/>검색 문서 관련성 평가"]
    DECIDE_RELEVANCE{"관련 문서가<br/>최소 기준 이상인가?"}
    ASSESS["assess_context_sufficiency<br/>답변 충분성 평가"]
    DECIDE_SUFFICIENCY{"내부 문서만으로<br/>답변 가능한가?"}
    REWRITE["rewrite_question<br/>질문 재작성"]
    WEB["web_search<br/>KHU 도메인 웹검색"]
    GENERATE["generate_answer<br/>근거 기반 답변 생성"]
    END([END])

    START --> RETRIEVE
    RETRIEVE --> GRADE
    GRADE --> DECIDE_RELEVANCE
    DECIDE_RELEVANCE -- "관련 문서 부족, 재작성 1회 미만" --> REWRITE
    REWRITE --> RETRIEVE
    DECIDE_RELEVANCE -- "관련 문서 부족, 재작성 후에도 부족" --> WEB
    DECIDE_RELEVANCE -- "관련 문서 있음" --> ASSESS
    ASSESS --> DECIDE_SUFFICIENCY
    DECIDE_SUFFICIENCY -- "충분" --> GENERATE
    DECIDE_SUFFICIENCY -- "충분하지 않음" --> WEB
    WEB --> GENERATE
    GENERATE --> END
```

## Detailed Flow

1. `retrieve`: 현재 질문과 최대 8개 이전 대화 메시지를 결합해 벡터 DB에서 학사행정 문서를 검색합니다.
2. `grade_documents`: 검색된 각 문서를 LLM grader가 `yes/no`로 평가합니다. 이 단계는 문서가 질문 주제와 관련 있는지를 판단합니다.
3. `관련성 기준`: `yes`로 평가된 문서 수가 `ACADEMIC_RAG_MIN_RELEVANT_DOCS` 이상이면 다음 단계로 진행합니다. 기본값은 1개입니다.
4. `rewrite_question`: 관련 문서가 부족하고 아직 재작성하지 않았다면, 이전 대화 맥락을 반영해 검색용 질문을 한 번 재작성합니다.
5. `assess_context_sufficiency`: 관련 문서가 있어도 그 문서만으로 구체적인 답변이 가능한지 다시 평가합니다. 현재 공지, 일정, URL, 양식처럼 변경 가능성이 큰 질문은 내부 문서에 명확한 근거가 없으면 부족하다고 판단합니다.
6. `web_search`: 관련 문서가 재검색 후에도 부족하거나, 관련 문서는 있지만 답변 충분성이 낮으면 `site:khu.ac.kr` 조건으로 웹검색을 수행합니다. 도메인은 `ACADEMIC_RAG_WEB_SEARCH_DOMAIN`으로 바꿀 수 있습니다.
7. `generate_answer`: 내부 문서를 최우선 근거로 사용하고, 웹검색 결과는 내부 문서가 부족할 때 보조 근거로 사용해 한국어 답변을 생성합니다.
