# Sentencify Phase 1 – Current Progress Log

> 진행 상황과 코드/환경 변경사항을 **시간순으로 누적 기록**하는 문서입니다.  
> 새 작업을 할 때마다 이 파일에 아래 포맷으로 항목을 추가합니다.

---

## 2025-11-22 – Phase 1.5 Step4 (Adaptive Scoring) 진행 중

### 0. Step 2. Diff Ratio Calculation Logic ✅
- Schema K(`FullDocumentStore`, `api/app/schemas/document.py`) 정의: `blocks`, `latest_full_text`, `previous_full_text`, `diff_ratio`, `last_synced_at`, `schema_version` 등 v2.3 필드 정리.
- Diff 계산 유틸(`api/app/utils/diff.py`) 추가: `calculate_diff_ratio(prev, curr)`가 Levenshtein 거리를 `max(len(prev), 1)`로 정규화하여 0~1 범위 비율을 반환.
- 의존성: `api/requirements.txt`에 `python-Levenshtein` 추가 및 Standalone 테스트(`scripts/test_step2_diff.py`)로 "✅ Step 2 Diff Logic Passed" 확인.

### 1. Step 3. Macro ETL Service ✅
- 파일: `api/app/services/macro_service.py`
  - `.env` 로딩 및 `gemini-2.5-flash` 모델 호출 → LLM 응답 JSON을 정제/파싱하여 `DocumentContextCache`로 직렬화 후 Redis TTL 1시간으로 저장.
- 파일: `scripts/test_step3_macro_llm.py`
  - `AsyncMock`으로 LLM 응답을 패치하고 실제 Redis(`localhost:6379`)에 쓰기/읽기 검증. 성공 시 "✅ Step 3 Macro ETL Service Passed".

### 2. Step 4. Adaptive Scoring Logic (In Progress)
- 파일: `api/app/utils/scoring.py`
  - `calculate_maturity_score()`로 문서 길이를 [0,1] 스케일링, `calculate_alpha()`로 도큐먼트 가중치 계산.
- 파일: `api/app/main.py`
  - `/recommend`에서 Redis `get_macro_context()`를 불러 `P_doc`을 구성하고, 문서 길이 기반 `doc_maturity_score` → `applied_weight_doc(alpha)`를 산출.
  - 최종 점수는 `(1-α)·P_vec + α·P_doc`으로 평가하며, 응답 및 A/I 이벤트에 `P_doc`, `doc_maturity_score`, `applied_weight_doc` 필드를 추가.
- 파일: `scripts/test_step4_scoring.py`
  - 짧은/긴 텍스트 케이스와 벡터/도큐먼트 스코어 블렌딩을 검증하여 "✅ Step 4 Scoring Logic Passed" 출력.

---

## 2025-11-19 – Phase 1.5 Step1 (Redis Schema F) 완료

### 1. Step 1. Redis Infrastructure & Schema F ✅
- Phase 1.5 Step 1을 완료하고, `docker-compose.mini.yml`의 `redis` 서비스/`api/requirements.txt`의 `redis` 패키지 존재를 재확인(추가 변경 없음).
- Schema F(`DocumentContextCache`, `api/app/schemas/macro.py`)를 v2.3 필드( `macro_llm_version`, `schema_version` 등)로 정의.
- Async Redis 클라이언트(`api/app/redis/client.py`): `get_redis_client()`, `set_macro_context()`, `get_macro_context()` 구현. 기본 호스트 `redis`, TTL 기본 3600초.

### 2. Standalone 테스트 & Phase1.5 테스트 리스트
- 파일: `scripts/test_step1_redis.py`
  - `REDIS_HOST`/`REDIS_PORT` 환경변수로 접속 대상 지정 → Schema F 저장/조회 라운드트립 검증 후 "✅ Step 1 Redis Test Passed" 출력.
- 파일: `docs/phase1.5_test_lists.md`
  - 체크리스트 `Step 1: Redis Connection & Schema F Serialization` 완료 표시.

---

## 2025-11-18 – Phase1 Step1 E2E + Kafka 세팅

### 1. BE `/recommend` API 고도화 (Stub 기반)
- 파일: `api/app/main.py`
- 주요 변경
  - `RecommendRequest`/`RecommendResponse` 정식 스키마 정의
    - Request: `doc_id`, `user_id`, `selected_text`, `context_prev/next`, `field`, `language`, `intensity`, `user_prompt`.
    - Response: `insert_id`, `recommend_session_id`, `reco_options[]`, `P_rule`, `P_vec`, `context_hash`, 버전 정보(`model_version`, `api_version`, `schema_version`, `embedding_version`).
  - `context_full` 조립 및 `context_hash = sha256(doc_id + ":" + context_full)` 구현.
  - Stub 점수:
    - `P_rule = {"thesis": 0.5, "email": 0.3, "article": 0.2}`
    - `P_vec  = {"thesis": 0.7, "email": 0.2, "article": 0.1}`
    - `P_final = 0.5 * P_rule + 0.5 * P_vec` 로 최종 카테고리 선택.
  - 추천 옵션 생성:
    - `reco_options = [{ category: best_category, language: req.language or "ko", intensity: req.intensity or "moderate" }]`
  - CORS 허용 추가 (로컬 Vite 프론트에서 직접 호출 가능하도록).

