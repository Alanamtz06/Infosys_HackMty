import { useEffect } from "react";

import { ControlPanel } from "../components/dashboard/ControlPanel";
import { LiveLog } from "../components/dashboard/LiveLog";
import { MapView } from "../components/map/MapView";
import { simulationApi } from "../services/api";
import { useAppStore } from "../state/store";

const POLL_INTERVAL_MS = 2000;

export function SimulationPage() {
  const runId = useAppStore((s) => s.simulation?.run_id ?? null);
  const isFinished = useAppStore((s) => s.simulation?.is_finished ?? true);
  const setSimulation = useAppStore((s) => s.setSimulation);

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
      <ControlPanel />
      <div className="relative flex-1 animate-fade-in" style={{ animationDelay: "150ms" }}>
        {/* OrdersWidget (lista comparativa inteligente/novato + detalle) vive
            DENTRO de MapView: necesita el estado de ruta que ya calcula ahi. */}
        <MapView />
        <LiveLog />
      </div>
    </div>
  );
}
