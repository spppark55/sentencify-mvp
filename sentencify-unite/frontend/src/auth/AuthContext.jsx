import { createContext, useContext, useEffect, useState } from 'react';

const AuthCtx = createContext(null);
const KEY = 'auth:user:v1';

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // { id, email, name }

  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) setUser(JSON.parse(raw));
    } catch {}
  }, []);

  const login = async ({ email, password }) => {
    // ✅ 목 로그인: 실제로는 서버에 POST /auth/login
    if (!email || !password) throw new Error('이메일/비밀번호를 입력하세요');
    const fakeUser = {
      id: crypto.randomUUID(),
      email,
      name: email.split('@')[0],
    };
    setUser(fakeUser);
    localStorage.setItem(KEY, JSON.stringify(fakeUser));
  };

  const signup = async ({ email, password }) => {
    // ✅ 목 회원가입: 실제로는 서버에 POST /auth/signup
    if (!email || !password) throw new Error('이메일/비밀번호를 입력하세요');
    const fakeUser = {
      id: crypto.randomUUID(),
      email,
      name: email.split('@')[0],
    };
    setUser(fakeUser);
    localStorage.setItem(KEY, JSON.stringify(fakeUser));
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem(KEY);
  };

  return (
    <AuthCtx.Provider value={{ user, login, signup, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