### 2. A / I / E 이벤트 + 파일 로그 + Kafka 연동
- 파일: `api/app/main.py`
- 주요 변경
  - 공통 JSONL 로그:
    - `logs/a.jsonl`, `logs/i.jsonl`, `logs/e.jsonl` 에 이벤트를 한 줄씩 기록하는 `append_jsonl()` 구현.
  - Kafka Producer 초기화:
    - `KAFKA_BOOTSTRAP_SERVERS` 환경변수 사용 (`kafka:9092` 기본값).
    - `get_kafka_producer()`에서 `KafkaProducer` 생성, 실패 시 `None` 반환.
  - 이벤트별 헬퍼:
    - `produce_a_event(payload)` → `editor_recommend_options` 토픽 + `logs/a.jsonl`.
    - `produce_i_event(payload)` → `model_score` 토픽 + `logs/i.jsonl`.
    - `produce_e_event(payload)` → `context_block` 토픽 + `logs/e.jsonl`.
  - `/recommend` 내부에서 한 번의 호출로 A/I/E 이벤트 모두 생성:
    - A: `editor_recommend_options` (입력 컨텍스트 + P_rule/P_vec + reco_options).
    - I: `model_score` (P_rule/P_vec 및 내부 스코어 스냅샷).
    - E: `context_block` (context_full, context_hash, doc_id 중심).

### 3. Frontend ↔ `/recommend` 연동 및 상태 구조
- 파일: `frontend/src/App.jsx`, `frontend/src/utils/api.js`, `frontend/src/DebugPanel.jsx`, `frontend/src/OptionPanel.jsx`
- 주요 변경
  - `axios` 기반 API 클라이언트 추가 (`src/utils/api.js`):
    - `baseURL = VITE_API_BASE_URL || "http://localhost:8000"`
    - `postRecommend(payload)` 헬퍼.
  - 선택 이벤트 → `/recommend` 호출 흐름:
    - `handleSelectionChange`를 `async`로 변경, 드래그 시:
      - 문맥 계산: `context_prev` / `context_next` (문장 단위).
      - intensity 매핑: 슬라이더 0/1/2 → `weak`/`moderate`/`strong`.
      - `/recommend` Request body를 spec에 맞춰 생성 후 `postRecommend` 호출.
    - Response 처리:
      - `recommendId = recommend_session_id`, `recommendInsertId = insert_id` 상태로 저장.
      - `recoOptions`, `contextHash` 상태로 저장.
      - 첫 번째 추천 옵션 기준으로 `category`, `language`를 기본값으로 세팅.
    - FE 로그 (`logEvent`)로 A 이벤트 디버깅용 기록:
      - `event: "editor_recommend_options"` + `P_rule`, `P_vec`, `context_hash`, 버전 정보 포함.
  - B/C 이벤트 쪽 키 정합성 보완:
    - `editor_run_paraphrasing` / `editor_selected_paraphrasing` 로그에
      - `recommend_session_id`, `source_recommend_event_id = insert_id` 포함.

### 4. Docker / Kafka 개발 스택 정리
- 파일: `docker-compose.mini.yml`, `frontend/Dockerfile`
- 주요 변경
  - Kafka 서비스 재구성 (KRaft 단일 노드):
    - `image: apache/kafka:3.7.0`
    - 환경변수:
      - `KAFKA_NODE_ID`, `KAFKA_PROCESS_ROLES`, `KAFKA_LISTENERS`, `KAFKA_ADVERTISED_LISTENERS`,
        `KAFKA_CONTROLLER_LISTENER_NAMES`, `KAFKA_CONTROLLER_QUORUM_VOTERS`,
        `KAFKA_LISTENER_SECURITY_PROTOCOL_MAP`, `KAFKA_LOG_DIRS`, `CLUSTER_ID` 등.
    - 볼륨: `kafka-data:/var/lib/kafka/data`
    - 네트워크: `sentencify-net`
  - API 서비스에서 Kafka 사용:
    - `KAFKA_BOOTSTRAP_SERVERS: "kafka:9092"` 환경변수 유지.
  - Frontend Dockerfile 정리:
    - `node:20-alpine` + `npm ci` 사용.
    - `npm run dev -- --host 0.0.0.0 --port 5173`로 Vite dev 서버 실행.
  - Frontend service command 수정:
    - `docker-compose.mini.yml`에서 `frontend`에
      - `command: sh -c "npm install && npm run dev -- --host 0.0.0.0"` 적용 (컨테이너 내 dev 서버 자동 실행).

### 5. Kafka 토픽 생성 및 확인 (Phase1용)
- Kafka 컨테이너 기동:
  - `docker-compose -f docker-compose.mini.yml up -d kafka`
- 생성한 토픽들:
  - `editor_recommend_options`  (A)
  - `editor_run_paraphrasing`  (B)
  - `editor_selected_paraphrasing` (C)
  - `context_block`            (E)
  - `model_score`              (I)
- 커맨드 예시:
  - 리스트: `kafka-topics --bootstrap-server kafka:9092 --list`
  - 생성: `kafka-topics --bootstrap-server kafka:9092 --create --topic <name> --partitions 3 --replication-factor 1`

