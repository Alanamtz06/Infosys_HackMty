import { useAppStore } from "../../state/store";
import type { SimEvent } from "../../types";

const EVENT_DOT: Record<SimEvent["type"], string> = {
  shift_started: "bg-plum",
  shift_ended: "bg-charcoal",
  order_generated: "bg-dust ring-1 ring-plum/30",
  order_accepted: "bg-plum",
  order_rejected: "bg-charcoal/40",
  god_mode: "bg-blush ring-1 ring-plum/40",
};

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// Log en vivo de lo que hace el backend: cada tick de /simulation/state
// puede generar una orden, y cada decision del conductor queda registrada
// aqui con su hora real (no la hora virtual) para que se sienta como una
// bitacora de verdad, no solo un contador.
export function LiveLog() {
  const simulation = useAppStore((s) => s.simulation);
  const events = simulation?.events ?? [];

  return (
    <div className="animate-fade-in absolute right-4 top-4 z-10 flex max-h-[calc(100%-2rem)] w-72 flex-col overflow-hidden rounded-xl border border-dust bg-paper/95 shadow-[0_8px_24px_rgba(104,73,89,0.12)] backdrop-blur">
      <div className="flex items-center gap-2 border-b border-dust px-3 py-2">
        <span className="relative flex h-2 w-2">
          {simulation && !simulation.is_finished && (
            <span className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-plum" />
          )}
          <span className="relative inline-flex h-2 w-2 rounded-full bg-plum" />
        </span>
        <span className="text-xs font-medium uppercase tracking-[0.12em] text-charcoal/70">Live log</span>
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto p-3">
        {events.length === 0 ? (
          <p className="text-xs text-charcoal/50">Nothing has happened yet.</p>
        ) : (
          events.map((event, i) => (
            <div key={`${event.ts}-${i}`} className="flex items-start gap-2 text-xs">
              <span className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${EVENT_DOT[event.type]}`} />
              <div className="min-w-0">
                <div className="text-[10px] tabular-nums text-charcoal/45">{formatTime(event.ts)}</div>
                <div className="text-charcoal/80">{event.message}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
