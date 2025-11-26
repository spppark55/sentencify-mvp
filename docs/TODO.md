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

