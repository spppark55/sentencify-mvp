import os
# .env 파일을 읽기 위한 라이브러리 (설치 필요: pip install python-dotenv)
from dotenv import load_dotenv
import google.generativeai as genai

# 1. .env 파일 로드 (환경변수 설정)
# 같은 폴더에 있는 .env 파일을 찾아서 로드합니다.
load_dotenv()

def test_gemini():
    print("========================================")
    print("🧪 Gemini API Standalone Test")
    print("========================================")

    # 2. API 키 확인
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ Error: 'GEMINI_API_KEY' 환경변수가 설정되지 않았습니다.")
        print("   .env 파일이 존재하는지, 키가 올바르게 들어있는지 확인해주세요.")
        return

    print(f"✅ API Key Found: {api_key[:5]}... (Masked)")

    # 3. Gemini 설정
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        print(f"❌ Configuration Error: {e}")
        return

    # 4. 모델 호출 테스트
    try:
        print("\n🚀 Sending request to Gemini (model: gemini-2.5-flash)...")
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        # 간단한 테스트 프롬프트
        response = model.generate_content("인공지능에 대해 한 문장으로 설명해줘.")
        
        print("\n✅ Success! Response received:")
        print("-" * 40)
        print(response.text)
        print("-" * 40)

    except Exception as e:
        print(f"\n❌ API Call Failed: {e}")
        print("   - API 키가 유효한지 확인하세요.")
        print("   - 인터넷 연결 상태를 확인하세요.")
        print("   - 구글 클라우드 콘솔에서 해당 API가 활성화되어 있는지 확인하세요.")

if __name__ == "__main__":
    test_gemini()