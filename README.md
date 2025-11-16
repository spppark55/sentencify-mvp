# yeardream_final

먼저 어디까지 된 상태인지부터 짧게 정리할게요.

* `docker-compose.mini.yml` ✅

  * `api / kafka / mongo / qdrant / redis` 5개 컨테이너 전부 올라가는 상태
* `api` 이미지 ✅

  * `Dockerfile`, `requirements.txt`, `app/main.py` 기준으로 빌드되고 컨테이너에서 실행 가능
* `.devcontainer/devcontainer.json` ✅

  * VS Code에서 “Reopen in Container” 하면 `api` 컨테이너 안에서 바로 개발 가능

이제 다른 팀원이 그대로 따라 쓸 수 있게 **README 내용**이랑 **커밋 메시지**를 정리해 줄게요.

---

## 1. README.md 내용 (그대로 붙여넣기용)

원래 내용 지우고 아래를 전체 복사해서 `README.md`에 넣으면 됩니다.

````markdown
# Sentencify MVP

Sentencify Phase 1(실시간 추천 + 데이터 수집)을 빠르게 개발하기 위한 **로컬 MSA 개발 환경**입니다.  
모든 서비스는 Docker Compose + VS Code Dev Container로 구동합니다.

---

## 📦 구성 서비스

`docker-compose.mini.yml` 기준 서비스 구성은 다음과 같습니다.

- `api` : FastAPI 기반 추천 API 서버 (`POST /recommend`)
- `kafka` : A / B / C / E / I 이벤트를 처리하는 메시지 큐
- `mongo` : `D (correction_history)` 저장용 메인 DB
- `qdrant` : `E (context_block)` 벡터를 저장하는 Vector DB
- `redis` : LLM 응답 캐시 (B 이벤트용)

모든 서비스는 `sentencify-net` 브리지 네트워크에서 **서비스 이름으로 서로 통신**합니다.

---

## 🔧 사전 준비 사항

팀원이 이 레포를 처음 가져와 실행할 때 필요한 것들입니다.

1. **Git**
2. **Docker Desktop**
3. **VS Code**
4. **VS Code 확장**
   - Dev Containers (ms-vscode-remote.remote-containers)

---

## 🏁 1단계: 레포 클론

```bash
git clone https://github.com/<ORG_OR_USER>/sentencify-mvp.git
cd sentencify-mvp
````

> `sentencify-mvp` 폴더가 프로젝트 루트입니다.

---

## 🚀 2단계: Docker Compose로 인프라 올리기

프로젝트 루트에서 다음 명령을 실행합니다.

```bash
docker compose -f docker-compose.mini.yml up -d --build
```

이 명령으로 아래 5개 서비스가 한 번에 올라갑니다.

* `sentencify-mvp-api-1`
* `sentencify-mvp-kafka-1`
* `sentencify-mvp-mongo-1`
* `sentencify-mvp-qdrant-1`
* `sentencify-mvp-redis-1`

상태 확인:

```bash
docker ps
```

중지/정리할 때:

```bash
docker compose -f docker-compose.mini.yml down
```

---

## 💻 3단계: VS Code Dev Container에서 개발하기

1. VS Code에서 **프로젝트 루트(`sentencify-mvp`)를 폴더로 열기**
2. 명령 팔레트 열기

   * `Cmd + Shift + P` (Mac)
   * `Ctrl + Shift + P` (Windows)
3. `Dev Containers: Reopen in Container` 실행
4. 잠시 기다리면 VS Code가 `api` 컨테이너 안으로 붙습니다.

> 이 상태에서는 **로컬에서 코드를 수정하듯이** 작업해도, 실제 실행은 컨테이너 안의 Python + 라이브러리를 사용하게 됩니다.
> `.devcontainer/devcontainer.json`이 레포에 포함되어 있기 때문에, 팀원도 그대로 `Reopen in Container`만 하면 동일한 환경을 얻습니다.

---

## 🧪 4단계: FastAPI 서버 실행

Dev Container로 붙은 상태에서 터미널을 열고:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

브라우저에서 다음 주소로 접속하면 Swagger가 열립니다.

* [http://localhost:8000/docs](http://localhost:8000/docs)

`POST /recommend` 엔드포인트에 예시 payload를 넣고 호출해보면:

* `insert_id`
* `recommend_session_id`
* 더미 `reco_options` 리스트

가 반환되면 Phase 1 **Step 1 (실시간 API 최소 기능)** 이 성공한 것입니다.

---

## 📂 디렉터리 구조(요약)

```text
sentencify-mvp/
  ├─ api/
  │   ├─ app/
  │   │   └─ main.py          # FastAPI 엔트리포인트
  │   ├─ requirements.txt     # 컨테이너에서 설치하는 Python 패키지
  │   └─ Dockerfile           # api 서비스용 Dockerfile
  ├─ .devcontainer/
  │   └─ devcontainer.json    # VS Code Dev Container 설정
  ├─ docker-compose.mini.yml  # 로컬 개발용 MSA 인프라 정의
  └─ README.md
```

---

## 📝 devcontainer 관리 가이드

* `.devcontainer/devcontainer.json`은 **레포에 포함(커밋)** 합니다.

  * 이유: 모든 팀원이 동일한 개발 환경을 자동으로 재현할 수 있어야 하기 때문입니다.
* 일반적으로 `.gitignore`에 넣지 않습니다.
* 설정을 바꾸고 싶으면 PR을 통해 팀 차원에서 논의 후 수정하는 것을 권장합니다.

---

## ✅ 현재 Phase 1 로드맵 기준 상태

이 레포를 받은 팀원이 위 가이드대로 실행하면:

* **Step 0 – 인프라 구축** ✅
* **Step 1 – 최소 추천 API 스켈레톤 (`/recommend`)** ✅
* Dev Container 기반의 공통 개발 환경 ✅

다음 단계는:

* `P_rule`, `P_vec` 실제 로직 구현
* Kafka Producer/Consumer 코드 추가 (A/I/E/B/C 처리)
* FE에서 `/recommend` + B/C 이벤트 연동

입니다.

````

---

