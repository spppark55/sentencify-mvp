# Sentencify MVP Roadmap & TODO (v2.4)

> **Update (2025-11-25):** 
> - **Phase 2.5 (ELK):** Streamlit을 폐기하고 ELK Stack으로 관제/분석 일원화 진행 중.
> - **Phase 3 (Personalization):** `Airflow` 대신 경량화된 `Prefect` 도입 및 기업 데이터(`user_prompt`) 기반의 정교한 시뮬레이터 구축 예정.

---

## 0. 📊 주요 변경 및 구체화 리포트 (v2.4)

초기 계획 대비 아키텍처 및 운영 전략이 다음과 같이 구체화되었습니다.

### 1. Monitoring Architecture: Streamlit → ELK Stack (Phase 2.5)
*   **변경 전:** `Streamlit` 컨테이너가 MongoDB를 직접 폴링하여 관제.
*   **변경 후:** 
    *   `Streamlit`은 디버깅 후 **비활성화(폐기)**.
    *   `Logstash`가 Kafka(Raw Log)와 MongoDB(Golden Data)를 병렬 구독 → `Elasticsearch` 적재 → `Kibana` 시각화.
*   **Status:** `docker-compose.elk.yml` 구성 완료, 동기화 스크립트(`sync_golden_to_es.py`) 구현 완료.

### 2. Pipeline Tool: Airflow → Prefect (Phase 3)
*   **변경 전:** `Airflow` + `BigQuery`의 무거운 ELT.
*   **변경 후:**
    *   **MVP/Current:** Python Script + MongoDB Aggregation.
    *   **Next (Phase 3):** 유연하고 가벼운 **`Prefect`**를 도입하여 **Simulation → ETL → Training → Deploy**의 Data Wheel 자동화.

### 3. Corporate Data Utilization Strategy
*   **Context Pool:** 기업 데이터에서 실제 문맥 추출.
*   **Prompt Pool:** `D.user_prompt`(자연어 요청)를 추출하여 "정중하게", "요약해줘" 등의 **Real User Style**을 시뮬레이터에 주입.
*   **Schema Mapping:** 기업 로그(`maintenance`, `llm_name` 등)를 시스템 스키마(`intensity`, `model_version`)로 정규화하여 매핑.

### 4. 🏗️ Redis Data Store Status (Current Architecture)

현재 아키텍처상 Redis는 **Phase 1.5(Macro), Phase 2(User Profile), Phase 3(Cluster Profile)**의 핵심 캐시 레이어로 사용됩니다.

*   **✅ Phase 1.5: Macro Context Cache (구현됨)**
    *   **Schema:** **F (DocumentContextCache)**
    *   **Key Pattern:** `macro_context:{doc_id}`
    *   **Content:** LLM이 분석한 문서의 거시적 정보.
        *   `macro_topic`: 문서 요약 주제.
        *   `macro_category_hint`: `thesis`, `email` 등 카테고리 힌트.
        *   `valid_until`: TTL 만료 시각 (기본 1시간).
    *   **Status:** `api/app/schemas/macro.py`, `api/app/redis/client.py`에 구현 완료.

*   **✅ Phase 1: LLM Response Cache (구현됨)**
    *   **Key Pattern:** `llm:para:{hash}`
    *   **Content:** LLM(`gpt-4.1-nano` 등)의 응답 텍스트 리스트 (비용 절감용).
    *   **Status:** `api/app/main.py`, `api/app/redis/client.py`에 구현 완료.

*   **🚧 Phase 2: User Profile Cache (구현 예정/진행중)**
    *   **Schema:** **G (UserProfile)**
    *   **Key Pattern:** `user_profile:{user_id}` (예상)
    *   **Content:** 사용자의 개인화된 선호도 정보.
        *   `preferred_category_vector`: 선호 카테고리 벡터.
        *   `preferred_strength_vector`: 선호 강도 벡터.
        *   `user_embedding_v1`: 사용자 행동 임베딩.
    *   **Status:** `docs/아키텍쳐2-4.md`에 명시되어 있으나, `api/app/redis/client.py`에는 아직 해당 메서드(`set_user_profile` 등)가 구현되지 않았습니다. (Phase 3 진입 시 구현 필요)

