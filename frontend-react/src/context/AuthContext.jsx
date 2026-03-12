import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem('authToken'));
  const [loading, setLoading] = useState(true);

  // On mount, verify existing token with backend
  useEffect(() => {
    const initAuth = async () => {
      const stored = localStorage.getItem('authToken');
      if (!stored) {
        setLoading(false);
        return;
      }
      try {
        const res = await fetch(`${API_BASE_URL}/auth/verify`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${stored}` },
        });
        if (res.ok) {
          const data = await res.json();
          if (data.success && data.user) {
            setUser(data.user);
            setToken(stored);
          } else {
            _clearAuth();
          }
        } else {
          _clearAuth();
        }
      } catch {
        // Backend unreachable — keep token optimistically so user isn't logged out
      } finally {
        setLoading(false);
      }
    };
    initAuth();
  }, []);

  const _clearAuth = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('userName');
    setToken(null);
    setUser(null);
  };

  const login = useCallback(async (email, password) => {
    const formData = new FormData();
    formData.append('email', email);
    formData.append('password', password);

    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      body: formData,
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || data.message || 'Login failed');
    }

    if (data.token) {
      localStorage.setItem('authToken', data.token);
      setToken(data.token);
    }
    if (data.user) {
      setUser(data.user);
      if (data.user.name) localStorage.setItem('userName', data.user.name);
    }
    return data;
  }, []);

  const register = useCallback(async (name, email, password) => {
    const res = await fetch(`${API_BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || data.message || 'Registration failed');
    }

    if (data.token) {
      localStorage.setItem('authToken', data.token);
      setToken(data.token);
    }
    if (data.user) {
      setUser(data.user);
      if (name) localStorage.setItem('userName', name);
    }
    return data;
  }, []);

  const logout = useCallback(() => {
    _clearAuth();
  }, []);

  const isAuthenticated = !!token;

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, isAuthenticated }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
