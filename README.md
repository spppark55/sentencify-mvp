### 1. Prerequisites
* **Docker Desktop**이 설치되어 있어야 합니다.

### 2. Setup Data
* 제공된 `data` 폴더를 프로젝트 루트 디렉토리에 위치시켜 주세요.

### 3. Run Application
OS 환경에 맞는 스크립트를 실행해 주세요.

* **Windows** (약 10분 소요)
  ```powershell
  ./run_local_docker.ps1
  ```
* **macOS / Linux** (약 5분 소요)
  ```Bash
  ./run_local_docker.sh
  ```
  
### 4. 사용 시작
API 서버 로그에 다음 메시지가 출력되면 사용이 가능합니다.

* Application startup complete.
  
### 5. Access Services
| Service      | URL                     | Description              |
|-------------|-------------------------|--------------------------|
| Frontend    | http://localhost:5173    | 문장 교정 에디터 메인     |
| Dashboard   | http://localhost:8501    | 데이터 모니터링 대시보드  |
| Backend Docs| http://localhost:8000/docs | API 명세서 (Swagger) |