### 6. 스펙 문서 정리
- 파일: `docs/phase1/phase1-front-spec.md`
  - 3.1.3에 **“Phase 1 Step 1 – 실제 구현 규칙 정리”** 섹션 추가.
  - FE ↔ `/recommend` 간 필드 사용 규칙 및 응답 활용 방식 정리:
    - `doc_id`, `user_id`, `selected_text`, `context_prev/next`, `field`, `language`, `intensity`, `user_prompt`.
    - `insert_id`, `recommend_session_id`, `reco_options`, `P_rule`, `P_vec`, `context_hash` 등.
- 파일: `docs/phase1/phase1-recommend-spec.md`
  - `/recommend` ↔ P_rule/P_vec 내부 인터페이스 정의:
    - `RecommendContext` 구조,
    - `compute_p_rule(ctx) -> dict[str, float]`,
    - `compute_p_vec(ctx) -> dict[str, float]`,
    - P_final 결합 규칙 및 `reco_options` 생성 규칙,
    - A/I/E 이벤트와의 관계 정리.

### 7. 현재까지 Phase1 Step1 상태 요약
- FE에서 드래그 시 `/recommend` 호출 → Stub 기반 추천 옵션/ID 반환 OK.
- 같은 호출에서 A/I/E 이벤트 생성 → `logs/*.jsonl` + Kafka 토픽까지 적재 OK.
- Kafka 인프라/토픽 구성 완료.
- P_rule/P_vec은 Stub이지만, 인터페이스/스키마/로그 구조는 Phase1 스펙과 정합.
- 다음 단계로는 Mongo/Redis Data Layer 준비 및 B/C 이벤트 엔드포인트/Consumer 구현 예정.

---

## 2025-11-18 – Mongo 초기 스키마 init 스크립트 추가

### 1. Mongo init 스크립트 도입
- 파일: `docker/mongo-init.js`
- 목적:
  - 로컬/팀원 환경에서 MongoDB 컨테이너가 처음 올라올 때,
    Phase1에서 사용하는 컬렉션과 인덱스를 **자동으로 동일하게 생성**하기 위함.
- 주요 내용:
  - DB: `sentencify`
  - 컬렉션 생성 (존재하지 않을 때만):
    - `correction_history`
    - `full_document_store`
    - `usage_summary` (선택)
    - `client_properties` (선택)
    - `event_raw` (선택)
    - `metadata` (init 정보 기록용)
  - 인덱스:
    - `correction_history`:
      - `{ user: 1, created_at: -1 }`
      - `{ field: 1, created_at: -1 }`
      - `{ intensity: 1 }`
    - `full_document_store`:
      - `{ doc_id: 1 }` (unique)
      - `{ last_synced_at: -1 }`
    - `usage_summary`:
      - `{ recent_execution_date: -1 }`
      - `{ count: -1 }`
    - `client_properties`:
      - `{ "properties.last_seen": -1 }`
      - `{ distinct_id: 1 }` (unique)
    - `event_raw`:
      - `{ event: 1, time: -1 }`
      - `{ insert_id: 1 }` (unique)
      - `{ user_id: 1, time: -1 }`
  - `metadata` 컬렉션에 init 기록 1건 insert:
    - `type: "init"`, `source`, `created_at`, `note` 등.

### 2. docker-compose에 init 스크립트 연결
- 파일: `docker-compose.mini.yml`
- 변경 사항:
  - `mongo` 서비스에 init 스크립트 볼륨 마운트 추가:
    ```yaml
    mongo:
      image: mongo:6.0
      ports:
        - "27017:27017"
      volumes:
        - mongo-data:/data/db
        - ./docker/mongo-init.js:/docker-entrypoint-initdb.d/mongo-init.js:ro
      networks:
        - sentencify-net
    ```
- 동작 방식:
  - `mongo-data` 볼륨이 **새로 생성될 때** 컨테이너 기동 시 `mongo-init.js`가 자동 실행된다.
  - 이미 존재하는 `mongo-data` 볼륨이 있으면 init 스크립트는 다시 실행되지 않으므로,
    완전히 초기 상태를 맞추려면 `docker volume rm sentencify-mvp_mongo-data` 후 재기동이 필요하다(주의).

---

## 2025-11-18 – 기업 JSON import용 Mongo 스크립트 및 data 폴더 구조

### 1. 기업 JSON 전용 data 폴더 및 Git 설정
- 파일: `.gitignore`
  - `data/` 항목 추가 → 기업 실제 JSON 데이터는 Git에 올라가지 않도록 설정.
- 폴더:
  - `data/` (프로젝트 루트)
    - 팀원이 각자 로컬에서 기업 제공 JSON 파일을 여기에 복사해서 사용.
    - 예: `data/4_문장교정기록.json` (D.correction_history 원본).

### 2. Mongo 컨테이너에서 data 폴더 접근 설정
- 파일: `docker-compose.mini.yml`
- 변경 사항:
  - `mongo` 서비스에 `./data`를 읽기 전용으로 마운트:
    ```yaml
    mongo:
      image: mongo:6.0
      ports:
        - "27017:27017"
      volumes:
        - mongo-data:/data/db
        - ./docker/mongo-init.js:/docker-entrypoint-initdb.d/mongo-init.js:ro
        - ./data:/data/import:ro
      networks:
        - sentencify-net
    ```
