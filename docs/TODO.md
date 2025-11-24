# Sentencify MVP - Remaining Tasks (TODO)

> **Goal:** Phase 3 (Personalization) 완성 및 MLOps 파이프라인 (Prefect) 구축.
> **Strategy:** 실제 데이터(OpenAI API, 기업 데이터)를 활용한 고품질 시뮬레이션과 자동화된 데이터 휠(Data Wheel) 구현.

---

## 1. 🧹 환경 정리 및 최적화 (Cleanup)
- [ ] **Streamlit 비활성화:** `docker-compose.mini.yml`에서 `dashboard` 서비스를 주석 처리하여 리소스 확보 (삭제 X).
- [ ] **README 정리:** ELK 스택 중심의 운영 가이드로 개편.

## 2. ⚙️ MLOps 인프라 구축 (Prefect)
- [ ] **Prefect 구성:**
    - `docker-compose.mini.yml`에 Prefect Server/Worker 추가 (또는 로컬 라이브러리 활용).
    - 기존 파이썬 스크립트(`etl_service.py` 등)를 Prefect `@task`, `@flow`로 래핑.

## 3. 🛠️ 데이터 자산화 (Data Preparation)
- [ ] **Context Pool 로더:**
    - `api/test_data.csv` (New Data)를 로드하여 시뮬레이터의 입력 문장(Input Sentence)으로 활용.
- [ ] **Prompt Pool 로더:**
    - 기업 데이터(D)에서 `user_prompt`가 존재하는 행만 추출.
    - 자주 사용되는 요청 스타일(예: "정중하게", "요약해줘")을 말뭉치(Corpus)로 변환하여 시뮬레이터의 `style_request`로 활용.

## 4. 🎭 리얼 월드 시뮬레이션 (Real-World Traffic Generation)
- [ ] **`scripts/generate_persona_traffic.py` 작성:**
    - **10 Personas:** Scholar, Socializer, Marketer 등 10가지 유저 타입 정의.
    - **Real API Call:** B(실행) 단계에서 실제로 **OpenAI API**를 호출하여 교정 결과(`candidates`) 생성.
    - **Decision Logic:** 페르소나별 취향(Category, Tone)에 따라 생성된 후보 중 하나를 선택(C)하거나 이탈.
    - **Output:** 실제 LLM 응답이 포함된 고품질 A/B/C 로그 MongoDB 적재.

## 5. ⛓️ Prefect 자동화 파이프라인 (The Data Wheel)
다음 작업들이 순차적/의존적으로 실행되도록 Prefect Flow 구현:
1.  **Simulate:** 위 4번 트래픽 생성기 실행.
2.  **ETL (H):** Raw Log → `training_examples` 생성.
3.  **Sync (ES):** `training_examples` → Elasticsearch `sentencify-golden-*` 인덱스 동기화.
4.  **Profiling (G):** 유저별 `context_embedding` 평균 -> `user_embedding_v1` 생성.
5.  **Clustering (J):** K-Means 알고리즘 수행 -> `cluster_id` 부여 및 `cluster_profile` 생성 -> **Redis 캐싱**.
6.  **Vector DB Re-indexing:** `test_data.csv`에서 유입된 새로운 문맥(E)에 대해 Qdrant 인덱스 최적화 수행.

## 6. 🚀 API 적용 (Phase 3 Completion)
- [ ] **Personalization Logic:**
    - `/recommend` API 수정.
    - Redis에서 `user_profile`, `cluster_profile` 조회.
    - $P_{user}$ (유저 유사도), $P_{cluster}$ (군집 유사도) 계산 및 $P_{final}$ 반영.
