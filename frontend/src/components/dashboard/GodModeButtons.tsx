import { simulationApi } from "../../services/api";
import { useAppStore } from "../../state/store";
import type { GodModePreset } from "../../types";

const PRESETS: { key: GodModePreset; label: string }[] = [
  { key: "manana", label: "Mañana" },
  { key: "comida", label: "Hora de Comida" },
  { key: "salida_trabajo", label: "Salida del Trabajo" },
];

// Grupo de botones aislado del resto del panel: nunca se activa un preset
// automaticamente, solo cuando el usuario hace click aqui.
export function GodModeButtons() {
  const activePreset = useAppStore((s) => s.godModePreset);
  const setGodModePreset = useAppStore((s) => s.setGodModePreset);

  function applyPreset(key: GodModePreset) {
    setGodModePreset(key);
    simulationApi.godMode(key);
  }

  function resetToNormal() {
    setGodModePreset(null);
    // TODO: exponer un endpoint /simulation/normal en el backend para
    // devolver el reloj virtual a su avance normal en vez de solo limpiar la UI.
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        onClick={resetToNormal}
        className={`rounded-full px-3 py-1.5 text-sm transition-colors ${
          activePreset === null
            ? "bg-emerald-500 text-black"
            : "bg-neutral-800 text-neutral-300 hover:bg-neutral-700"
        }`}
      >
        Normal
      </button>
      {PRESETS.map(({ key, label }) => (
        <button
          key={key}
          onClick={() => applyPreset(key)}
          className={`rounded-full px-3 py-1.5 text-sm transition-colors ${
            activePreset === key
              ? "bg-amber-500 text-black"
              : "bg-neutral-800 text-neutral-300 hover:bg-neutral-700"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
