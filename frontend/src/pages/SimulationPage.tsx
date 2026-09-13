import { useEffect } from "react";

import { LiveLog } from "../components/dashboard/LiveLog";
import { WidgetControls } from "../components/dashboard/WidgetControls";
import { MapView } from "../components/map/MapView";
import { simulationApi } from "../services/api";
import { useAppStore } from "../state/store";

const POLL_INTERVAL_MS = 2000;

export function SimulationPage() {
  const runId = useAppStore((s) => s.simulation?.run_id ?? null);
  const isFinished = useAppStore((s) => s.simulation?.is_finished ?? true);
  const setSimulation = useAppStore((s) => s.setSimulation);
  const isActive = runId !== null && !isFinished;

  useEffect(() => {
    if (!runId || isFinished) return;

    let cancelled = false;

    async function poll() {
      try {
        const { data } = await simulationApi.getState(runId!);
        if (!cancelled) setSimulation(data);
      } catch {
        // Un poll fallido no detiene el turno — se reintenta en el proximo tick.
      }
    }

    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [runId, isFinished, setSimulation]);

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-paper">
      <div className="relative flex-1 animate-fade-in" style={{ animationDelay: "150ms" }}>
        {/* OrdersWidget (lista comparativa inteligente/novato + detalle) vive
            DENTRO de MapView: necesita el estado de ruta que ya calcula ahi. */}
        <MapView />
        <LiveLog />
        {isActive && (
          <div id="config-widget-container" className="pointer-events-auto absolute z-panel top-6 left-6 animate-fade-up">
            <WidgetControls />
          </div>
        )}
      </div>
    </div>
  );
}
