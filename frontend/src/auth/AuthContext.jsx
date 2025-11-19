import { createContext, useContext, useEffect, useState } from 'react';
import { api } from '../utils/api.js';

const AuthCtx = createContext(null);
const USER_KEY = 'auth:user:v1';
const TOKEN_KEY = 'auth:token:v1';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // { id, email }

  useEffect(() => {
    try {
      const rawUser = localStorage.getItem(USER_KEY);
      const token = localStorage.getItem(TOKEN_KEY);
      if (rawUser) {
        const parsed = JSON.parse(rawUser);
        setUser(parsed);
        if (token) {
          api.defaults.headers.common.Authorization = `Bearer ${token}`;
        }
      }
    } catch {}
  }, []);

  const login = async ({ email, password }) => {
    if (!email || !password) throw new Error('이메일/비밀번호를 입력하세요');

    const res = await api.post('/auth/login', { email, password });
    const { access_token } = res.data || {};
    if (!access_token) throw new Error('로그인 응답에 access_token이 없습니다.');

    const nextUser = { email };
    setUser(nextUser);
    try {
      localStorage.setItem(USER_KEY, JSON.stringify(nextUser));
      localStorage.setItem(TOKEN_KEY, access_token);
    } catch {}

    api.defaults.headers.common.Authorization = `Bearer ${access_token}`;
  };

  const signup = async ({ email, password }) => {
    if (!email || !password) throw new Error('이메일/비밀번호를 입력하세요');

    await api.post('/auth/signup', { email, password });
    // 회원가입 후 바로 로그인
    await login({ email, password });
  };

  const logout = () => {
    setUser(null);
    try {
      localStorage.removeItem(USER_KEY);
      localStorage.removeItem(TOKEN_KEY);
    } catch {}
    delete api.defaults.headers.common.Authorization;
  };

  return (
    <AuthCtx.Provider value={{ user, login, signup, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
