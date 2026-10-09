import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const platformApi = axios.create({ baseURL: `${BACKEND_URL}/api` });

platformApi.interceptors.request.use((config) => {
  const token = localStorage.getItem("platform_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
