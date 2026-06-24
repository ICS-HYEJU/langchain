# 주식 분석 Multi-Agent Graph

Supervisor가 시장 조사, 주가 조사, 기업 재무 조사 agent를 순차적으로 호출하고, 최종 analyst가 한국어로 매수/매도/보유 판단을 생성하는 흐름입니다.

## Graph Diagram

```mermaid
flowchart TD
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
```

## Detailed Flow

1. `supervisor`: 사용자 요청과 현재 메시지 상태를 보고 다음에 실행할 worker를 선택합니다.
2. `market_research`: Yahoo Finance 뉴스와 Polygon 도구를 사용해 시장/뉴스/거시 정보를 조사하고 한국어로 요약합니다.
3. `stock_research`: `yfinance` 기반 최근 1개월 주가 데이터를 조회해 사실 중심으로 정리합니다.
4. `company_research`: 기업 재무 정보와 SEC 공시 정보를 조회해 회사 펀더멘털 자료를 정리합니다.
5. `반복 제어`: 각 worker 결과는 다시 supervisor로 돌아가고, supervisor가 더 필요한 worker가 없다고 판단하면 `FINISH`를 반환합니다.
6. `analyst`: 수집된 정보를 종합해 한국어로 최종 판단을 생성하며, 결론은 `매수`, `매도`, `보유` 중 하나를 포함합니다.
