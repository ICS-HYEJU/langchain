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


DIAGRAMS = [
    Diagram(
        slug="academic_admin_agentic_rag",
        title="대학 학사행정 Agentic RAG Graph",
        description=(
            "KHU 대학행정 매뉴얼 PDF 등 학사행정 문서를 검색하고, "
            "검색 결과가 부족하면 질문을 재작성한 뒤 답변을 생성하는 Agentic RAG 흐름입니다."
        ),
        mermaid="""flowchart TD
    START([START])
    RETRIEVE["retrieve<br/>문서 검색"]
    GRADE["grade_documents<br/>검색 문서 관련성 평가"]
    DECIDE{"관련 문서가 충분한가?"}
    REWRITE["rewrite_question<br/>질문 재작성"]
    GENERATE["generate_answer<br/>근거 기반 답변 생성"]
    END([END])

    START --> RETRIEVE
    RETRIEVE --> GRADE
    GRADE --> DECIDE
    DECIDE -- "아니오, 재작성 1회 미만" --> REWRITE
    REWRITE --> RETRIEVE
    DECIDE -- "예 또는 재작성 완료" --> GENERATE
    GENERATE --> END
""",
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
    ),
]


def render_markdown(diagram: Diagram) -> str:
    return f"""# {diagram.title}

{diagram.description}

```mermaid
{diagram.mermaid.strip()}
```
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
