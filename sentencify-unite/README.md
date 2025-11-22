Sentencify MVP: KoBERT & Gemini Integration
이 프로젝트는 사용자가 입력한 문장의 문맥을 파악하여 최적의 교정 옵션을 제안하는 AI 기반 문장 교정 서비스의 MVP 버전입니다.
🌟 주요 기능 (Phase 1 MVP)
1. 문맥 기반 형식 추천 (Hybrid Analysis):
   KoBERT (P_rule): 문장의 문법적, 어조적 특성을 분석하여 문서 형식(논문, 기사, 이메일 등)을 분류합니다.
   Vector Search (P_vec): 입력 문장과 유사한 문맥을 가진 과거 데이터를 검색하여 형식을 추론합니다.
   두 모델의 결과를 융합하여 최적의 카테고리를 제안합니다.
2. AI 자동 교정 (Gemini 1.5 Flash):
   분석된 문맥 태그와 사용자 선호도(강도, 스타일)를 바탕으로 Google Gemini 1.5 Flash 모델이 3가지 교정안을 생성합니다.
   Mock 데이터가 아닌 실제 AI가 생성한 문장을 제공합니다.
3. 실시간 연동 시스템:
   React 프론트엔드와 FastAPI 백엔드가 유기적으로 연결되어 드래그 앤 드롭 시 실시간으로 분석 및 교정이 이루어집니다.
   Kafka 타임아웃 방지 로직이 적용되어 안정적인 응답 속도를 보장합니다.
🛠️설치 및 실행 가이드
이 프로젝트를 실행하기 위해서는 Python (Backend) 및 Node.js (Frontend) 환경이 필요합니다.
1. 환경 변수 설정 (필수)Gemini API 사용을 위해 API 키 설정이 필요합니다. 터미널에서 다음 명령어를 실행하세요.
Windows (CMD):
   set GEMINI_API_KEY=your_actual_api_key_here
macOS / Linux:
   export GEMINI_API_KEY=your_actual_api_key_here
   ⚠️ 주의: API 키 값에 큰따옴표(")를 포함하지 마세요.
2. 백엔드 (FastAPI) 실행
   sentencify-unite 루트 폴더에서 다음 명령어를 실행합니다.
   # 필요한 라이브러리 설치
   pip install -r requirements.txt

   # 서버 실행 (8000번 포트)
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   - 서버가 정상 실행되면 http://localhost:8000/docs에서 API 문서를 확인할 수 있습니다.
3. 프론트엔드 (React/Vite) 실행
   sentencify-unite/frontend 폴더로 이동하여 실행합니다.
      cd frontend

      # 의존성 설치
      npm install

      # 개발 서버 실행
      npm run dev
      - 브라우저에서 http://localhost:5173으로 접속합니다.
🧪 테스트 방법
1. 웹 페이지(http://localhost:5173)에 접속합니다.
2. 에디터에 교정하고 싶은 문장을 입력합니다.
   - 예시: "레알마드리드는 리버풀전에서 졸전 끝에 석패하여 사람들에게 충격을 안겼다"
3. 해당 문장을 마우스로 드래그합니다.
   - 우측 패널의 '카테고리'가 자동으로 변경되는지 확인합니다 (실험 후 수정 필요할듯).
   - 하단 Debug Panel에 recoOptions 데이터가 들어오는지 확인합니다.
4. "실행 (교정)" 버튼을 클릭합니다.
   - 에디터의 문장이 AI가 제안한 문장으로 자연스럽게 교체되는지 확인합니다.
📂 폴더 구조
   - api/: FastAPI 백엔드 소스 코드
      - app/models/: AI 모델 로직 (KoBERT, Vector, Gemini)
      - main.py: 메인 서버 엔트리 포인트
   - frontend/: React 프론트엔드 소스 코드
   - data/: 데이터 및 모델 파일 저장소
⚠️ 주의 사항
- Kafka 연결: 현재 로컬 개발 환경에서는 Kafka 서버가 없어도 작동하도록 비동기 처리가 되어 있습니다. (KafkaTimeoutError 로그는 무시해도 됩니다.)
- API 키: Gemini API 호출 실패 시(400/404 에러), API 키가 올바른지 및 결제 계정이 연결되어 있는지 확인해 주세요.