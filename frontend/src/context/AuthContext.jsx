import { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null = loading
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      setReady(true);
      return;
    }
    api
      .get("/auth/me")
      .then((res) => setUser(res.data))
      .catch(() => {
        localStorage.removeItem("token");
        setUser(false);
      })
      .finally(() => setReady(true));
  }, []);

  const authenticate = (token, u) => {
    localStorage.setItem("token", token);
    setUser(u);
  };

  const logout = () => {
    localStorage.removeItem("token");
    api.post("/auth/logout").catch(() => {});
    setUser(false);
  };

  return (
    <AuthContext.Provider value={{ user, ready, authenticate, logout, setUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
