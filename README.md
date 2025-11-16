# yeardream_final

📘 Sentencify MVP – 로컬 MSA 개발 환경

Sentencify Phase 1(실시간 추천 + 데이터 수집)을 개발하기 위한 로컬 MSA + DevContainer 기반 환경입니다.

FastAPI API 서버는 VS Code DevContainer 안에서 개발하고,
Kafka / Mongo / Qdrant / Redis 등 인프라는 Docker Compose로 실행합니다.

🚀 1. 사전 준비

팀원이 이 레포를 처음 가져올 때 필요한 것:

Git

Docker Desktop

VS Code

VS Code 확장

Dev Containers (ms-vscode-remote.remote-containers)

🚀 2. 레포 클론
git clone https://github.com/<USER_OR_ORG>/sentencify-mvp.git
cd sentencify-mvp

🚀 3. MSA 인프라 실행 (Docker Compose)

루트 폴더에서 실행:

docker compose -f docker-compose.mini.yml up -d --build


이 명령으로 다음 5개 컨테이너가 실행됩니다:

api (FastAPI – DevContainer에서 개발용)

kafka

mongo

qdrant

redis

상태 확인:

docker ps


중지:

docker compose -f docker-compose.mini.yml down

🧩 4. FastAPI 개발 (VS Code Dev Container)

FastAPI 코드는 DevContainer 내부에서 실행해야 함
(로컬 Python 환경을 사용하지 않음)

실행 방법

VSCode에서 sentencify-mvp 폴더를 열기

명령 팔레트 열기

macOS: Cmd + Shift + P

Windows: Ctrl + Shift + P

Dev Containers: Reopen in Container 선택

VS Code가 자동으로 API 컨테이너 환경으로 들어감

🧪 5. FastAPI 서버 실행

DevContainer 안에서 터미널을 열고:

uvicorn app.main:app --host 0.0.0.0 --port 8000


브라우저에서 접속:

👉 http://localhost:8000/docs

정상적으로 보이면 다음 값이 응답됩니다:

insert_id

recommend_session_id

더미 reco_options 리스트

➡️ 이것이 Phase 1 Step 1 “API 최소 기능” 성공 기준입니다.

📁 디렉터리 구조
sentencify-mvp/
├─ api/
│   ├─ app/
│   │   └─ main.py
│   ├─ requirements.txt
│   └─ Dockerfile
├─ .devcontainer/
│   └─ devcontainer.json
├─ docker-compose.mini.yml
└─ README.md

📝 DevContainer 관리 규칙

.devcontainer/devcontainer.json 레포에 포함(커밋) 해야 함

이유: 팀원이 Reopen in Container만 하면 동일한 개발 환경을 자동 복원

일반적으로 .gitignore에 넣지 않음

🎯 Phase 1 진행 상황 요약
✔ 현재 이 레포로 가능한 것

Step 0: MSA 인프라 구축 완료

Step 1: FastAPI 기본 스켈레톤 동작

개발 환경 자동화(DevContainer) 완성

🔜 다음 해야 할 일

P_rule / P_vec 실제 로직 구현

Kafka Producer/Consumer 코드 추가

FE와 B/C 이벤트 스키마 확정 및 연동

📄 기술 로드맵

긴 Phase 1 로드맵(기술 아키텍처, Step 0~5)은 별도 문서로 분리되었습니다.

👉 docs/phase1-roadmap.md (추가 예정)