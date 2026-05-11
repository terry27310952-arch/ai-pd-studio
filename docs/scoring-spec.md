# 점수 산정 명세 v0.1

## 1. 목적

점수 시스템은 수집된 게시글을 좋아요 총량순으로만 보는 것이 아니라, 현재 불붙는 속도와 댓글 논쟁성을 함께 반영해 제작 우선순위를 정하기 위한 장치다.

## 2. 핵심 점수

### Viral Score

바이럴 가능성 총점.

```text
Viral Score =
현재 반응량 30
상승 속도 35
댓글 밀도 20
소스 내 랭킹 15
```

### Velocity Score

지금 뜨는 속도.

```text
Velocity Score =
최근 1시간 댓글 증가량
최근 1시간 좋아요 증가량
게시 후 경과 시간 보정
```

### Debate Density

댓글창이 얼마나 붙었는지 보는 점수.

```text
Debate Density =
댓글수 / 조회수
댓글수 / 좋아요수
댓글 증가 속도
```

### Conflict Score

AI 분석 후 산정하는 갈등 구조 점수.

```text
Conflict Score =
인물 간 대립 25
도덕적 판단 가능성 20
댓글 논쟁성 20
배신/거짓말 요소 15
반전 가능성 20
```

### Shorts Score

쇼츠 적합도.

```text
Shorts Score =
3초 후킹 가능성 30
한 문장 요약력 20
반전 압축력 20
댓글 유도력 20
시각화 쉬움 10
```

### Longform Score

롱폼 확장성.

```text
Longform Score =
서사 확장성 25
등장인물 관계성 20
갈등 단계성 20
중간 반전 가능성 20
엔딩 여운 15
```

### Risk Score

높을수록 위험하다.

```text
Risk Score =
개인정보 위험 25
명예훼손 위험 25
저작권 복제 위험 20
민감 주제 위험 15
플랫폼 약관 위험 15
```

## 3. 좋은 소재의 조건

```text
Viral Score 높음
Velocity Score 높음
Debate Density 높음
Shorts 또는 Longform Score 높음
Risk Score 낮음
```

## 4. 우선순위 판정

### A급 소재

- Viral Score 85 이상
- Risk Score 50 이하
- Shorts Score 또는 Longform Score 80 이상

### B급 소재

- Viral Score 70 이상
- Risk Score 60 이하
- Conflict Score 70 이상

### 보류 소재

- Risk Score 70 이상
- 개인정보/명예훼손 위험이 높은 경우
- 원문 의존도가 높은 경우

## 5. 스냅샷 기반 계산

상승률 계산을 위해 metric snapshot을 저장한다.

```text
current_snapshot
previous_snapshot
↓
like_delta
comment_delta
view_delta
hours_elapsed
↓
likes_per_hour
comments_per_hour
views_per_hour
```

초기 MVP에서는 단순 공식으로 시작하고, 실제 수집 데이터가 쌓이면 percentile 기반 정규화로 개선한다.
