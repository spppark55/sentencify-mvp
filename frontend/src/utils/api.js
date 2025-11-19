import axios from 'axios';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
});

export async function postRecommend(payload) {
  const { data } = await api.post('/recommend', payload);
  return data;
}

/**
 * B 이벤트: editor_run_paraphrasing
 * 실제 Gemini API를 사용한 문장 교정 요청
 */
export async function postParaphrase(payload) {
  const { data } = await api.post('/paraphrase', payload);
  return data;
}

export default api;

