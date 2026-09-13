import { Marker } from "react-map-gl/maplibre";

import type { RouteStop } from "../../types";

interface Props {
  stop: RouteStop;
  /** Posicion en el recorrido: 0 es el punto de partida. */
  index: number;
  /** Muestra el nombre y el ETA junto al punto. */
  detailed?: boolean;
  /** Escalona la entrada para que las paradas aparezcan en orden de visita. */
  delayMs?: number;
  dimmed?: boolean;
  /** Sustituye `stop.label` (que el backend manda fijo en ingles) por texto
   * ya traducido — ver lib/stopLabel.ts. Si no se pasa, cae al de la API. */
  label?: string;
}

function PickupGlyph() {
  return (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" aria-hidden="true">
      <path
        d="M5.5 8.5h13l-1 10.2a1.8 1.8 0 0 1-1.8 1.6H8.3a1.8 1.8 0 0 1-1.8-1.6L5.5 8.5Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="M9 8.5V6.8a3 3 0 0 1 6 0v1.7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function DropoffGlyph() {
  return (
    <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" aria-hidden="true">
      <path
        d="M12 21s6.4-5.3 6.4-10A6.4 6.4 0 0 0 5.6 11c0 4.7 6.4 10 6.4 10Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <circle cx="12" cy="10.6" r="2.2" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function StartGlyph() {
  return (
    <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="4.6" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}

// El recorrido se lee por forma y por orden, no solo por color: relleno lleno
// para donde hay que ir, contorno para donde ya se esta. Asi sigue siendo
// legible sobre el duotono del mapa y para quien no distingue plum de blush.
const STYLES: Record<RouteStop["kind"], { core: string; glyph: JSX.Element }> = {
  courier: {
    core: "bg-paper text-plum ring-1 ring-plum/35",
    glyph: <StartGlyph />,
  },
  pickup: {
    core: "bg-blush text-plum ring-1 ring-plum/25",
    glyph: <PickupGlyph />,
  },
  dropoff: {
    core: "bg-plum text-paper",
    glyph: <DropoffGlyph />,
  },
};

export function StopMarker({ stop, index, detailed = false, delayMs = 0, dimmed = false, label }: Props) {
  const style = STYLES[stop.kind];

  return (
    <Marker latitude={stop.lat} longitude={stop.lon}>
      <div
        className={`animate-pop-in flex flex-col items-center font-sans transition-opacity duration-300 ease-out ${
          dimmed ? "opacity-45" : "opacity-100"
        }`}
        style={{ animationDelay: `${delayMs}ms` }}
      >
        <div className="relative rounded-full bg-paper/80 p-[3px] shadow-[0_4px_12px_-2px_rgba(104,73,89,0.45)] backdrop-blur-sm">
          <div
            className={`flex h-7 w-7 items-center justify-center rounded-full shadow-[inset_0_1px_1px_rgba(250,246,243,0.3)] ${style.core}`}
          >
            {style.glyph}
          </div>

          {/* El orden de visita, pegado al punto. Sin esto, dos paradas
              parecidas no dicen cual va primero. */}
          {index > 0 && (
            <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-ink text-[9px] font-semibold tabular-nums text-paper ring-2 ring-paper">
              {index}
            </span>
          )}
        </div>

        {detailed && (
          <span className="animate-fade-up mt-1.5 max-w-[9.5rem] truncate rounded-full bg-paper/95 px-2 py-[3px] text-[10px] font-medium text-ink shadow-sm ring-1 ring-plum/10 backdrop-blur">
            {label ?? stop.label}
            {stop.eta_minutes > 0 && (
              <span className="ml-1 tabular-nums text-charcoal/55">{stop.eta_minutes.toFixed(0)}m</span>
            )}
          </span>
        )}
      </div>
    </Marker>
  );
}
