import { createContext, useContext, useState } from 'react';
import api from '../api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(localStorage.getItem('token'));

  const login = async (username, password) => {
    const res = await api.post('/auth/login', { username, password });
    const t = res.data.access_token;
    localStorage.setItem('token', t);
    setToken(t);
  };

  const logout = () => {
    localStorage.removeItem('token');
    setToken(null);
  };

  return (
    <AuthContext.Provider value={{ token, isAuth: !!token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
