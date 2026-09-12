import { simulationApi } from "../../services/api";
import { useAppStore } from "../../state/store";
import type { GodModePreset } from "../../types";

const PRESETS: { key: GodModePreset; label: string }[] = [
  { key: "manana", label: "Morning" },
  { key: "comida", label: "Lunch Rush" },
  { key: "salida_trabajo", label: "Rush Hour" },
];

interface Props {
  disabled?: boolean;
}

// Grupo de botones aislado del resto del panel: nunca se activa un preset
// automaticamente, solo cuando el usuario hace click aqui. Deshabilitado
// mientras no hay un turno activo (no tiene sentido forzar trafico sin reloj).
export function GodModeButtons({ disabled }: Props) {
  const simulation = useAppStore((s) => s.simulation);
  const setSimulation = useAppStore((s) => s.setSimulation);
  const activePreset = simulation?.god_mode_preset ?? null;

  async function applyPreset(preset: GodModePreset | null) {
    if (!simulation) return;
    const { data } = await simulationApi.godMode(simulation.run_id, preset);
    setSimulation(data);
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        onClick={() => applyPreset(null)}
        disabled={disabled}
        className={`rounded-full border px-3 py-1.5 text-sm font-medium transition duration-150 ease-out active:scale-95 disabled:cursor-not-allowed disabled:opacity-40 ${
          activePreset === null
            ? "border-plum bg-plum text-paper shadow-[0_2px_8px_rgba(104,73,89,0.35)]"
            : "border-dust bg-white text-charcoal hover:border-plum/30 hover:bg-dust/30"
        }`}
      >
        Normal
      </button>
      {PRESETS.map(({ key, label }) => (
        <button
          key={key}
          onClick={() => applyPreset(key)}
          disabled={disabled}
          className={`rounded-full border px-3 py-1.5 text-sm font-medium transition duration-150 ease-out active:scale-95 disabled:cursor-not-allowed disabled:opacity-40 ${
            activePreset === key
              ? "border-plum/40 bg-blush text-plum shadow-[0_2px_8px_rgba(229,202,217,0.7)]"
              : "border-dust bg-white text-charcoal hover:border-plum/30 hover:bg-dust/30"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
