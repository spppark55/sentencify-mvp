
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

* 인프라 구축
  (FastAPI, FE, Kafka, MongoDB, Qdrant, Redis 통합 실행)
* FastAPI 최소 스켈레톤 (`POST /recommend`)

### 필요 작업 (진행 예정)

1. **API 고도화**

   * `P_rule`, `P_vec` 추천 로직 구현
   * Kafka Producer 로직(A/I/E 이벤트) 추가

2. **FE ↔ BE 계약 확정**

   * FE가 `/recommend` API 호출하도록 변경
   * B/C 이벤트를 통해 실행/선택 로그 발행

3. **Vector DB 준비**

   * Synthetic DB 생성
   * Qdrant에 임베딩 적재

4. **비동기 컨슈머 구현**

   * B, C, E 이벤트 처리 컨슈머 개발

Phase 1의 공식 완료 기준(DoD)은 phase1-roadmap.md 문서를 참고합니다.

---