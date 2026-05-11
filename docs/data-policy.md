# 데이터 수집 및 저장 정책

## 1. 기본 원칙

Story Pattern Lab은 커뮤니티 원문 보관소가 아니라 바이럴 소재 레이더다. 따라서 콘텐츠 원문을 대량 저장하는 방식이 아니라, 게시글 단위의 URL·제목·반응 지표·분석값을 저장하는 지표 기반 소재 인덱싱 방식으로 설계한다.

## 2. 저장하는 데이터

- source_url
- platform
- source_name
- title
- posted_at
- first_collected_at
- last_collected_at
- like_count
- comment_count
- view_count
- rank_position
- engagement_rate
- growth_rate
- viral_score
- velocity_score
- debate_score
- risk_score
- summary
- keywords
- story_type
- analysis_status
- script_status

## 3. 저장하지 않는 데이터

- 댓글 원문 전체
- 작성자 닉네임
- 프로필 정보
- IP 또는 일부 IP
- 사진 원본
- 캡처 이미지
- 실명
- 전화번호
- 주소
- 회사명, 학교명 등 특정 식별 정보
- 삭제된 글의 원문

## 4. 댓글 처리 원칙

댓글 원문은 대량 저장하지 않는다. 필요한 경우 분석 시점에만 임시 처리하고, 저장 데이터는 감정 비율·핵심 반응 키워드·논쟁 포인트 요약으로 변환한다.

```text
댓글 원문 임시 처리
↓
감정 비율 추출
↓
주요 반응 키워드 추출
↓
논쟁 포인트 요약
↓
댓글 원문 폐기
↓
분석값만 저장
```

예시 저장 형태:

```json
{
  "comment_emotion": {
    "anger": 0.52,
    "shock": 0.24,
    "sympathy": 0.18,
    "humor": 0.06
  },
  "reaction_keywords": ["red flag", "gaslighting", "mother-in-law", "run"],
  "debate_point": "Was she overreacting or did she escape a toxic family?"
}
```

## 5. 수집 단계 분류

### Level 1. 허용형 소스

공식 API, RSS, 공개 트렌딩 피드처럼 비교적 안정적으로 사용할 수 있는 소스.

- Reddit official API
- RSS 제공 사이트
- 공개 API 제공 커뮤니티
- 뉴스/블로그 RSS

### Level 2. 관찰형 소스

공개 페이지는 접근 가능하지만 약관, robots.txt, 서버 부하, 수집 빈도 검토가 필요한 소스.

- 일반 커뮤니티 인기글 페이지
- 게시판 리스트 페이지
- 검색 결과 페이지

### Level 3. 보류형 소스

MVP에서는 제외한다.

- 로그인 필요 게시판
- 캡차가 있는 사이트
- 차단 우회가 필요한 사이트
- 약관상 자동 수집 금지가 명확한 사이트
- 개인정보 노출 위험이 큰 커뮤니티

## 6. 금지하는 수집 방식

- 로그인 우회
- 캡차 우회
- 차단 우회
- 비공개 영역 접근
- 서버에 과도한 요청
- 원문·댓글·유저정보 대량 저장
- AI 학습용 데이터셋 구축 목적의 무단 수집
- 원문을 거의 그대로 대본화

## 7. 대본 생성 정책

- 원문 문장 구조를 그대로 복제하지 않는다.
- 인물, 지역, 회사, 학교 등 식별 가능한 요소는 일반화한다.
- 대본은 해외 시청자용 서사 구조로 재창작한다.
- 사주·점성술은 직접 언급하지 않고 pattern, timing, karma 같은 표현으로 처리한다.

## 8. 리스크 판정 기준

Risk Score는 다음 항목을 종합한다.

- 개인정보 위험
- 명예훼손 위험
- 저작권 복제 위험
- 민감 주제 위험
- 플랫폼 약관 위험

Risk Score가 높은 소재는 자동 대본 생성을 제한하고, 수동 검토 상태로 이동한다.
