# Story Pattern Lab API

FastAPI 기반 MVP 백엔드입니다.

## 로컬 실행

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Windows PowerShell:

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## 빠른 테스트

### 1. 상태 확인

```bash
curl http://localhost:8000/health
```

### 2. RSS 소스 등록

```bash
curl -X POST http://localhost:8000/sources \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "reddit",
    "source_name": "Reddit AITA RSS",
    "source_url": "https://www.reddit.com/r/AmItheAsshole/.rss",
    "source_type": "rss",
    "collection_method": "metadata",
    "risk_level": "low",
    "crawl_interval_minutes": 60,
    "is_active": true
  }'
```

### 3. 수집 실행

```bash
curl -X POST http://localhost:8000/collect/run
```

### 4. 소재 목록 확인

```bash
curl http://localhost:8000/stories
```

### 5. 분석 생성

```bash
curl -X POST http://localhost:8000/stories/1/analyze
```

### 6. 쇼츠 대본 생성

```bash
curl -X POST http://localhost:8000/stories/1/scripts/shorts
```

## 현재 구현 상태

- Source CRUD 일부
- RSS collector
- Metric snapshot 저장
- Viral / Velocity / Debate score 계산
- Stub AI analysis
- Stub Shorts script generator

다음 단계는 실제 LLM provider 연결과 Reddit API collector 추가입니다.
