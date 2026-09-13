import { useTranslation } from "../../i18n/useTranslation";
import { useAppStore } from "../../state/store";
import type { SimEvent } from "../../types";
import { DraggableWidget } from "../widgets/DraggableWidget";

// Cada tipo de evento se distingue por forma ademas de color: relleno solido
// para lo que suma, contorno para lo que se dejo pasar. Sobre el duotono del
// mapa, el color solo no alcanza.
const EVENT_DOT: Record<SimEvent["type"], string> = {
  shift_started: "bg-plum",
  shift_ended: "bg-charcoal",
  order_generated: "bg-paper ring-1 ring-plum/40",
  order_accepted: "bg-plum",
  order_rejected: "bg-transparent ring-1 ring-charcoal/35",
};

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// Log en vivo de lo que hace el backend: cada tick de /simulation/state
// puede generar una orden, y cada decision del conductor queda registrada
// aqui con su hora SIMULADA (la del mundo, no la del servidor) para que se
// lea como una bitacora de verdad y no como un contador.
export function LiveLog() {
  const { t } = useTranslation();
  const simulation = useAppStore((s) => s.simulation);
  const events = simulation?.events ?? [];
  const isRunning = simulation !== null && !simulation.is_finished;

  if (!isRunning) return null;

  return (
    <DraggableWidget
      id="liveLog"
      title={t("liveLog.title")}
      anchorClassName="right-6 top-6"
      width="w-72"
      headerRight={
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-plum" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-plum" />
        </span>
      }
    >
      <div className="flex max-h-[calc(100vh-14rem)] min-h-0 flex-col">
        <div className="min-h-0 flex-1 space-y-2 overflow-y-auto px-4 pb-3 pt-1">
          {events.length === 0 ? (
            <p className="text-[11px] leading-snug text-charcoal/55">{t("liveLog.empty")}</p>
          ) : (
            events.map((event, i) => (
              <div key={`${event.ts}-${i}`} className="flex items-start gap-2">
                <span className={`mt-[5px] h-1.5 w-1.5 shrink-0 rounded-full ${EVENT_DOT[event.type]}`} />
                <div className="min-w-0">
                  <div className="text-[10px] tabular-nums text-charcoal/45">{formatTime(event.ts)}</div>
                  <div className="text-[11px] leading-snug text-charcoal/80">{event.message}</div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </DraggableWidget>
  );
}
