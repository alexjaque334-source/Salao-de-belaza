import axios from "axios";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || window.location.origin;
export const API = `${BACKEND_URL.replace(/\/$/, "")}/api`;

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function apiError(e) {
  const detail = e?.response?.data?.detail;
  if (detail == null) return e?.message || "Algo deu errado. Tente novamente.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((x) =>
        x && typeof x.msg === "string" ? x.msg : JSON.stringify(x)
      )
      .join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}