- 효과:
  - 호스트의 `sentencify-mvp/data/*` 파일이 Mongo 컨테이너 내부에서 `/data/import/*` 경로로 보인다.
  - `mongoimport`로 로컬 JSON을 쉽게 import 가능.

### 3. 기업 JSON import 스크립트 추가
- 파일: `scripts/mongo_import_company_data.sh`
- 역할:
  - Phase1에서 사용하는 기업 JSON(D 스키마)을 MongoDB `sentencify.correction_history` 컬렉션에 import.
- 주요 내용:
  - 기본값:
    - `COMPOSE_FILE = docker-compose.mini.yml`
    - `DB_NAME = sentencify`
    - 컨테이너 내부 데이터 경로: `/data/import`
  - 실행 로직:
    ```bash
    docker compose -f "${COMPOSE_FILE}" exec mongo \
      mongoimport \
        --db "${DB_NAME}" \
        --collection correction_history \
        --file "/data/import/4_문장교정기록.json" \
        --jsonArray
    ```
  - 실행 방법:
    ```bash
    cd sentencify-mvp
    chmod +x scripts/mongo_import_company_data.sh  # 최초 1회
    ./scripts/mongo_import_company_data.sh
    ```
- 주의 사항:
  - JSON 파일들은 Git에 포함되지 않으며, 팀원이 각자 `data/import` 폴더에 수동으로 복사해야 한다.
  - 컬렉션에 중복 insert를 방지하려면, 필요 시 `mongoimport` 옵션 또는 사전 정리 로직을 추가하는 것을 고려.

---

## 2025-11-18 – B/C 이벤트 수집용 /log 엔드포인트 추가

### 1. LogRequest 모델 및 /log API
- 파일: `api/app/main.py`
- 추가/변경 사항:
  - `LogRequest` Pydantic 모델 정의:
    - 필드: `event: str`
    - `extra = "allow"` 설정으로 나머지 필드는 자유롭게 허용 (전체 payload를 그대로 보존).
  - `POST /log` 엔드포인트 추가:
    - Body를 `LogRequest`로 수신하고 `req.model_dump()`로 전체 payload를 dict로 변환.
    - `event` 필드 값에 따라 분기:
      - `"editor_run_paraphrasing"` → B 이벤트로 처리.
      - `"editor_selected_paraphrasing"` → C 이벤트로 처리.
      - 그 외 이벤트 → `logs/others.jsonl`에만 기록.

### 2. B/C 이벤트용 프로듀서 헬퍼
- 파일: `api/app/main.py`
- 추가 함수:
  - `produce_b_event(payload: Dict) -> None`
    - `logs/b.jsonl`에 append.
    - Kafka Producer가 활성화되어 있으면 `editor_run_paraphrasing` 토픽으로 send.
    - Kafka 오류 발생 시 예외를 삼키고 흐름 유지.
  - `produce_c_event(payload: Dict) -> None`
    - `logs/c.jsonl`에 append.
    - Kafka Producer가 활성화되어 있으면 `editor_selected_paraphrasing` 토픽으로 send.
    - Kafka 오류 발생 시 동일하게 무시.
- 기존 A/I/E 헬퍼(`produce_a_event`, `produce_i_event`, `produce_e_event`)와 동일한 패턴 유지.

### 3. Kafka 비활성화(KAFKA_ENABLED=false) 처리
- `get_kafka_producer()` 로직을 재사용하여,
  - `KAFKA_ENABLED=false`인 경우 `None`을 반환하며,
  - B/C/A/I/E 모든 `produce_*_event` 함수에서 `producer is None`이면 Kafka 전송을 건너뛰도록 구현.
- 결과:
  - Kafka가 꺼져 있거나 설정이 잘못되더라도 `/recommend` 및 `/log`는 에러 없이 실행되고,
  - 최소한 로컬 파일 로그(`logs/*.jsonl`)는 항상 남도록 보장.

---

## 2025-11-18 – Kafka C/E Consumer 스켈레톤 추가

### 1. consumer.py 생성
- 파일: `api/app/consumer.py`
- 역할:
  - Kafka 토픽에서 C/E 이벤트를 구독하여
    - C: MongoDB `correction_history`에 적재
    - E: Qdrant `context_block_v1`에 upsert
  하는 Phase1용 Consumer 스켈레톤.

### 2. 공통 설정
- 사용 라이브러리:
  - `kafka-python`, `pymongo`, `qdrant-client`
- 환경변수:
  - `KAFKA_BOOTSTRAP_SERVERS` (기본 `kafka:9092`)
  - `MONGO_URI` (기본 `mongodb://mongo:27017`)
  - `MONGO_DB_NAME` (기본 `sentencify`)
  - `QDRANT_HOST` (기본 `qdrant`)
  - `QDRANT_PORT` (기본 `6333`)
  - `EMBED_DIM` (기본 `768`, Stub 벡터 차원)