*   **📅 Phase 3: Cluster Profile Cache (계획 단계)**
    *   **Schema:** **J (ClusterProfile)**
    *   **Key Pattern:** `cluster_profile:{cluster_id}`
    *   **Content:** 유사 사용자 그룹의 공통 선호도.
    *   **Status:** 아키텍처 설계상 존재하며, Phase 3 Personalization 구현 시 추가될 예정입니다.

---

## 1. [Phase 3] Corporate Data Mapping Plan (Schema Definition)

> **Goal:** `docs/기업명세.md`의 Raw Data를 시스템의 Standard Schema(B/C/D)로 변환하기 위한 매핑 규칙 수립.

### Mapping Table: `Corporate Log` → `Sentencify Event`

| Target Field (Sentencify) | Source Field (Corporate) | Transformation Logic |
| :--- | :--- | :--- |
| **Common** | | |
| `user_id` | `distinct_id` | (그대로 사용) |
| `created_at` | `time` | Unix Timestamp(sec) → ISO 8601 DateTime 변환 |
| **B/C Event** | | (`event_editor_run...`, `event_editor_selected...`) |
| `target_intensity` | `maintenance` | `weak`, `moderate`, `strong` (값 매핑 확인 필요) |
| `target_category` | `field` | `thesis`, `email` 등 (값 매핑 확인 필요) |
| `target_language` | `target_language` | (그대로 사용) |
| `model_version` | `llm_name` | 예: `gpt-4` → `gpt-4.1-nano` (버전 정규화) |
| `paraphrase_llm_provider`| `llm_provider` | (신규 필드 추가 고려) |
| `doc_id` | (None) | **Issue:** 기업 로그에 `doc_id` 부재 시 UUID 신규 발급 또는 Session 단위로 묶음 처리 필요. |
| **D (Correction History)** | | |
| `user_prompt` | `user_prompt` (추정) | 기업 데이터 내 별도 필드 확인 필요 (Phase 4 핵심) |

- [ ] **Import Script 작성:** 위 매핑 테이블을 구현한 `scripts/import_corporate_logs.py` 작성.

## 2. [Phase 3] MLOps & Simulation (Prefect)

> **Goal:** Prefect 기반의 자동화된 Data Wheel 구축.

- [ ] **Prefect 인프라:** `docker-compose.mini.yml`에 Prefect Server/Worker 추가.
- [ ] **Prompt Pool Loader:** 기업 데이터에서 `user_prompt` 추출하여 `prompts.json` 구축.
- [ ] **Persona Simulator (`scripts/generate_persona_traffic.py`):**
    - 10가지 페르소나 정의.
    - Prompt Pool을 활용한 Real API Call 수행.
- [ ] **Prefect Flow 구현:** `Simulate` → `ETL(Mongo)` → `Sync(ES)` → `Profile(Redis)` 자동화.

## 3. [Phase 3] Personalization API

- [ ] **API Logic Update:**
    - `/recommend`에서 `user_id`로 Redis `user_profile` 조회.
    - $P_{user}$ (개인화 점수) 계산 로직 적용.

## 4. [Phase 2.5] ELK Stack Integration (진행 중)

> **Goal:** Streamlit 제거 및 Kibana 단일 대시보드 체계 확립. (Priority: Low)

- [ ] **Streamlit 비활성화:** `docker-compose.mini.yml`에서 `dashboard` 서비스 주석 처리.
- [ ] **Kibana Dashboard 구성:**
    - **Ops:** `sentencify-logs-*` 기반 실시간 로그/에러 모니터링.
    - **Biz:** `sentencify-golden-*` 기반 Funnel, Retention, ROI 지표 시각화.
- [ ] **README 업데이트:** ELK 중심의 운영 가이드로 문서 현행화.
