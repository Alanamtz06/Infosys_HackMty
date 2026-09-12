import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { AgentType, GodModePreset, Order, SimulationState, User } from "../types";

interface AppState {
  user: User | null;
  simulation: SimulationState | null;
  agentType: AgentType;
  activeOrders: Order[];
  // null = modo normal (sin preset de trafico forzado). Nunca arranca en un preset.
  godModePreset: GodModePreset | null;
  setUser: (user: User | null) => void;
  setSimulation: (state: SimulationState) => void;
  setAgentType: (agentType: AgentType) => void;
  setActiveOrders: (orders: Order[]) => void;
  setGodModePreset: (preset: GodModePreset | null) => void;
}

// TODO: alimentar `simulation` desde un WebSocket/polling al backend
// (ver app/api/routes/simulation.py) en lugar de solo mutaciones locales.
export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      user: null,
      simulation: null,
      agentType: "inteligente",
      activeOrders: [],
      godModePreset: null,
      setUser: (user) => set({ user }),
      setSimulation: (simulation) => set({ simulation }),
      setAgentType: (agentType) => set({ agentType }),
      setActiveOrders: (activeOrders) => set({ activeOrders }),
      setGodModePreset: (godModePreset) => set({ godModePreset }),
    }),
    {
      name: "delivery-sim-session",
      // Solo la sesion del usuario sobrevive un refresh; el resto del estado
      // de la simulacion (mock/local por ahora) arranca limpio cada vez.
      partialize: (state) => ({ user: state.user }),
    },
  ),
);
