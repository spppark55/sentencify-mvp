이 로드맵은 개발팀 간의 의존성(Dependency)을 최소화하고, "API 개발 → 테스트 데이터 준비 → P_vec 튜닝 → 전체 체인 통합"의 자연스러운 흐름을 따릅니다.

---

## 🗺️ Sentencify Phase 1: 실행 순서 기반 로드맵 (v1.1)

Phase 1의 목표는 **(1) 실시간 추천 (`P_rule`+`P_vec`)**과 **(2) 데이터 수집 체인 (`A-B-C-D-E`)**을 완성하는 것입니다.

### 📍 Step 0: 개발 착수 (Foundation)

모든 개발의 전제 조건이며, 병목 현상을 막기 위해 가장 먼저 완료되어야 합니다.

1. **인프라 구축 (WBS TODO 12)**
    - `docker-compose.mini.yml`을 완성하고 실행합니다.
    - **핵심 서비스 5개:** `FastAPI`, `Kafka`, `MongoDB` (D 저장용), `Qdrant` (E 저장용), `Redis` (LLM 캐시용).
2. **One-Way Door 결정 (WBS TODO 10, 3)**
    - **임베딩 모델 확정:** `P_vec` 계산에 사용할 `embedding_v1` 모델(예: `all-MiniLM-L6-v2`)을 최종 선택합니다. (이 결정이 Step 3의 작업을 정의합니다)
    - **LLM 엔드포인트 확정:** `B` 이벤트 컨슈머가 호출할 `Paraphrasing LLM` (예: OpenAI API) 엔드포인트를 확정합니다.

### 📍 Step 1: 실시간 API 핵심 구현 (API-Side)

API 서버가 최소 기능으로 동작하고, 모든 후속 작업(컨슈머, FE)의 기준점을 제공합니다.

1. **API Contract & Logic (TODO 1, 2)**
    - `POST /recommend` 엔드포인트와 Pydantic 스키마(`Request`/`Response`)를 정의합니다.
    - `context_full`, `context_hash` 생성 로직을 구현합니다.
2. **추천 엔진 스텁(Stub) 구현 (TODO 2)**
    - `P_rule` (규칙 엔진): 하드코딩된 기본값(예: `{"email": 0.5}`)을 반환합니다.
    - `P_vec` (벡터 검색): Qdrant에 빈 값을 검색하거나 기본값을 반환합니다.
3. **핵심 ID 생성 및 반환 (TODO 2)**
    - `insert_id` (UUID)와 `recommend_session_id` (UUID)를 생성하여 `RecommendResponse`에 포함시킵니다.
4. **A/I/E 이벤트 발행 (TODO 2, 4)**
    - FE에 `200 OK` 응답을 반환한 직후, **3개 이벤트(A, I, E)를 Kafka로 `produce`*합니다. (Fire-and-Forget)

> [Step 1 완료 기준]POST /recommend 호출 시, (1) 가짜 추천 값과 (2) insert_id, session_id가 반환되며, (3) Kafka 토픽에 A, I, E 이벤트가 쌓입니다.
> 

### 📍 Step 2: FE-BE 계약 확정 (The Contract)

Step 1이 완료되는 즉시 FE팀과 백엔드팀이 이 계약을 확정하여 병렬 개발을 시작합니다.

1. **API 스키마 고정 (TODO 1)**
    - Step 1에서 만든 `RecommendRequest` / `RecommendResponse` 스키마를 API 명세서(Swagger/Notion)로 확정합니다.
2. **FE 역할 정의 (명세서 4.3)**
    - FE는 다음 3가지 역할을 수행하기로 확정합니다.
        1. `/recommend` 응답에서 `insert_id`와 `recommend_session_id`를 FE 내부 상태에 저장.
        2. '실행' 시, 저장된 2개 ID를 포함하여 `B (editor_run_paraphrasing)` 이벤트를 Kafka로 발행.
        3. '선택' 시, 저장된 2개 ID와 `selected_option_index` 등을 포함하여 `C (editor_selected_paraphrasing)` 이벤트를 Kafka로 발행.

