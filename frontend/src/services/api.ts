import axios from "axios";

import type {
  BenchmarkResult,
  HistoryResponse,
  LiveDashboardResponse,
  RoutePreview,
  ScoreboardResponse,
  SimulationState,
  User,
  VehicleType,
} from "../types";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
});

api.interceptors.request.use((config) => {
  if (config.method?.toLowerCase() === 'get') {
    config.params = config.params || {};
    config.params._t = Date.now();
  }
  return config;
});

export const simulationApi = {
  start: (payload: { user_id?: string; vehicle: VehicleType }) =>
    api.post<SimulationState>("/simulation/start", payload),
  getState: (runId: string) => api.get<SimulationState>("/simulation/state", { params: { run_id: runId } }),
  decide: (payload: { run_id: string; order_id: string; accept: boolean }) =>
    api.post<SimulationState>("/simulation/decide", payload),
  end: (runId: string) => api.post<SimulationState>("/simulation/end", { run_id: runId }),
  // Bajo demanda: solo cuando el conductor selecciona una oferta, no en cada
  // sondeo (rutear las 5 pendientes cada 2s seria caro y casi todo tirado).
  getRoute: (runId: string, orderId: string) =>
    api.get<RoutePreview>("/simulation/route", { params: { run_id: runId, order_id: orderId } }),
  // Turno headless (agente autonomo vs novato, sin reloj del mundo): el
  // dashboard lo dispara bajo demanda, nunca en el sondeo automatico.
  benchmark: (payload: { hours: number; vehicle: VehicleType; start_hour?: number }) =>
    api.post<BenchmarkResult>("/simulation/benchmark", payload),
};

export const ordersApi = {
  evaluate: (payload: unknown) => api.post("/orders/evaluate", payload),
};

export const auditApi = {
  auditDecision: (orderId: string) => api.post("/audit/decision", { order_id: orderId }),
};

export const statsApi = {
  getHistory: (period: string) => api.get<HistoryResponse>(`/stats/history/${period}`),
  getScoreboard: (sessionId?: string) =>
    api.get<ScoreboardResponse>("/stats/scoreboard", { params: sessionId ? { session_id: sessionId } : undefined }),
  getLive: () => api.get<LiveDashboardResponse>("/stats/live"),
};

export const authApi = {
  register: (payload: { username: string; password: string; vehicle_type: VehicleType }) =>
    api.post<User>("/auth/register", payload),
  login: (payload: { username: string; password: string }) => api.post<User>("/auth/login", payload),
  updateProfile: (payload: { user_id: string; vehicle_type: VehicleType }) =>
    api.patch<User>("/auth/profile", payload),
};
