
import axios from "axios";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || window.location.origin;

export const platformApi = axios.create({
  baseURL: `${BACKEND_URL.replace(/\/$/, "")}/api`,
});

platformApi.interceptors.request.use((config) => {
  const token = localStorage.getItem("platform_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
