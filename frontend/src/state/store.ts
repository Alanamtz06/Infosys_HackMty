import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { Language } from "../i18n/translations";
import type { SimulationState, User } from "../types";

interface AppState {
  user: User | null;
  // Snapshot completo de la ultima respuesta de /simulation/state (o /start,
  // /decide, /end — todas devuelven la misma forma). null = no hay un turno
  // activo todavia.
  simulation: SimulationState | null;
  // Oferta que el conductor esta inspeccionando: pinta su ruta en el mapa y
  // abre su ficha. No se persiste — es seleccion de UI, no sesion.
  selectedOrderId: string | null;
  // Idioma de la interfaz. Persistido junto a `user` (una preferencia de
  // cuenta, no de sesion) — default "es": el publico de la ZMM y los
  // comentarios del propio codigo ya son en español.
  language: Language;
  setUser: (user: User | null) => void;
  setSimulation: (state: SimulationState | null) => void;
  setSelectedOrderId: (orderId: string | null) => void;
  setLanguage: (language: Language) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      user: null,
      simulation: null,
      selectedOrderId: null,
      language: "es",
      setUser: (user) => set({ user }),
      setSimulation: (simulation) =>
        set((prev) => ({
          simulation,
          // Si la oferta seleccionada ya no esta pendiente (se acepto, se
          // rechazo o expiro), se suelta la seleccion: dejarla apuntando a
          // un id muerto deja la ruta pintada sobre una orden que ya no existe.
          selectedOrderId:
            prev.selectedOrderId &&
            simulation?.pending_orders.some((o) => o.order_id === prev.selectedOrderId)
              ? prev.selectedOrderId
              : null,
        })),
      setSelectedOrderId: (selectedOrderId) => set({ selectedOrderId }),
      setLanguage: (language) => set({ language }),
    }),
    {
      name: "lynx-session",
      // Solo la sesion del usuario sobrevive un refresh; un turno activo no
      // se recupera tras recargar (el backend lo mantiene en memoria y no
      // hay forma de re-suscribirse a esa sesion desde cero todavia).
      partialize: (state) => ({ user: state.user, language: state.language }),
    },
  ),
);
