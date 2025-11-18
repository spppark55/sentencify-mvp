# Sentencify Phase 1 – Current Progress Log

> 진행 상황과 코드/환경 변경사항을 **시간순으로 누적 기록**하는 문서입니다.  
> 새 작업을 할 때마다 이 파일에 아래 포맷으로 항목을 추가합니다.

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

