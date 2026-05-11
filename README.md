# AI PD Studio

## Story Pattern Lab

Story Pattern Lab은 해외 커뮤니티와 사연형 콘텐츠 소스에서 반응 지표를 수집하고, 좋아요수·댓글수·조회수·상승률을 기반으로 바이럴 가능성이 높은 썰 소재를 자동 선별한 뒤, LLM을 활용해 영어권 유튜브 쇼츠/롱폼 대본으로 재구성하는 제작 보조 웹앱입니다.

### 핵심 방향

- 수동 URL 입력형 도구가 아니라 자동 소재 발굴형 레이더로 개발합니다.
- 원문 대량 저장소가 아니라 지표 기반 소재 인덱싱 시스템으로 설계합니다.
- 수집·저장·정렬·점수 계산은 하드코딩 기반으로 안정화합니다.
- 갈등 구조 분석·레드플래그 추출·해외 시청자용 대본 생성은 LLM 기반으로 처리합니다.
- 브랜딩은 앱 개발 중 테스트하며 캐릭터명, 채널명, 슬로건을 유연하게 변경할 수 있도록 설정값으로 분리합니다.

### 1차 MVP

1. Source Manager
2. Collector Scheduler
3. Metric Snapshot DB
4. Viral / Velocity / Debate Score Engine
5. AI Story Analysis Queue
6. Shorts / Longform Script Generator
7. Production Board

### 문서

- `docs/product-plan.md` : 제품 개발 방향
- `docs/data-policy.md` : 수집·저장·리스크 정책
- `docs/scoring-spec.md` : 점수 산정 방식
- `docs/brand-direction.md` : 브랜딩 개발 방향
- `docs/implementation-plan.md` : 개발 일정과 이슈 구조
