> ⚠️ **Phase1 개발용 빠른 실행 순서 (Mongo init + Kafka 포함)**  
> 팀원이 새로 클론했을 때, 아래 순서대로 실행하면 동일한 환경이 구성됩니다.
>
> 1. MongoDB 초기화(최초 1회, 또는 깨끗한 상태로 리셋하고 싶을 때만)  
>    ```bash
>    # 기존 mongo 컨테이너/볼륨 제거 - 데이터 전부 삭제되니 주의
>    docker compose -f docker-compose.mini.yml stop mongo
>    docker compose -f docker-compose.mini.yml rm -f mongo
>    docker volume rm sentencify-mvp_mongo-data  # 이름은 `docker volume ls`로 확인
>
>    # 다시 기동 (이때 docker/mongo-init.js가 자동 실행되어
>    # sentencify.correction_history / full_document_store 등 컬렉션+인덱스가 생성됨)
>    docker compose -f docker-compose.mini.yml up -d mongo
>    ```
> 3. Kafka + 나머지 서비스 기동  
>    ```bash
>    docker compose -f docker-compose.mini.yml up -d kafka api frontend redis qdrant
>    ```
> 2. Phase1용 Kafka 토픽 생성(최초 1회)  
>    ```bash
>    # A
>    docker compose -f docker-compose.mini.yml exec kafka \
>      kafka-topics --bootstrap-server kafka:9092 \
>      --create --topic editor_recommend_options \
>      --partitions 3 --replication-factor 1
>
>    # B
>    docker compose -f docker-compose.mini.yml exec kafka \
>      kafka-topics --bootstrap-server kafka:9092 \
>      --create --topic editor_run_paraphrasing \
>      --partitions 3 --replication-factor 1
>
>    # C
>    docker compose -f docker-compose.mini.yml exec kafka \
>      kafka-topics --bootstrap-server kafka:9092 \
>      --create --topic editor_selected_paraphrasing \
>      --partitions 3 --replication-factor 1
>
>    # E
>    docker compose -f docker-compose.mini.yml exec kafka \
>      kafka-topics --bootstrap-server kafka:9092 \
>      --create --topic context_block \
>      --partitions 3 --replication-factor 1
>
>    # I
>    docker compose -f docker-compose.mini.yml exec kafka \
>      kafka-topics --bootstrap-server kafka:9092 \
>      --create --topic model_score \
>      --partitions 3 --replication-factor 1
>    ```
> 5. 동작 확인  
>    - 프론트: `http://localhost:5173`  
>    - API 문서: `http://localhost:8000/docs`  
>    - Mongo 컬렉션:  
>      ```bash
>      docker compose -f docker-compose.mini.yml exec mongo mongosh
>      use sentencify
>      show collections   # correction_history, full_document_store 등 확인
>      ```
>
> 상세 진행 상황은 `docs/curr_progress.md`를 참고하세요.

---

# Sentencify MVP – 개발 환경 안내

Sentencify Phase 1(실시간 추천 및 데이터 수집)을 위한 로컬 개발 환경입니다.
본 프로젝트는 **Backend (FastAPI)**, **Frontend (React/Vite)**, **Infra(Kafka, MongoDB, Qdrant, Redis)** 를 Docker Compose 기반으로 통합 실행합니다.
모든 개발은 VS Code Dev Containers 또는 로컬 환경 중 선택하여 진행할 수 있습니다.

---

## 1. 구성 요소 (총 6개 서비스)

`docker-compose.mini.yml` 파일은 다음 6개의 컨테이너 서비스를 동시에 실행합니다.

1. `api`
   FastAPI 기반의 추천 API 서버
   주소: `http://localhost:8000`

2. `frontend`
   React + Vite 기반 사용자 인터페이스
   주소: `http://localhost:5173`

3. `kafka`
   이벤트 스트림(A / B / C / E / I 이벤트) 처리용 메시지 큐

4. `mongo`
   Ground Truth 저장소 (`D.correction_history`)

5. `qdrant`
   문맥 벡터 저장소 (`E.context_block`)

6. `redis`
   LLM 응답 캐시 저장소 (B 이벤트용)

모든 서비스는 `sentencify-net` 네트워크를 통해 서로 서비스 이름(kafka, mongo 등)만으로 통신합니다.

---

## 2. 시작하기

개발을 시작하는 방법은 두 가지입니다.
가급적 **VS Code Dev Container 방식(워크플로우 A)**을 권장합니다.

### 워크플로우 A. VS Code Dev Container 사용 (권장)

로컬 시스템에 Python 또는 Node를 설치하지 않아도 되고, 팀 전체가 동일한 개발 환경을 보장할 수 있습니다.

**사전 요구사항**

1. Docker Desktop (실행 중이어야 함)
2. VS Code
3. VS Code 확장: Dev Containers

**실행 단계**

1. 레포지토리 클론

   ```bash
   git clone https://github.com/<ORG_OR_USER>/sentencify-mvp.git
   cd sentencify-mvp
   ```

2. VS Code로 폴더 열기

   ```bash
   code .
   ```

3. 하단 알림에서
   **"Reopen in Container"** 선택
   (또는 `Cmd + Shift + P` → `Dev Containers: Reopen in Container`)

