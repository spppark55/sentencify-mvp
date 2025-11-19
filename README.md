# Sentencify MVP – Phase 1 개발 환경

Sentencify Phase 1(실시간 추천 및 데이터 파이프라인) 구축을 위한 통합 개발 환경입니다.  
FastAPI(Backend), React(Frontend), Kafka, MongoDB, Qdrant, Redis가 Docker Compose로 통합되어 있습니다.

---

## 🚀 빠른 실행 가이드 (Quick Start)

팀원은 아래 순서대로 실행하면, 동일한 환경에서 개발 및 테스트를 진행할 수 있습니다.

### 1. 컨테이너 실행 (전체 서비스 기동)

최초 실행 시 이미지를 빌드하고 컨테이너를 띄웁니다.

```bash
# 프로젝트 루트에서 실행
docker compose -f docker-compose.mini.yml up -d --build
```

MongoDB는 `docker/mongo-init.js`를 통해 자동으로 기본 컬렉션/인덱스를 생성합니다  
(`sentencify.correction_history`, `full_document_store`, `users` 등).

### 2. (필수) Kafka 데이터 컨슈머 실행

**중요:** 추천/교정 데이터를 DB(Mongo/Qdrant)에 적재하려면 백그라운드 컨슈머를 별도로 켜야 합니다.

```bash
# API 컨테이너 내부에서 컨슈머 스크립트 실행
docker compose -f docker-compose.mini.yml exec -d api python -m app.consumer
```

### 3. 동작 확인

- **Frontend:** `http://localhost:5173`
- **Backend Docs (Swagger):** `http://localhost:8000/docs`
- **MongoDB (예: Compass):** `mongodb://localhost:27017`

자세한 진행 상황은 `docs/curr_progress.md`를 참고하세요.

---

## 📊 현재 구현 기능 및 상태 (Phase 1 Status)

현재 **“실시간 추천 → 사용자 실행/선택 → 데이터 수집”**의 전체 사이클(E2E)이 연결되어 있습니다.

### 1. Frontend (React)

- 에디터 UI
  - 텍스트 입력, 드래그 시 자동 추천 요청(`/recommend`).
- 옵션 패널
  - 카테고리, 언어, 강도 조절 및 서술형 요청 입력.
- 이벤트 로깅
  - 추천(A), 실행(B), 선택(C) 이벤트를 `logEvent` 유틸에서 `/log`로 전송.
  - 동시에 `window.__eventLog`에 버퍼링하여 DebugPanel에서 확인 가능.

### 2. Backend (FastAPI)

- `/recommend`
  - Pydantic 기반 Request/Response 스키마 정의.
  - `context_prev/next + selected_text`로 `context_full`, `context_hash` 계산.
  - Stub `P_rule` / `P_vec`로 추천 카테고리 선택.
  - A/I/E 이벤트를 Kafka 토픽 및 파일 로그(`logs/a.jsonl`, `logs/i.jsonl`, `logs/e.jsonl`)에 기록.
- `/log`
  - 프론트에서 전송한 이벤트 payload를 수신.
  - `event` 필드에 따라:
    - `editor_run_paraphrasing` → Kafka `editor_run_paraphrasing` + `logs/b.jsonl`.
    - `editor_selected_paraphrasing` → Kafka `editor_selected_paraphrasing` + `logs/c.jsonl`.
    - 기타 이벤트 → `logs/others.jsonl`에만 기록.
- `/auth`
  - `POST /auth/signup`:
    - 이메일/비밀번호를 받아 `users` 컬렉션에 저장(이메일 유니크).
  - `POST /auth/login`:
    - 이메일/비밀번호 검증 후 JWT Access Token 발급(기본 24시간).
  - 비밀번호 해싱: `passlib[bcrypt]`, JWT: `python-jose[cryptography]`.

### 3. Data Pipeline (Kafka & Consumer)

- Kafka Topic (Phase1)
  - `editor_recommend_options` (A)
  - `editor_run_paraphrasing` (B)
  - `editor_selected_paraphrasing` (C)
  - `context_block` (E)
  - `model_score` (I)
