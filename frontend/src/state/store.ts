import { create } from "zustand";

import type { AgentType, GodModePreset, Order, SimulationState } from "../types";

interface AppState {
  simulation: SimulationState | null;
  agentType: AgentType;
  activeOrders: Order[];
  // null = modo normal (sin preset de trafico forzado). Nunca arranca en un preset.
  godModePreset: GodModePreset | null;
  setSimulation: (state: SimulationState) => void;
  setAgentType: (agentType: AgentType) => void;
  setActiveOrders: (orders: Order[]) => void;
  setGodModePreset: (preset: GodModePreset | null) => void;
}

// TODO: alimentar `simulation` desde un WebSocket/polling al backend
// (ver app/api/routes/simulation.py) en lugar de solo mutaciones locales.
export const useAppStore = create<AppState>((set) => ({
  simulation: null,
  agentType: "inteligente",
  activeOrders: [],
  godModePreset: null,
  setSimulation: (simulation) => set({ simulation }),
  setAgentType: (agentType) => set({ agentType }),
  setActiveOrders: (activeOrders) => set({ activeOrders }),
  setGodModePreset: (godModePreset) => set({ godModePreset }),
}));
