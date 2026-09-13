import { useState } from "react";

import { useTranslation } from "../../i18n/useTranslation";
import { simulationApi } from "../../services/api";
import { useAppStore } from "../../state/store";
import { VirtualClock } from "./VirtualClock";
import { WidgetControls } from "./WidgetControls";

export function ControlPanel() {
  const { t } = useTranslation();
  const user = useAppStore((s) => s.user);
  const simulation = useAppStore((s) => s.simulation);
  const setSimulation = useAppStore((s) => s.setSimulation);
  const [loading, setLoading] = useState(false);

  const isActive = simulation !== null && !simulation.is_finished;
  const virtualHour = simulation?.virtual_hour ?? 8;

  async function handleStart() {
    if (!user) return;
    setLoading(true);
    try {
      const { data } = await simulationApi.start({ user_id: user.id, vehicle: user.vehicle_type });
      setSimulation(data);
    } finally {
      setLoading(false);
    }
  }

  async function handleEnd() {
    if (!simulation) return;
    setLoading(true);
    try {
      const { data } = await simulationApi.end(simulation.run_id);
      setSimulation(data);
    } finally {
      setLoading(false);
    }
  }

  return (
    // Sin `backdrop-blur`: esta barra va en el flujo normal sobre el fondo
    // solido de la app, asi que no hay nada detras que desenfocar — solo
    // costaba una capa de GPU extra. El blur se reserva para los paneles que
    // flotan sobre el mapa, que si tienen contenido debajo.
    <div className="animate-fade-up relative space-y-3 border-b border-dust bg-gradient-to-r from-dust/30 via-paper to-blush/25 p-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <img src="/logo-mark.png" alt="" className="h-7 w-7" />
          <span className="text-sm font-semibold tracking-tight text-ink">Lynx</span>
          <VirtualClock virtualHour={virtualHour} />
          {isActive && (
            <span className="animate-fade-in rounded-full bg-blush/40 px-3 py-1 text-sm font-semibold tabular-nums tracking-[-0.01em] text-plum ring-1 ring-plum/15">
              ${simulation!.net_earnings.toFixed(2)} MXN
            </span>
          )}
        </div>

        {isActive ? (
          <button
            onClick={handleEnd}
            disabled={loading}
            className="rounded-full bg-paper/80 px-4 py-1.5 text-[13px] font-medium text-charcoal/75 ring-1 ring-plum/10 transition duration-300 ease-out hover:bg-paper hover:text-ink hover:ring-plum/25 active:scale-[0.97] disabled:opacity-50"
          >
            {loading ? t("control.ending") : t("control.endShift")}
          </button>
        ) : (
          <button
            onClick={handleStart}
            disabled={loading}
            className="group flex items-center gap-2 rounded-full bg-plum py-1.5 pl-4 pr-1.5 text-[13px] font-medium text-paper shadow-[0_10px_24px_-10px_rgba(104,73,89,0.95)] transition duration-300 ease-out hover:bg-ink active:scale-[0.98] disabled:opacity-50"
          >
            {loading ? t("control.starting") : t("control.startShift")}
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-paper/15 transition duration-300 ease-out group-hover:-translate-y-[1px] group-hover:translate-x-[2px] group-hover:scale-105">
              <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" aria-hidden="true">
                <path
                  d="M5 12h13M13 6.5 18.5 12 13 17.5"
                  stroke="currentColor"
                  strokeWidth="1.7"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </span>
          </button>
        )}
      </div>

      {/* Solo tiene sentido con un turno activo: sin el, no hay widgets
          flotantes en pantalla que mostrar u ocultar. */}
      {isActive && (
        <div className="flex flex-wrap items-center justify-end gap-3 border-t border-dust pt-3">
          <WidgetControls />
        </div>
      )}

      <span className="absolute inset-x-0 bottom-0 h-[2px] bg-gradient-to-r from-plum via-blush to-dust" />
    </div>
  );
}
