# Story Pattern Lab Streamlit Starter

개발 초보도 바로 실행해볼 수 있는 테스트용 Streamlit 앱입니다.

FastAPI, Next.js, Docker, PowerShell을 몰라도 먼저 이 앱으로 전체 제품 흐름을 확인할 수 있습니다.

## 1. 실행 전 준비

Python이 설치되어 있어야 합니다.

## 2. 실행 방법

### 터미널에서 프로젝트 폴더로 이동

```bash
cd apps/streamlit
```

### 패키지 설치

```bash
pip install -r requirements.txt
```

### 앱 실행

```bash
streamlit run app.py
```

실행 후 브라우저에서 아래 주소가 열립니다.

```text
http://localhost:8501
```

## 3. 사용 방법

1. 왼쪽 사이드바에서 Reddit RSS 소스를 고릅니다.
2. `소재 수집하기` 버튼을 누릅니다.
3. Story Radar 표에서 수집된 소재를 확인합니다.
4. 소재를 선택하면 오른쪽에 쇼츠 대본 초안이 나옵니다.

## 4. 현재 되는 것

- Reddit RSS 기반 소재 수집
- 소스별 게시글 랭킹 수집
- 간단한 Viral Score 계산
- 소재 유형 자동 분류
- 쇼츠 대본 초안 생성

## 5. 현재 안 되는 것

- Reddit API 기반 좋아요/댓글수 수집
- 실제 LLM 대본 생성
- 데이터베이스 저장
- 자동 스케줄러
- Next.js 대시보드

이 Streamlit 버전은 개념 검증용입니다. 전체 흐름을 눈으로 확인한 뒤 FastAPI + Next.js 버전으로 확장합니다.
