import { useState } from "react";

import { simulationApi } from "../../services/api";
import { useAppStore } from "../../state/store";
import { GodModeButtons } from "./GodModeButtons";
import { VirtualClock } from "./VirtualClock";

export function ControlPanel() {
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
    <div className="animate-fade-up relative space-y-3 border-b border-dust bg-gradient-to-r from-dust/30 via-paper to-blush/25 p-4 backdrop-blur">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <img src="/logo-mark.png" alt="Lynx" className="h-7 w-7" />
          <span className="text-sm font-semibold tracking-tight text-ink">Lynx</span>
          <VirtualClock virtualHour={virtualHour} />
          {isActive && (
            <span className="animate-fade-in rounded-full bg-blush/40 px-2.5 py-1 text-sm font-semibold tabular-nums text-plum">
              ${simulation!.net_earnings.toFixed(2)} MXN
            </span>
          )}
        </div>

        {isActive ? (
          <button
            onClick={handleEnd}
            disabled={loading}
            className="rounded-full border border-dust bg-white px-4 py-1.5 text-sm font-medium text-charcoal transition duration-150 ease-out hover:border-plum/30 hover:bg-dust/30 active:scale-95 disabled:opacity-50"
          >
            {loading ? "Ending…" : "End Shift"}
          </button>
        ) : (
          <button
            onClick={handleStart}
            disabled={loading}
            className="rounded-full bg-plum px-4 py-1.5 text-sm font-medium text-paper shadow-[0_2px_8px_rgba(104,73,89,0.35)] transition duration-150 ease-out hover:bg-charcoal active:scale-95 disabled:opacity-50"
          >
            {loading ? "Starting…" : "Start Shift"}
          </button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t border-dust pt-3">
        <span className="text-xs font-medium uppercase tracking-[0.15em] text-plum">God Mode (demo)</span>
        <GodModeButtons disabled={!isActive} />
      </div>

      <span className="absolute inset-x-0 bottom-0 h-[2px] bg-gradient-to-r from-plum via-blush to-dust" />
    </div>
  );
}
