export interface SimulationState {
  virtual_hour: number;
  virtual_minute: number;
  is_finished: boolean;
  net_earnings: number;
}

export interface Order {
  id: string;
  pickup_lat: number;
  pickup_lon: number;
  dropoff_lat: number;
  dropoff_lon: number;
  fare: number;
}

export interface OrderDecision {
  order_id: string;
  accepted: boolean;
  score: number;
  distance_km: number;
  time_minutes: number;
}

export type GodModePreset = "manana" | "comida" | "salida_trabajo";

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
