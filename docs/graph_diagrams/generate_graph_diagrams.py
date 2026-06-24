from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


OUTPUT_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Diagram:
    slug: str
    title: str
    description: str
    mermaid: str
    flow: list[str]


DIAGRAMS = [
    Diagram(
        slug="academic_admin_agentic_rag",
        title="대학 학사행정 Agentic RAG Graph",
        description=(
            "KHU 대학행정 매뉴얼 PDF 등 학사행정 문서를 검색하고, 검색 결과가 부족하면 "
            "질문 재작성 후 재검색하며, 그래도 부족하면 KHU 도메인 웹검색을 보조 근거로 검토하는 흐름입니다."
        ),
        mermaid="""flowchart TD
    START([START])
    RETRIEVE["retrieve<br/>문서 검색"]
    GRADE["grade_documents<br/>검색 문서 관련성 평가"]
    DECIDE{"관련 문서가 충분한가?"}
    REWRITE["rewrite_question<br/>질문 재작성"]
    WEB["web_search<br/>KHU 도메인 웹검색"]
    GENERATE["generate_answer<br/>근거 기반 답변 생성"]
    END([END])

    START --> RETRIEVE
    RETRIEVE --> GRADE
    GRADE --> DECIDE
    DECIDE -- "충분" --> GENERATE
    DECIDE -- "부족, 재작성 1회 미만" --> REWRITE
    REWRITE --> RETRIEVE
    DECIDE -- "부족, 재작성 후에도 부족" --> WEB
    WEB --> GENERATE
    GENERATE --> END
""",
        flow=[
            "`retrieve`: 현재 질문과 최대 8개 이전 대화 메시지를 결합해 벡터 DB에서 학사행정 문서를 검색합니다.",
            "`grade_documents`: 검색된 각 문서를 LLM grader가 `yes/no`로 평가합니다. 질문에 답하는 데 구체적으로 도움이 되는 문서만 `yes`입니다.",
            "`충분성 기준`: `yes`로 평가된 관련 문서 수가 `ACADEMIC_RAG_MIN_RELEVANT_DOCS` 이상이면 충분하다고 판단합니다. 기본값은 1개입니다.",
            "`rewrite_question`: 충분하지 않고 아직 재작성하지 않았다면, 이전 대화 맥락을 반영해 검색용 질문을 한 번 재작성합니다.",
            "`web_search`: 재작성 후에도 충분하지 않으면 `site:khu.ac.kr` 조건으로 웹검색을 수행합니다. 도메인은 `ACADEMIC_RAG_WEB_SEARCH_DOMAIN`으로 바꿀 수 있습니다.",
            "`generate_answer`: 내부 문서를 최우선 근거로 사용하고, 웹검색 결과는 내부 문서가 부족할 때 보조 근거로만 사용해 한국어 답변을 생성합니다.",
        ],
    ),
    Diagram(
        slug="stock_trading_multi_agent",
        title="주식 분석 Multi-Agent Graph",
        description=(
            "Supervisor가 시장 조사, 주가 조사, 기업 재무 조사 agent를 순차적으로 호출하고, "
            "최종 analyst가 한국어로 매수/매도/보유 판단을 생성하는 흐름입니다."
        ),
        mermaid="""flowchart TD
    START([START])
    SUPERVISOR{"supervisor<br/>다음 작업자 선택"}
    MARKET["market_research<br/>시장 뉴스/거시 정보 조사"]
    STOCK["stock_research<br/>최근 주가 데이터 조사"]
    COMPANY["company_research<br/>재무 정보 및 SEC 공시 조사"]
    ANALYST["analyst<br/>한국어 최종 투자 의견 생성"]
    END([END])

    START --> SUPERVISOR
    SUPERVISOR -- "market_research" --> MARKET
    SUPERVISOR -- "stock_research" --> STOCK
    SUPERVISOR -- "company_research" --> COMPANY
    SUPERVISOR -- "FINISH" --> ANALYST
    MARKET --> SUPERVISOR
    STOCK --> SUPERVISOR
    COMPANY --> SUPERVISOR
    ANALYST --> END
""",
        flow=[
            "`supervisor`: 사용자 요청과 현재 메시지 상태를 보고 다음에 실행할 worker를 선택합니다.",
            "`market_research`: Yahoo Finance 뉴스와 Polygon 도구를 사용해 시장/뉴스/거시 정보를 조사하고 한국어로 요약합니다.",
            "`stock_research`: `yfinance` 기반 최근 1개월 주가 데이터를 조회해 사실 중심으로 정리합니다.",
            "`company_research`: 기업 재무 정보와 SEC 공시 정보를 조회해 회사 펀더멘털 자료를 정리합니다.",
            "`반복 제어`: 각 worker 결과는 다시 supervisor로 돌아가고, supervisor가 더 필요한 worker가 없다고 판단하면 `FINISH`를 반환합니다.",
            "`analyst`: 수집된 정보를 종합해 한국어로 최종 판단을 생성하며, 결론은 `매수`, `매도`, `보유` 중 하나를 포함합니다.",
        ],
    ),
]


def render_markdown(diagram: Diagram) -> str:
    flow_lines = "\n".join(f"{index}. {item}" for index, item in enumerate(diagram.flow, start=1))
    return f"""# {diagram.title}

{diagram.description}

## Graph Diagram

```mermaid
{diagram.mermaid.strip()}
```

## Detailed Flow

{flow_lines}
"""


def write_diagram(diagram: Diagram) -> None:
    markdown_path = OUTPUT_DIR / f"{diagram.slug}.md"
    mermaid_path = OUTPUT_DIR / f"{diagram.slug}.mmd"

    markdown_path.write_text(render_markdown(diagram), encoding="utf-8")
    mermaid_path.write_text(diagram.mermaid, encoding="utf-8")


def main() -> None:
    for diagram in DIAGRAMS:
        write_diagram(diagram)
        print(f"Wrote {diagram.slug}.md and {diagram.slug}.mmd")


if __name__ == "__main__":
    main()
