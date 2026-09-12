import { useAppStore } from "../../state/store";
import { GodModeButtons } from "./GodModeButtons";
import { VirtualClock } from "./VirtualClock";

export function ControlPanel() {
  const simulation = useAppStore((s) => s.simulation);
  const agentType = useAppStore((s) => s.agentType);
  const setAgentType = useAppStore((s) => s.setAgentType);

  // Hora neutral (11:00) mientras no hay simulacion corriendo: fuera de toda
  // ventana de trafico pico, para no arrancar ya "dentro" de un Modo Dios.
  const virtualHour = simulation?.virtual_hour ?? 11;

  return (
    <div className="space-y-3 border-b border-neutral-800 bg-neutral-950 p-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-neutral-200">Delivery Sim ZMM</span>
          <VirtualClock virtualHour={virtualHour} />
        </div>
        <select
          value={agentType}
          onChange={(e) => setAgentType(e.target.value as "inteligente" | "novato")}
          className="rounded-md bg-neutral-800 px-2 py-1.5 text-sm text-neutral-100"
        >
          <option value="inteligente">Agente Inteligente</option>
          <option value="novato">Agente Novato</option>
        </select>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t border-neutral-800 pt-3">
        <span className="text-xs font-medium uppercase tracking-wide text-neutral-500">
          Modo Dios (demo)
        </span>
        <GodModeButtons />
      </div>
    </div>
  );
}