### 3. C 이벤트 Consumer (`editor_selected_paraphrasing`)
- 함수: `process_c_events()`
- 동작:
  - KafkaConsumer 설정:
    - 토픽: `editor_selected_paraphrasing`
    - `auto_offset_reset="earliest"`, `enable_auto_commit=True`
    - `group_id="sentencify_c_consumer"`
  - 각 메시지에 대해:
    - payload를 dict로 파싱.
    - `was_accepted`가 명시적으로 `false`인 경우는 무시 (실제 채택된 것만 저장).
    - MongoDB `sentencify.correction_history` 컬렉션에 `insert_one`:
      - 전체 payload를 복사하고 `created_at`에 현재 UTC ISO 문자열을 추가.
  - 예외 발생 시:
    - 에러 메시지만 출력하고 루프는 계속.

### 4. E 이벤트 Consumer (`context_block`)
- 함수: `process_e_events()`
- 동작:
  - Qdrant 클라이언트 초기화 후 `ensure_qdrant_collection()` 호출:
    - 컬렉션 이름: `context_block_v1`
    - `VectorParams(size=EMBED_DIM, distance=Cosine)` 로 컬렉션이 없을 경우 생성.
  - KafkaConsumer 설정:
    - 토픽: `context_block`
    - `group_id="sentencify_e_consumer"`
  - 각 메시지에 대해:
    - payload를 메타데이터로 활용.
    - Stub 벡터 생성: `[0.0] * EMBED_DIM`
    - Qdrant `upsert` 호출:
      - `PointStruct(id=str(uuid.uuid4()), vector=vector, payload=payload)` 형태로 등록.
  - 예외 발생 시:
    - 에러 메시지를 출력하고 루프를 계속 진행.

### 5. 실행 구조
- `main()` 함수:
  - 두 개의 데몬 스레드 생성:
    - `process_c_events` / `process_e_events` 각각을 별도 스레드로 실행.
  - 스레드 시작 후 `join()`으로 메인 스레드를 유지.
  - `KeyboardInterrupt` 시에는 메시지만 출력하고 종료.
- 엔트리포인트:
  - `if __name__ == "__main__": main()` 블록을 추가하여
    - `python -m app.consumer` 또는 `python app/consumer.py` 로 직접 실행 가능하도록 구성.

---

## 2025-11-18 – Infra: users 컬렉션 및 인증 의존성 추가

### 1. Mongo users 컬렉션 준비
- 파일: `docker/mongo-init.js`
- 변경 사항:
  - `users` 컬렉션 자동 생성 로직 추가:
    - 컬렉션이 없을 경우 `db.createCollection("users")`.
  - 인덱스:
    - `db.users.createIndex({ email: 1 }, { unique: true })`  
      → 이메일 기준 유저 조회 및 중복 방지용 Unique Index.
- 효과:
  - 새 환경에서 Mongo 컨테이너가 처음 올라올 때,
    `sentencify.users` 컬렉션과 `email` 유니크 인덱스가 자동으로 준비되어,
    이후 회원 관리/인증 기능을 구현할 때 바로 사용할 수 있음.

### 2. API 인증 관련 라이브러리 의존성 추가
- 파일: `api/requirements.txt`
- 추가된 패키지:
  - `python-jose[cryptography]`
    - JWT 발급/검증용 라이브러리.
  - `passlib[bcrypt]`
    - 비밀번호 해싱/검증용 (bcrypt 스키마 사용).
  - `python-multipart`
    - FastAPI에서 form-data 기반 로그인/업로드 등을 처리할 때 필요한 의존성.
- 현재는 실제 인증/회원 엔드포인트는 구현하지 않았으며,
  - Phase1 이후 회원 관리 기능을 붙일 때 사용할 준비 단계로 패키지만 추가한 상태.

---

## 2025-11-18 – Backend: Implemented JWT Auth API (Ready for Frontend)

### 1. Auth 라우터 및 Mongo users 연동
- 파일: `api/app/auth.py`
- 주요 내용:
  - PyMongo 기반 `users` 컬렉션 헬퍼:
    - `get_mongo_users_collection()` → `sentencify.users` 컬렉션 반환.
  - 비밀번호 해싱/검증:
    - `passlib.context.CryptContext` (bcrypt) 사용.
    - `hash_password(password)`, `verify_password(plain, hashed)` 유틸 함수 정의.
  - JWT 토큰 생성:
    - `create_access_token(data, expires_delta)`:
      - 기본 만료 시간: `ACCESS_TOKEN_EXPIRE_HOURS` (환경변수, 기본 24시간).
      - `SECRET_KEY` 환경변수와 `HS256` 알고리즘으로 서명.
  - Pydantic 모델:
    - `SignupRequest`: `email: EmailStr`, `password: str`
    - `LoginRequest`: `email: EmailStr`, `password: str`
    - `TokenResponse`: `access_token`, `token_type="bearer"`

### 2. `/auth/signup` 엔드포인트
- 라우터: `auth_router.post("/signup")`
- 동작:
  - `SignupRequest` 수신 (`email`, `password`).
  - `users.find_one({"email": req.email})`로 중복 이메일 체크:
    - 이미 존재하면 HTTP 400 (`"Email already registered"`).
  - 신규 유저 문서 생성:
    - `email`
    - `password_hash` (bcrypt 해시)
    - `created_at` (UTC ISO 문자열)
  - `insert_one` 후 `{"id": <inserted_id>, "email": ...}` 형태로 응답.

