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
        className={`rounded-full border px-3 py-1.5 text-sm font-medium transition duration-150 ease-out active:scale-95 ${
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
          className={`rounded-full border px-3 py-1.5 text-sm font-medium transition duration-150 ease-out active:scale-95 ${
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
