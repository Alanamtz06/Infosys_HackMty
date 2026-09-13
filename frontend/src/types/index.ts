export interface NoviceOutcome {
  outcome: "accepted" | "busy" | "unreachable";
  score: number | null;
  fare: number | null;
  distance_km: number | null;
  time_minutes: number | null;
}

export interface PendingOrder {
  order_id: string;
  pickup_name: string | null;
  // Zona nombrada de la ZMM mas cercana al restaurante (ver
  // backend/app/engine/zones.py) — deja comparar ofertas por vecindario.
  zone: string;
  pickup_lat: number;
  pickup_lon: number;
  dropoff_lat: number;
  dropoff_lon: number;
  fare: number;
  distance_km: number;
  time_minutes: number;
  gas_cost: number;
  time_cost: number;
  score: number;
  should_accept: boolean;
  // True si la mochila del repartidor ya tiene 2 pedidos: esta oferta no se
  // puede aceptar sin importar el score (distinto de "no conviene").
  at_capacity: boolean;
  // Veredicto que el agente novato YA tomo para esta misma orden — no una
  // prediccion, lo que su propio TripRecord ya registro.
  novice: NoviceOutcome;
}

export interface RouteStop {
  kind: "courier" | "pickup" | "dropoff";
  label: string;
  lat: number;
  lon: number;
  eta_minutes: number;
  // A que pedido pertenece esta parada — null para "courier" y para rutas de
  // un solo pedido; distingue los 2 pickups/dropoffs de una mochila combinada.
  order_id: string | null;
}

export interface RouteLeg {
  kind: "to_pickup" | "to_dropoff";
  distance_km: number;
  minutes: number;
}

/** Ruta que se recorreria si se acepta una oferta (GET /simulation/route). */
export interface RoutePreview {
  order_id: string;
  pickup_name: string | null;
  /** `[lon, lat]` — el orden de GeoJSON, tal cual lo espera MapLibre. */
  coordinates: [number, number][];
  pickup_index: number;
  stops: RouteStop[];
  legs: RouteLeg[];
  total_minutes: number;
  distance_km: number;
  fare: number;
  score: number;
}

/** Entrega en curso: la misma geometria, mas donde va el repartidor encima. */
export interface ActiveRoute {
  order_id: string;
  pickup_name: string | null;
  coordinates: [number, number][];
  pickup_index: number;
  stops: RouteStop[];
  progress: number;
  phase: "to_pickup" | "to_dropoff";
  courier_lat: number;
  courier_lon: number;
  eta_minutes: number;
  fare: number;
  is_current: boolean;
  // Nombre del restaurante del 2do pedido cuando esta entrega es una mochila
  // combinada (2 pedidos en una sola ruta) — null en el caso normal.
  extra_pickup_name: string | null;
}

export interface SimEvent {
  ts: string;
  type: "shift_started" | "shift_ended" | "order_generated" | "order_accepted" | "order_rejected";
  message: string;
}

export interface SimulationState {
  run_id: string;
  vehicle: VehicleType;
  virtual_hour: number;
  virtual_minute: number;
  is_finished: boolean;
  net_earnings: number;
  pending_orders: PendingOrder[];
  events: SimEvent[];

  // Campos que el backend ya mandaba pero el frontend no declaraba.
  sim_time: string;
  time_acceleration: number;
  courier_lat: number | null;
  courier_lon: number | null;
  /** Pedidos en la mochila del repartidor ahora mismo (0/1/2). */
  active_deliveries: number;
  deliveries_completed: number;
  orders_accepted: number;
  novice_earnings: number;
  session_id: string;

  /** Geometria de las entregas en curso — lo que anima el vehiculo. */
  active_routes: ActiveRoute[];
}

export interface Order {
  id: string;
  pickup_lat: number;
  pickup_lon: number;
  dropoff_lat: number;
  dropoff_lon: number;
  fare: number;
}

export type AgentType = "inteligente" | "novato" | "autonomo";

export type VehicleType = "moto" | "auto";

export interface User {
  id: string;
  username: string;
  vehicle_type: VehicleType;
}

export interface LiveDashboardSummary {
  agent_type: AgentType;
  vehicle: VehicleType;
  trips: number;
  accepted: number;
  net_score: number;
  avg_score: number;
  // Tasa de aceptacion (0-1) y MXN netos por hora TRABAJADA (tiempo en ruta
  // de entregas aceptadas) — la misma metrica que decision/policy.py compara
  // contra RESERVATION_RATE_MXN_PER_HOUR para aceptar/rechazar.
  acceptance_rate: number;
  earnings_per_hour: number;
}

export interface LiveDashboardResponse {
  is_active: boolean;
  summary: LiveDashboardSummary[];
}

export interface HistoryPoint {
  date: string;
  netEarnings: number;
  gasSaved: number;
  timeSaved: number;
  trips: number;
  acceptedTrips: number;
  noviceNetEarnings: number;
}

export interface HistoryTotals {
  netEarnings: number;
  gasSaved: number;
  timeSaved: number;
  trips: number;
  acceptedTrips: number;
}

export interface HistoryResponse {
  period: string;
  count: number;
  points: HistoryPoint[];
  totals: HistoryTotals;
}

// --- Marcador global (/stats/scoreboard) y benchmark autonomo (/simulation/benchmark) ---
// Ambos comparan agentes sobre el MISMO stream de ordenes, pero difieren en
// quien decide: el marcador es inteligente (asistido por humano) vs novato en
// vivo; el benchmark corre la MISMA politica de decision sin humano en el
// loop (agente autonomo) contra el mismo novato, en un turno headless aparte.

export interface ScoreboardAgentTotals {
  net_earnings: number;
  trips: number;
  accepted_trips: number;
  gas_cost: number;
  time_minutes: number;
  distance_km: number;
  avg_score: number;
  avg_rejected_score: number;
  acceptance_rate: number;
  earnings_per_hour: number;
  earnings_per_km: number;
}

export interface ScoreboardResponse {
  session_id: string | null;
  inteligente: ScoreboardAgentTotals;
  novato: ScoreboardAgentTotals;
  savings: {
    net_earnings?: number;
    gas_cost?: number;
    time_minutes?: number;
    earnings_per_hour?: number;
  };
}

export interface AgentBenchmark {
  net_earnings: number;
  accepted: number;
  rejected: number;
  missed_while_busy: number;
  minutes_worked: number;
  distance_km: number;
  earnings_per_hour: number;
}

export interface BenchmarkResult {
  session_id: string;
  hours: number;
  start_hour: number;
  vehicle: VehicleType;
  orders_offered: number;
  inteligente: AgentBenchmark;
  novato: AgentBenchmark;
  advantage_mxn: number;
  advantage_pct: number;
}