### 3. `/auth/login` 엔드포인트
- 라우터: `auth_router.post("/login")`, `response_model=TokenResponse`
- 동작:
  - `LoginRequest` 수신 (`email`, `password`).
  - 해당 이메일 유저 조회:
    - 없으면 HTTP 400 (`"Invalid credentials"`).
  - bcrypt로 비밀번호 검증:
    - 실패 시 동일하게 HTTP 400 (`"Invalid credentials"`).
  - JWT Access Token 생성:
    - payload: `{"sub": email, "user_id": str(user["_id"])}`.
    - 만료: 기본 24시간(환경변수로 조정 가능).
  - 응답:
    - `{"access_token": "<JWT>", "token_type": "bearer"}`.

### 4. main.py에 Auth Router 등록
- 파일: `api/app/main.py`
- 변경 사항:
  - `from .auth import auth_router` import 추가.
  - 파일 하단에:
    ```python
    app.include_router(auth_router, prefix="/auth")
    ```
    를 추가하여 `/auth/signup`, `/auth/login` 경로가 메인 FastAPI 앱에 노출되도록 설정.
- 결과:
  - 프론트엔드는 `/auth/signup`, `/auth/login`를 통해
    - 회원 가입 / 로그인 + JWT 발급 플로우를 붙일 수 있는 상태가 되었음.
  - 현재는 보호 라우터/토큰 검증 의존성은 추가하지 않았으며,
    - 이후 필요 시 `Depends` 기반 JWT 검증 유틸을 같은 모듈에 확장 가능.

---

## 2025-11-18 – Frontend: Integrated Real Auth API (Login/Signup)

### 1. AuthContext에서 실제 /auth API 연동
- 파일: `frontend/src/auth/AuthContext.jsx`
- 변경 사항:
  - `../utils/api.js`의 axios 인스턴스(`api`)를 사용하도록 변경.
  - 로컬 스토리지 키:
    - 사용자 정보: `auth:user:v1`
    - 액세스 토큰: `auth:token:v1`
  - 초기화 로직:
    - 마운트 시 localStorage에서 user/token을 읽어 `user` 상태를 복원하고,
      토큰이 있으면 `api.defaults.headers.common.Authorization = "Bearer <token>"` 설정.

### 2. 로그인 / 회원가입 / 로그아웃 구현
- `login({ email, password })`:
  - `POST /auth/login` 호출 → `access_token` 수신.
  - `user = { email }` 상태로 세팅.
  - localStorage에 user/token 저장.
  - axios default header에 `Authorization: Bearer <token>` 설정.
- `signup({ email, password })`:
  - `POST /auth/signup` 호출.
  - 성공 시 `login({ email, password })`를 호출하여 자동 로그인 처리.
- `logout()`:
  - `user` 상태를 `null`로 초기화.
  - localStorage에서 user/token 키 제거.
  - axios default header에서 `Authorization` 제거.

### 3. 효과
- 프론트엔드에서 Mock Auth 대신 실제 FastAPI `/auth/signup`, `/auth/login` API를 사용하여 인증 플로우 구현.
- 이후 보호된 API를 호출할 때 Authorization 헤더를 자동으로 사용할 수 있는 기반이 준비됨.

---

## 2025-11-18 – Frontend UX: Auto-refresh Sidebar on save

### 1. 자동 저장 시 Sidebar 문서 목록 갱신 트리거
- 파일: `frontend/src/App.jsx`, `frontend/src/Sidebar.jsx`
- 변경 사항:
  - `App.jsx`:
    - 상태 추가:
      - `lastSnapshotTime` (최근 자동 저장/스냅샷 시간)
      - `refreshTrigger` (Sidebar 목록 갱신용 카운터)
      - `isSaving` (저장 중 표시용)
    - 자동 저장(useEffect) 로직 보완:
      - 텍스트 변경 시 400ms debounce 후 localStorage에 저장.
      - 저장 직후:
        - `lastSnapshotTime = Date.now()`
        - `refreshTrigger++`
        - `isSaving = false`
      - 효과: 실제 K 이벤트/스냅샷 성공 시점에 맞춰 이 부분만 조정하면, Sidebar가 자동으로 최신 목록을 가져오게 됨.
    - Sidebar에 `refreshTrigger` 전달:
      ```jsx
      <Sidebar
        userId={user?.id}
        refreshTrigger={refreshTrigger}
        ...
      />
      ```
  - `Sidebar.jsx`:
    - `refreshTrigger`를 props로 받아 `useEffect` 의존성에 추가:
      - `useEffect(..., [userId, refreshTrigger])`
      - 값이 바뀔 때마다 `GET /documents?user_id=...`를 다시 호출하여 문서 목록을 갱신.

### 2. 저장 상태 표시 UX
- 파일: `frontend/src/App.jsx`
- 변경 사항:
  - 에디터 제목 옆에 저장 상태 텍스트 추가:
    ```jsx
    <div className="flex items-center justify-between mb-3">
      <h1 className="text-xl font-semibold">에디터</h1>
      <span className="text-xs text-gray-500">
        {isSaving ? '저장 중...' : lastSnapshotTime ? '저장됨' : ''}
      </span>
    </div>
    ```
  - 텍스트 입력 직후에는 잠깐 `저장 중...`이 표시되고,
    자동 저장이 끝난 뒤에는 `저장됨`으로 상태가 바뀜.
