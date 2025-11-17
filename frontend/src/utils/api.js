import axios from 'axios';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
});

export async function postRecommend(payload) {
  const { data } = await api.post('/recommend', payload);
  return data;
}

export default api;