- Consumer (`api/app/consumer.py`)
  - C 이벤트 (선택):
    - 토픽 `editor_selected_paraphrasing`을 구독.
    - `was_accepted != false` 인 이벤트를 MongoDB `sentencify.correction_history`에 insert.
  - E 이벤트 (문맥):
    - 토픽 `context_block`을 구독.
    - Qdrant `context_block_v1` 컬렉션에 Stub 벡터(0 벡터, dim=768)와 함께 upsert.

---

## 🧪 테스트 시나리오

Phase1이 올바르게 동작하는지 확인하려면 아래 시나리오를 따라가면 됩니다.

1. 추천 요청
   - 에디터에 문장을 여러 개 입력.
   - 일부를 드래그 → 자동으로 `/recommend` 호출.
   - 우측 옵션 패널에 추천 카테고리/언어가 갱신되는지 확인.
2. 교정 실행 및 적용
   - [실행(교정 후보 생성)] 버튼 클릭 → B 이벤트(`/log` → Kafka `editor_run_paraphrasing`).
   - 후보 문장 중 하나를 선택/적용 → C 이벤트(`/log` → Kafka `editor_selected_paraphrasing`).
3. 데이터 확인 (MongoDB)
   - 터미널에서:
     ```bash
     docker compose -f docker-compose.mini.yml exec mongo \
       mongosh sentencify --eval "db.correction_history.find().sort({_id:-1}).limit(1)"
     ```
   - 방금 선택한 문장/이벤트가 보이면 성공.

---

## 🛠️ 개발 팁 & 트러블슈팅

### MongoDB 데이터 초기화

DB를 완전히 초기화하고 싶다면 볼륨을 삭제하고 재기동합니다.

```bash
docker compose -f docker-compose.mini.yml down -v
docker compose -f docker-compose.mini.yml up -d
```

### Kafka 토픽 생성 (최초 1회)

Kafka 컨테이너가 올라온 뒤, Phase1에서 사용할 토픽을 생성합니다.

```bash
# 예시: A 이벤트용 토픽
docker compose -f docker-compose.mini.yml exec kafka \
  kafka-topics --bootstrap-server kafka:9092 \
  --create --topic editor_recommend_options \
  --partitions 3 --replication-factor 1
```

다른 토픽들(`editor_run_paraphrasing`, `editor_selected_paraphrasing`, `context_block`, `model_score`)도 같은 방식으로 생성할 수 있습니다.

### 기업 데이터 Import (로컬 전용)

`data/import/` 폴더에 기업 JSON 파일들을 넣고 아래 스크립트를 실행하면 MongoDB에 적재됩니다.

```bash
./scripts/mongo_import_company_data.sh
```

- 예:
  - `data/import/correction_history.json` → `correction_history`
  - `data/import/usage_summary.json` → `usage_summary`
  - `data/import/client_properties.json` → `client_properties`
  - `data/import/event_raw.json` → `event_raw`

---

## 📂 주요 디렉터리 구조

```
sentencify-mvp/
├── api/                  # FastAPI Backend
│   ├── app/
│   │   ├── main.py       # API 엔드포인트 (/recommend, /log, /auth 등)
│   │   ├── auth.py       # JWT 기반 인증 (signup/login)
│   │   └── consumer.py   # Kafka C/E 이벤트 Consumer
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/             # React Frontend
│   ├── src/
│   │   ├── App.jsx
│   │   ├── DebugPanel.jsx
│   │   ├── Editor.jsx
│   │   ├── OptionPanel.jsx
│   │   └── utils/
│   │       ├── api.js    # axios 기반 /recommend 호출
│   │       └── logger.js # /log 이벤트 전송 + 디버그 버퍼
│   ├── package.json
│   └── Dockerfile
├── docker/
│   └── mongo-init.js     # Mongo 초기 컬렉션/인덱스 생성 스크립트
├── docs/
│   ├── curr_progress.md  # 실제 진행 로그
│   └── phase1/           # Phase 1 설계/스펙 문서
├── scripts/
│   └── mongo_import_company_data.sh  # 기업 JSON → Mongo import 스크립트
├── data/                 # 로컬 전용 데이터 (Git에 포함되지 않음)
│   └── import/
│       ├── correction_history.json
│       ├── usage_summary.json
│       ├── client_properties.json
│       └── event_raw.json
└── docker-compose.mini.yml          # 인프라 구성 (api, frontend, kafka, mongo, qdrant, redis)
```