- 효과:
  - 사용자가 문서를 편집했을 때 “어디까지 저장됐는지”를 직관적으로 파악할 수 있고,
  - Sidebar에도 자동으로 최신 문서 목록이 반영되어 저장 여부를 확인하기 쉬워짐.

---

## 2025-11-18 – Frontend UX: Create document + immediate Sidebar refresh

### 1. 새 글 생성 시 백엔드 문서 생성 연동
- 파일: `frontend/src/App.jsx`
- 변경 사항:
  - `handleNewDraft`를 async 함수로 변경.
  - 로직:
    - `api.post('/documents', { user_id: user.id })` 호출로 서버에 새 문서 생성 요청.
    - 응답의 `doc_id`를 현재 `docId`로 설정하고,
      - `text`는 빈 문자열,
      - selection/context/recommend 관련 상태는 초기화.
    - 실패 시에는 기존처럼 로컬에서만 `uuidv4()`로 docId를 생성해 fallback 처리.
  - 새 문서 생성 직후:
    - `setLastSnapshotTime(null)`로 저장 상태 초기화.
    - `setRefreshTrigger((v) => v + 1)` 호출로 Sidebar가 즉시 목록을 다시 불러오도록 트리거.

### 2. Sidebar 문서 목록 표시/하이라이팅 개선
- 파일: `frontend/src/Sidebar.jsx`
- 변경 사항:
  - props에 `selectedDocId` 추가:
    - 현재 선택된 문서의 `doc_id`를 받아 목록에서 하이라이팅에 사용.
  - 목록 렌더링:
    - 라벨 결정:
      - `label = (doc.preview_text && doc.preview_text.trim()) || '새 문서'`
      - preview가 비어 있으면 `"새 문서"`를 기본값으로 표시.
    - 선택된 문서 하이라이트:
      - `isActive = selectedDocId === doc.doc_id`
      - 활성 항목에 `bg-purple-50` 같은 배경색 클래스를 적용.
  - `App.jsx`에서 Sidebar 사용 시:
    - `selectedDocId={docId}`를 넘겨 현재 열려 있는 문서와 목록의 선택 상태를 동기화.

---

## 2025-11-18 – Infra: Refactored init scripts & Added Auto-init entrypoint

### 1. Qdrant 초기화 스크립트 구조 개편
- 파일 이동:
  - `api/init_qdrant.py` → `scripts/init_qdrant.py`
- 변경 사항:
  - 컨테이너 경로 기준으로 앱 모듈을 import할 수 있도록 상단에
    ```python
    import os
    import sys

    sys.path.append("/app")
    ```
    추가.
  - CSV 경로를 명시적으로 `/app/train_data.csv`로 고정:
    - `csv_path = "/app/train_data.csv"`
    - Dockerfile에서 해당 위치로 CSV를 복사하도록 맞춤.

### 2. API Dockerfile에서 스크립트/데이터 복사 및 EntryPoint 구성
- 파일: `api/Dockerfile`
- 변경 사항:
  - 빌드 컨텍스트를 루트(`.`)로 사용하기 위해 경로 조정:
    - `COPY api/requirements.txt .`
    - `COPY api/app ./app`
  - init 스크립트/데이터 파일 복사:
    - `COPY scripts /app/scripts`
    - `COPY api/train_data.csv /app/train_data.csv`
  - 엔트리포인트 스크립트 실행을 위한 설정:
    - `RUN chmod +x /app/scripts/entrypoint.sh`
    - `ENTRYPOINT ["/bin/bash", "/app/scripts/entrypoint.sh"]`

### 3. EntryPoint 스크립트 추가
- 파일: `scripts/entrypoint.sh`
- 내용 요약:
  ```bash
  #!/bin/bash
  set -e

  echo "Starting initialization..."
  python /app/scripts/init_qdrant.py || echo "Init skipped or failed"

  echo "Starting Server..."
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000
  ```
- 효과:
  - 컨테이너가 시작될 때마다 Qdrant 컬렉션 및 초기 데이터가 자동으로 준비되며,
    초기화에 실패해도 API 서버는 정상적으로 뜨도록 구성.

### 4. docker-compose에서 API 빌드 설정 변경
- 파일: `docker-compose.mini.yml`
- 변경 사항:
  - `api` 서비스의 `build` 설정을 다음과 같이 수정:
    ```yaml
    api:
      build:
        context: .
        dockerfile: api/Dockerfile
    ```
  - 이렇게 함으로써 루트 컨텍스트 기준으로 `api/`와 `scripts/`를 모두 Docker 빌드에 포함시킬 수 있게 됨.


---

## 2025-11-18 – Phase 1.5: Document Snapshot & Management Pipeline