4. VS Code가 자동으로 다음을 수행

   * docker compose up 실행
   * api 컨테이너 내부로 VS Code 연결
   * api 컨테이너 내부에서 개발 가능해짐

**개발 환경 구동 완료 기준**

* 6개 서비스(api, frontend, kafka, mongo, qdrant, redis)가 실행됨
* VS Code 터미널은 자동으로 api 컨테이너 내부 쉘을 제공함

---

### 워크플로우 B. 로컬 환경에서 직접 실행 (선택)

VS Code Dev Container를 사용하지 않고 직접 실행하는 방법입니다.

1. Docker Compose 인프라 실행

   ```bash
   docker compose -f docker-compose.mini.yml up -d --build
   ```

2. 프론트엔드를 로컬에서 직접 실행하고 싶을 경우

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

---

## 3. 접속 및 상태 확인

서비스 실행 후 아래 주소에서 정상 작동 여부를 확인할 수 있습니다.

* 프론트엔드
  `http://localhost:5173`

* 백엔드 FastAPI 문서(Swagger)
  `http://localhost:8000/docs`

* 실행 중인 컨테이너 확인

  ```bash
  docker ps
  ```

* 컨테이너 전체 중지

  ```bash
  docker compose -f docker-compose.mini.yml down
  ```

---

## 4. 개발 워크플로우 (Hot Reloading)

`docker-compose.mini.yml`의 볼륨 설정으로 인해, 로컬에서 파일을 수정하면 컨테이너 내부 애플리케이션이 자동으로 재시작됩니다.

* **프론트엔드 (React/Vite)**
  `frontend/src` 내부 파일 수정 시 브라우저 자동 새로고침

* **백엔드 (FastAPI)**
  `api/app/main.py` 수정 시 `uvicorn` 자동 재시작
  (Dev Container 사용 시 VS Code 터미널에서 로그 확인 가능)

---

## 5. 디렉터리 구조

```
sentencify-mvp/
├── .devcontainer/
│   └── devcontainer.json
├── api/
│   ├── app/
│   │   └── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── docs/
│   └── phase1/
│       └── phase1-roadmap.md
├── frontend/
│   ├── src/
│   │   ├── utils/
│   │   ├── App.jsx
│   │   └── ...
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile
├── docker-compose.mini.yml
└── .gitignore
```

---

## 6. Phase 1 진행 상황 요약

### 완료된 항목

- 인프라 구축  
  - FastAPI, Frontend, Kafka, MongoDB, Qdrant, Redis 통합 실행 (`docker-compose.mini.yml`)
  - Kafka(KRaft 단일 노드) 설정 및 Phase1용 토픽 생성
- MongoDB 기본 스키마 자동 생성  
  - `docker/mongo-init.js`를 통해 `sentencify` DB에 다음 컬렉션/인덱스 자동 생성
    - `correction_history` (D), `full_document_store` (K)  
    - 선택: `usage_summary`, `client_properties`, `event_raw`, `metadata`
- `/recommend` API 고도화 (Stub 기반)
  - Pydantic 스키마: `RecommendRequest` / `RecommendResponse`
  - `context_full` 조립 + `context_hash`(sha256) 생성
  - Stub `P_rule`/`P_vec` + P_final로 추천 카테고리 선택
  - A/I/E 이벤트를 Kafka 토픽 및 `logs/*.jsonl`에 발행
  - `KAFKA_BOOTSTRAP_SERVERS` 환경변수로 Kafka Producer 사용
- Frontend ↔ `/recommend` 연동
  - 에디터 드래그 시 `/recommend` 호출
  - 응답의 `insert_id`, `recommend_session_id`, `reco_options`, `P_rule`, `P_vec`, `context_hash`를 FE 상태 및 디버그 로그에 반영

### 필요 작업 (진행 예정)

1. **Mongo / Redis Data Layer 확장**
   - `4_문장교정기록.json` → `correction_history` import (D)
   - (선택) 기업 1~3 JSON → `usage_summary`, `client_properties`, `event_raw` import
   - Redis LLM 캐시용 키 상수/클라이언트 헬퍼 정의

2. **B/C 이벤트 FE ↔ BE ↔ Kafka 플로우**
   - 백엔드: `POST /events/b`, `POST /events/c` 엔드포인트 추가 → Kafka `editor_run_paraphrasing`, `editor_selected_paraphrasing` 토픽으로 전달
   - 프론트: 교정 실행/후보 적용 시 B/C payload를 위 엔드포인트로 전송

3. **Kafka Consumers (특히 C/E)**
   - E Consumer: `context_block` 토픽 구독 → Qdrant `context_block_v1` upsert (Stub 가능)
   - C Consumer: `editor_selected_paraphrasing` 토픽 구독 → `correction_history`에 D 문서 insert

4. **최종 E2E 검증**
   - FE 드래그 → `/recommend` → B 실행 → C 선택 → Mongo/Qdrant/Redis까지 데이터 흐름 검증

Phase 1의 공식 완료 기준(DoD)은 `docs/phase1/Phase 1 로드맵.md` 문서를 참고합니다.
