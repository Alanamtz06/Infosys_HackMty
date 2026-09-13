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

export type AgentType = "inteligente" | "novato";

export type VehicleType = "moto" | "auto";

export interface User {
  id: string;
  username: string;
  vehicle_type: VehicleType;
}

export interface LiveDashboardSummary {
  agent_type: AgentType;
  vehicle: VehicleType;
  trips_last_5min: number;
  accepted_last_5min: number;
  net_score_last_5min: number;
  avg_score_last_5min: number;
}

export interface LiveTrip {
  id: number;
  created_at: string;
  run_id: string;
  order_id: string;
  agent_type: AgentType;
  vehicle: VehicleType;
  accepted: boolean;
  fare: number;
  distance_km: number;
  time_minutes: number;
  gas_cost_live: number;
  time_cost_live: number;
  score_live: number;
  username: string | null;
}

export interface LiveDashboardResponse {
  summary: LiveDashboardSummary[];
  recent_trips: LiveTrip[];
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