### 📍 Step 3: 테스트 데이터 준비 및 P_vec 고도화

API가 동작하는 동안, `P_vec`의 정확도를 높이기 위한 데이터를 준비하고 로직을 튜닝합니다.

1. **Synthetic DB 생성/적재 (WBS TODO 10)**
    - `Step 0`에서 확정한 `embedding_v1` 모델로 가상 데이터(Synthetic DB)의 임베딩을 생성합니다.
    - 이 벡터 데이터(임베딩, `embedding_version: "v1.0"`)를 `Qdrant`에 미리 적재합니다. (명세서 2.3)
2. **`P_vec` 로직 고도화 (WBS TODO 2)**
    - `Step 1`에서 만든 `P_vec` 스텁(Stub)을 실제 `Qdrant` 검색 로직으로 교체합니다.
    - `Synthetic DB`를 기반으로 `P_vec` 점수 계산 로직을 튜닝합니다.

### 📍 Step 4: 비동기 컨슈머 구현 (Data Chain)

`Step 2`의 계약에 따라 FE와 API가 발행할 이벤트를 처리하는 백엔드 로직을 구현합니다.

1. **`E` 컨슈머 구현 (WBS TODO 4)**
    - `E (context_block)` 토픽을 구독(subscribe)하여 `Qdrant`에 `upsert`합니다. (PK: `context_hash`)
2. **`B` 컨슈머 구현 (WBS TODO 3)**
    - `B (editor_run_paraphrasing)` 토픽을 구독합니다.
    - `Step 0`에서 확정한 `Paraphrasing LLM`을 호출하고, `Redis`에 응답을 캐시합니다.
3. **`C` 컨슈머 구현 (WBS TODO 8)**
    - `C (editor_selected_paraphrasing)` 토픽을 구독합니다.
    - `C.was_accepted == true`인 경우, `MongoDB`에 `D(correction_history)` 문서를 생성(insert)합니다.
    - (선택적) 생성된 `D._id`를 `C.correction_history_id` 필드에 넣어 다시 Kafka `C-log` 토픽에 발행하거나 BigQuery에 저장합니다. (명세서 4.3 Rule 3)

### 📍 Step 5: E2E 통합 및 Phase 1 완료 (DoD Check)

모든 컴포넌트(FE, API, Consumers)를 통합하고, Phase 1의 공식 완료 조건을 검증합니다.

1. **FE-BE-Consumer 전체 연동**
    - `Step 2`의 계약대로 FE 개발을 완료하고 전체 시스템을 통합합니다.
2. **Phase 1 완료 기준 (7개) 검증 (Definition of Done)**
    - 사용자 시나리오(드래그 → 실행 → 선택)를 1회 수행한 뒤, 아래 7개 항목이 모두 성공하는지 검증합니다.
    - ✅ **`/recommend` API 300ms 내 응답** (명세서 2.4)
    - ✅ **`A/I/E` 이벤트가 모두 Kafka에 정상 발행**
    - ✅ **`E` Consumer가 Qdrant에 context 저장** (WBS TODO 4)
    - ✅ **`B` Consumer가 LLM 호출 → Redis 저장** (WBS TODO 3)
    - ✅ **`C` Consumer가 D(correction_history) 생성** (in MongoDB) (WBS TODO 8)
    - ✅ **`FE`가 `insert_id`/`session_id`를 정상 전달** (B, C 이벤트 Payload 검증)
    - ✅ **`A→B→C→D→E` 전체 체인이 한 세션에서 끊김 없이 생성됨** (명세서 2.4)

> [Phase 1 완료]
위 7개 검증 항목이 모두 통과되면, Phase 1의 공식 목표("실시간 추천 + Hooks 수집")가 달성됩니다.
>