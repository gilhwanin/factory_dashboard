# Factory Dashboard 프로젝트

## 프로젝트 개요
- PyQt 기반 공장 대시보드 애플리케이션
- MSSQL Server (pymssql) 사용
- DB: GP (대시보드), GFOOD_B (마스터/레시피), GWCHUL (출하/발주)

## 핵심 파일 구조
- `UI/dashboard.py` — UI 정의
- `core/widget.py` — 시그널 연결
- `core/data_writer.py` — 데이터 쓰기 (발주량 갱신 등)
- `core/data_loader.py` — 데이터 로딩
- `logic/cal_values.py` — 업체별 계산 로직
- `UTIL/db_handler.py` — DB 연결/쿼리 실행
- `UTIL/const.py` — 상수 (DB_NAME = "GP")

## 업체별 발주량 조회 요약
- **홈플러스**: GWCHUL.PAN
- **이마트**: GFOOD_B.MMASTER → MPAN
- **마켓컬리**: GFOOD_B.MPAN (토요일 날짜보정)
- **롯데**: GFOOD_B.MJEN → MPAN
- **코스온**: GWCHUL.MASTER → COSONC
- **코스트코**: GWCHUL.COS_B (날짜보정 있음)
- 결과 저장: GP.ORDER_DASHBOARD.order_qty_after

## 주요 로직 문서
- [발주량 갱신 로직 상세](docs/발주량_갱신_로직.md) — 업체별 DB/테이블/쿼리 전체 정리
