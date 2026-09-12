import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
});

// TODO: reemplazar por llamadas reales a los endpoints del backend
// (app/api/routes en el backend) conforme se implemente su logica de negocio.
export const simulationApi = {
  start: (payload: { real_duration_minutes: number; agent_type: string }) =>
    api.post("/simulation/start", payload),
  getState: () => api.get("/simulation/state"),
  godMode: (preset: "manana" | "comida" | "salida_trabajo") =>
    api.post("/simulation/god-mode", { preset }),
};

export const ordersApi = {
  evaluate: (payload: unknown) => api.post("/orders/evaluate", payload),
};

export const auditApi = {
  auditDecision: (orderId: string) => api.post("/audit/decision", { order_id: orderId }),
};

export const statsApi = {
  getHistory: (period: string) => api.get(`/stats/history/${period}`),
  getScoreboard: () => api.get("/stats/scoreboard"),
};
