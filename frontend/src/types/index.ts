export interface PendingOrder {
  order_id: string;
  pickup_name: string | null;
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
}

export interface SimEvent {
  ts: string;
  type: "shift_started" | "shift_ended" | "order_generated" | "order_accepted" | "order_rejected" | "god_mode";
  message: string;
}

export interface SimulationState {
  run_id: string;
  vehicle: VehicleType;
  virtual_hour: number;
  virtual_minute: number;
  is_finished: boolean;
  net_earnings: number;
  god_mode_preset: GodModePreset | null;
  pending_orders: PendingOrder[];
  events: SimEvent[];
}

export interface Order {
  id: string;
  pickup_lat: number;
  pickup_lon: number;
  dropoff_lat: number;
  dropoff_lon: number;
  fare: number;
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