### 1. Frontend – editor_document_snapshot Throttling 및 상태 관리
- 파일: (에디터/스냅샷 관련) `frontend/src/App.jsx` 및 관련 유틸
- 주요 로직:
  - 사용자가 에디터에 입력할 때마다 바로 스냅샷을 쏘지 않고,
    - **Debounce 2초**: 입력이 멈춘 뒤 2초가 지난 시점,
    - **Throttle 30초**: 최소 30초 간격으로만 전송,
    를 만족하는 경우에만 `editor_document_snapshot` 이벤트를 발생.
  - `lastSnapshotText` 상태를 두어,
    - 현재 텍스트와 이전에 보낸 스냅샷 텍스트가 동일할 경우에는 이벤트를 보내지 않도록 방어.

### 2. Backend – K 이벤트 Consumer (editor_document_snapshot → full_document_store)
- 파일: `api/app/consumer.py`
- 추가 함수: `process_k_events()`
- 동작:
  - Kafka 토픽 `editor_document_snapshot` 구독.
  - 메시지에서 `doc_id`, `full_text`(현재 문서 전체 텍스트), `user_id` 등을 읽어 MongoDB `full_document_store`에 반영.
  - **Case A – 기존 문서가 존재할 때 (Update)**:
    - `prev_text = existing.latest_full_text`
    - `curr_text = payload.full_text`
    - Diff Stub 계산:
      - `len_diff = abs(len(curr_text) - len(prev_text))`
      - `diff_ratio = len_diff / max(len(prev_text), 1)`
    - `update_one`으로 아래 필드 갱신:
      - `previous_full_text = prev_text`
      - `latest_full_text = curr_text`
      - `diff_ratio`
      - `last_synced_at` (현재 UTC ISO)
  - **Case B – 문서가 없을 때 (Insert)**:
    - `insert_one`으로 새 도큐먼트 생성:
      - `doc_id`, `user_id`(있을 경우), `latest_full_text = curr_text`
      - `previous_full_text = None`
      - `diff_ratio = 1.0`
      - `created_at`, `last_synced_at` (현재 UTC ISO)

### 3. Backend – 문서 관리용 API (`GET /documents`, `DELETE /documents/{doc_id}`)
- 파일: `api/app/main.py`
- `GET /documents`:
  - 쿼리 파라미터 `user_id`를 받아, MongoDB `sentencify.full_document_store`에서 해당 유저 문서 목록 조회.
  - `last_synced_at` 내림차순으로 정렬.
  - 응답 항목:
    - `doc_id`
    - `latest_full_text` (에디터 복원용)
    - `preview_text` (latest_full_text 앞 50자)
    - `last_synced_at` (ISO 문자열)
- `DELETE /documents/{doc_id}`:
  - 쿼리 파라미터 `user_id`와 path `doc_id`를 조건으로 `delete_one`.
  - 응답: `{ "deleted": <삭제된 문서 개수> }`

### 4. Frontend – Sidebar와 문서 API 연동
- 파일: `frontend/src/Sidebar.jsx`, `frontend/src/App.jsx`
- Sidebar:
  - `userId`를 prop으로 받아 마운트 시 `GET /documents?user_id=...` 호출.
  - 응답 받은 문서 리스트를 실제 목록으로 렌더링:
    - `preview_text`를 제목처럼 표시.
    - 각 항목 우측에 "삭제" 버튼 추가 → `DELETE /documents/{doc_id}?user_id=...` 호출 후 목록 갱신.
    - 항목 클릭 시 `onSelectDoc({ doc_id, text: latest_full_text })`로 상위(App)에 전달.
- App:
  - `handleSelectDocument(doc)` 핸들러 추가:
    - `doc.doc_id`를 현재 `docId`로 설정.
    - `doc.text`를 에디터의 `text`로 반영.
    - 선택/컨텍스트/추천 상태를 초기화하여 새 문서로 전환.
  - `Sidebar`를 `userId`와 `onSelectDoc`을 넘겨 사용하는 형태로 변경.

## 2025-11-19 – Phase 1.5 Step1 (Redis Schema F) 진행 중

### 1. Phase 1.5 착수
- Phase 1.5 Macro Context 단계 시작을 선언하고 Step 1 상태를 **In Progress**로 기록.
- `docker-compose.mini.yml`에 `redis` 서비스 존재 여부, `api/requirements.txt`에 `redis` 패키지 포함 여부를 검증(변경 사항 없음).

### 2. Schema F & Redis 클라이언트
- 파일: `api/app/schemas/macro.py`, `api/app/redis/client.py`, `api/app/redis/__init__.py`, `api/app/schemas/__init__.py`
  - Schema F(`DocumentContextCache`) 정의: `doc_id`, `macro_topic`, `macro_category_hint`, `cache_hit_count`, `last_updated`, `valid_until`, `invalidated_by_diff`, `diff_ratio`.
  - Redis Async 클라이언트(`redis.asyncio`) 추가: `get_redis_client()`, `set_macro_context()`, `get_macro_context()` 구현 및 공용 키 프리픽스 적용.

### 3. Standalone 테스트 & Phase1.5 테스트 리스트
- 파일: `scripts/test_step1_redis.py`
  - 루트 경로에서 실행 가능한 독립 검증 스크립트. 로컬 Redis 접속 → Schema F Dummy 작성 → 저장 후 재로딩 검증.
- 파일: `docs/phase1.5_test_lists.md`
  - Phase 1.5 테스트 항목 시작 (`Redis Connection Test`, `Schema F Validation`).

---
