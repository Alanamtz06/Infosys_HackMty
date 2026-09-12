import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { SimulationState, User } from "../types";

interface AppState {
  user: User | null;
  // Snapshot completo de la ultima respuesta de /simulation/state (o /start,
  // /decide, /end, /god-mode — todas devuelven la misma forma). null = no
  // hay un turno activo todavia.
  simulation: SimulationState | null;
  setUser: (user: User | null) => void;
  setSimulation: (state: SimulationState | null) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      user: null,
      simulation: null,
      setUser: (user) => set({ user }),
      setSimulation: (simulation) => set({ simulation }),
    }),
    {
      name: "lynx-session",
      // Solo la sesion del usuario sobrevive un refresh; un turno activo no
      // se recupera tras recargar (el backend lo mantiene en memoria y no
      // hay forma de re-suscribirse a esa sesion desde cero todavia).
      partialize: (state) => ({ user: state.user }),
    },
  ),
);
