-----

# Sentencify-MVP (Phase 1.5 완료)

이 프로젝트는 문맥 기반 문장 교정 추천 시스템 **Sentencify**의 MVP 버전입니다.
현재 **Phase 1.5** 단계가 완료되었으며, KoBERT 분류기(Rule), 벡터 검색(Micro), 문서 전체 분석(Macro)이 결합된 하이브리드 추천 로직이 적용되어 있습니다.

##  현재 진행 상황 (Current Progress)

  - [x] **Phase 1: 기본 추천 로직 완성**
      - `P_rule` (KoBERT Classifier): 룰 기반 카테고리 분류
      - `P_vec` (Vector Search): 문맥(Micro Context) 유사도 검색
  - [x] **Phase 1.5: 문서 전체 분석 완성**
      - `P_doc` (Macro Context): 문서 전체(Full Text) 분석 기반 가중치 적용 (`alpha`)
  - [ ] **Phase 2: 분석 대시보드 & 파이프라인 (진행 중)**
      - Streamlit 대시보드 뼈대 구축 완료
      - 데이터 수집 및 연동 테스트 진행 중

-----

##  실행 전 필수 준비 사항 (Prerequisites)

프로젝트를 실행하기 전에 **반드시** 아래 3가지 파일/설정을 준비해야 합니다.
*(필요한 파일은 공유된 구글 드라이브 링크를 참고하세요)*

### 1\. 모델 및 데이터 파일 배치

다운로드 받은 파일들을 아래 경로에 정확히 위치시켜 주세요.

  * **KoBERT 모델 폴더**
      * 소스: `kobert-classifier` 폴더 (내부에 `config.json`, `spiece.model` 등 포함)
      * 타겟 경로: **`./models/kobert-classifier/`**
  * **학습 데이터 (Qdrant 적재용)**
      * 소스: `train_data.csv`
      * 타겟 경로: **`./api/train_data.csv`**

### 2\. 환경 변수 설정 (.env)

프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 아래 내용을 입력하세요.
(Macro Context 분석을 위해 OpenAI API 사용이 필요하며, 약 $5 정도의 크레딧 결제가 권장됩니다.)

```bash
# .env 파일 생성
OPENAI_API_KEY=sk-proj-... (본인의 API KEY 입력)
```

-----

##  실행 방법 (How to Run)

도커를 이용하여 전체 서비스를 실행합니다.

```bash
docker-compose -f docker-compose.mini.yml up --build
```

###  주의 사항 (Qdrant Data Loading)

컨테이너가 실행된 직후에는 **추천 기능이 바로 동작하지 않을 수 있습니다.**

  * 서버 시작 시 `api/train_data.csv` 데이터를 Qdrant(Vector DB)에 적재하는 과정이 진행됩니다.
  * 로그에 **`Qdrant Collection Initialized`** 또는 데이터 적재 완료 메시지가 뜬 이후부터 정상적인 추천이 가능합니다.

-----

## 🔗 접속 정보 (Access Points)

서비스가 정상적으로 실행되면 아래 주소로 접속할 수 있습니다.

| 서비스 | URL | 설명 |
| :--- | :--- | :--- |
| **Frontend** | `http://localhost:5173` | 웹 에디터 및 사용자 인터페이스 |
| **Backend API** | `http://localhost:8000/docs` | Swagger API 명세서 및 테스트 |
| **Dashboard** | `http://localhost:8501` | 관리자용 데이터 분석 대시보드 |

-----

##  추천 점수 산출 공식 (Scoring Logic)

현재 `/recommend` API는 아래 공식을 사용하여 최종 점수(`P_final`)를 산출합니다.
규칙 기반 점수(`P_rule`)에 고정 가중치를 부여하고, 나머지 비중을 문맥(`P_vec`)과 문서 전체(`P_doc`)가 문서 성숙도(`alpha`)에 따라 나눠 갖는 구조입니다.

$$
P_{final} = 0.3 \times P_{rule} + 0.7 \times \left[ (1 - \alpha) P_{vec} + \alpha P_{doc} \right]
$$  * **$P_{rule}$ (30%)**: KoBERT 모델이 판단한 카테고리 확률 (고정 비중)
* **$P_{vec}$**: 선택된 문장 주변의 문맥 유사도 (Micro Context)
* **$P_{doc}$**: 문서 전체의 주제 및 특성 분석 (Macro Context)
* **$\alpha$ (Alpha)**: 문서 성숙도 (문서 길이에 따라 0\~1 사이 값으로 동적 변동)
$$