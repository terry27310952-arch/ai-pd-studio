# Story Pattern Lab 제품 개발 계획서

## 1. 제품 정의

Story Pattern Lab은 해외 커뮤니티와 사연형 콘텐츠 소스에서 반응 지표를 자동 수집하고, 바이럴 가능성이 높은 썰 소재를 선별해 영어권 유튜브 쇼츠·롱폼 대본으로 재구성하는 제작 보조 웹앱이다.

핵심은 원문 복제가 아니라 소재 판단 자동화다.

## 2. 핵심 사용자

- 해외 썰 유튜브 채널 운영자
- 쇼츠/릴스/틱톡용 사연 콘텐츠 제작자
- 콘텐츠 소재를 매일 대량으로 발굴해야 하는 PD
- 커뮤니티 반응 데이터를 기반으로 대본을 만들고 싶은 제작팀

## 3. 제품 원칙

1. 자동 수집형으로 시작한다.
2. 원문 대량 저장을 피하고 지표와 분석값 중심으로 저장한다.
3. 좋아요수, 댓글수, 조회수, 상승률, 댓글 밀도 같은 정량 지표를 우선한다.
4. LLM은 모든 글에 쓰지 않고 상위 후보에만 사용한다.
5. 대본은 원문을 복제하지 않고 새로운 서사로 재구성한다.
6. 브랜딩과 캐릭터명은 설정값으로 분리해 개발 중 변경 가능하게 둔다.

## 4. 1차 MVP 범위

### 포함

- Source Manager
- 자동 Collector Scheduler
- Reddit 또는 RSS 기반 소스 1개 이상 연동
- 게시글 메타데이터 저장
- Metric Snapshot 저장
- Viral Score / Velocity Score / Debate Density 계산
- 소재 카드 자동 생성
- 상위 후보 AI 분석
- 영어 쇼츠/롱폼 대본 생성
- 제목/썸네일 문구/댓글 질문 생성
- Production Board 상태 관리

### 제외

- 로그인 우회 기반 수집
- 캡차 우회
- 댓글 원문 대량 저장
- 영상 자동 생성
- TTS 자동 생성
- 유튜브 자동 업로드
- 모든 커뮤니티 범용 크롤링

## 5. 핵심 플로우

```text
Source Manager
↓
Collector Scheduler
↓
Metadata Collector
↓
Metric Snapshot DB
↓
Trend Scoring Engine
↓
Story Card Generator
↓
AI Analysis Queue
↓
Script Generator
↓
Production Board
```

## 6. 화면 구성

### Dashboard

- 오늘 수집한 소재 수
- Viral Score 상위 소재
- 댓글 증가율 상위 소재
- Risk Score 높은 소재
- 쇼츠 적합 소재
- 롱폼 적합 소재

### Source Manager

- 플랫폼
- 소스명
- 소스 URL
- 수집 방식
- 수집 주기
- 위험도
- 활성화 여부

### Story Radar

- 제목
- 플랫폼
- 좋아요수
- 댓글수
- 조회수
- 시간당 댓글 증가량
- Viral Score
- Velocity Score
- Debate Score
- Risk Score

### Story Detail

- 핵심 갈등
- 레드플래그
- 댓글 터질 포인트
- 해외 시청자 반응 포인트
- 쇼츠화 가능성
- 롱폼화 가능성
- 위험 요소

### Script Generator

- 영상 길이 선택
- 언어 선택
- 톤 선택
- 캐릭터 개입도 선택
- 제목 후보 생성
- 썸네일 문구 생성
- 쇼츠 대본 생성
- 롱폼 대본 생성

### Production Board

- Collected
- Analyzed
- Approved
- Scripted
- Rejected
- Archived

## 7. 기술 스택 제안

- Frontend: Next.js
- Backend: FastAPI
- Database: PostgreSQL
- Queue: Redis + RQ 또는 Celery
- Collector: Python worker
- AI Layer: LLM API
- Auth: Supabase Auth 또는 NextAuth
- Deploy: Vercel + Render/Fly.io

## 8. 1차 개발 목표

1차 목표는 완전한 자동 크롤러가 아니라, 매일 자동으로 후보를 모으고 점수순으로 정렬한 뒤 제작 가능한 대본까지 뽑는 최소 동작 제품이다.
