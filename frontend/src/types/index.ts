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
