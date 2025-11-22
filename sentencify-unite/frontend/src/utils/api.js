import axios from 'axios';

// API BASE URL은 환경 변수 VITE_API_BASE_URL 또는 로컬 8000번 포트로 설정됩니다.
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  // 💡 [수정]: 타임아웃을 20초로 증가 (백엔드 처리 지연 대비)
  timeout: 20000, 
});

export async function postRecommend(payload) {
  try {
    // 💡 [수정]: axios는 기본적으로 응답을 JSON으로 파싱하려 시도합니다.
    // 여기서 .data를 구조분해할 때 오류가 발생할 가능성이 있습니다.
    const response = await api.post('/recommend', payload);
    
    // 💡 [추가]: 혹시 모를 에러를 대비하여 응답 상태 코드를 다시 확인합니다.
    if (response.status !== 200) {
      throw new Error(`Server returned status ${response.status}`);
    }

    // response.data는 이미 JSON 객체일 것입니다.
    return response.data;
  } catch (error) {
    // 💡 [추가]: 에러 객체를 명확하게 로깅하여 문제 진단 (Console)
    console.error("AXIOS ERROR IN postRecommend:", error.message);
    if (error.response) {
        console.error("Response Data:", error.response.data);
        console.error("Response Status:", error.response.status);
    }
    // 프론트엔드의 catch 블록으로 에러를 다시 던집니다.
    throw error;
  }
}

export default api;