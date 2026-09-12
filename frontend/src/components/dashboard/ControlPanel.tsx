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
    <div className="animate-fade-up relative space-y-3 border-b border-dust bg-gradient-to-r from-dust/30 via-paper to-blush/25 p-4 backdrop-blur">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-plum text-paper">
            <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 8h16l-1.4 11.1a2 2 0 0 1-2 1.9H7.4a2 2 0 0 1-2-1.9L4 8Z" />
              <path d="M8 8V6a4 4 0 0 1 8 0v2" />
            </svg>
          </span>
          <span className="text-sm font-semibold tracking-tight text-ink">Delivery Sim ZMM</span>
          <VirtualClock virtualHour={virtualHour} />
        </div>
        <select
          value={agentType}
          onChange={(e) => setAgentType(e.target.value as "inteligente" | "novato")}
          className="rounded-md border border-dust bg-white px-2 py-1.5 text-sm text-ink transition duration-150 ease-out hover:border-plum/40 focus-visible:border-plum focus-visible:ring-2 focus-visible:ring-plum/20"
        >
          <option value="inteligente">Agente Inteligente</option>
          <option value="novato">Agente Novato</option>
        </select>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t border-dust pt-3">
        <span className="text-xs font-medium uppercase tracking-[0.15em] text-plum">
          Modo Dios (demo)
        </span>
        <GodModeButtons />
      </div>

      <span className="absolute inset-x-0 bottom-0 h-[2px] bg-gradient-to-r from-plum via-blush to-dust" />
    </div>
  );
}
