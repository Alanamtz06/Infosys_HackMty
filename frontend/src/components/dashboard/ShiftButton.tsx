import { useState } from "react";
import { useTranslation } from "../../i18n/useTranslation";
import { simulationApi } from "../../services/api";
import { useAppStore } from "../../state/store";

export function ShiftButton() {
  const { t } = useTranslation();
  const user = useAppStore((s) => s.user);
  const simulation = useAppStore((s) => s.simulation);
  const setSimulation = useAppStore((s) => s.setSimulation);
  const [loading, setLoading] = useState(false);

  const isActive = simulation !== null && !simulation.is_finished;

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

  if (isActive) {
    return (
      <button
        onClick={handleEnd}
        disabled={loading}
        className="rounded-full px-3 py-1.5 text-[12px] font-medium text-charcoal/70 transition duration-300 ease-out hover:bg-blush/45 hover:text-ink active:scale-[0.97] disabled:opacity-50"
      >
        {loading ? t("control.ending") : t("control.endShift")}
      </button>
    );
  }

  return (
    <button
      onClick={handleStart}
      disabled={loading}
      className="group flex items-center gap-1.5 rounded-full bg-plum py-1 pl-3 pr-1 text-[12px] font-medium text-paper shadow-[0_6px_16px_-8px_rgba(104,73,89,0.9)] transition duration-300 ease-out hover:bg-plum/90 active:scale-[0.98] disabled:opacity-50"
    >
      {loading ? t("control.starting") : t("control.startShift")}
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-paper/15 transition duration-300 ease-out group-hover:-translate-y-[1px] group-hover:translate-x-[2px] group-hover:scale-105">
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
  );
}
