import { useTranslation } from "../../i18n/useTranslation";
import { translateStopLabel } from "../../lib/stopLabel";
import type { PendingOrder, RoutePreview } from "../../types";

interface Props {
  order: PendingOrder;
  route: RoutePreview | null;
  loading: boolean;
  error: string | null;
  deciding: boolean;
  onAccept: () => void;
  onReject: () => void;
  onBack: () => void;
}

function Row({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "neutral" | "gain" | "cost" | "total";
}) {
  const valueTone =
    tone === "gain"
      ? "text-ink"
      : tone === "cost"
        ? "text-charcoal/60"
        : tone === "total"
          ? "font-semibold text-plum"
          : "text-ink";

  return (
    <div className="flex items-baseline justify-between gap-3 py-[5px]">
      <span className="text-[11px] text-charcoal/65">{label}</span>
      <span className={`text-xs tabular-nums ${valueTone}`}>{value}</span>
    </div>
  );
}

// Marcador de carga con la FORMA del contenido que va a llegar, no un spinner:
// la tarjeta no cambia de alto cuando responde la ruta, asi que nada salta.
function LegSkeleton() {
  return (
    <div className="space-y-2 py-1" aria-hidden="true">
      <div className="h-2.5 w-3/4 animate-pulse rounded-full bg-dust/70" />
      <div className="h-2.5 w-2/3 animate-pulse rounded-full bg-dust/50" />
    </div>
  );
}

/**
 * Contenido de detalle de una oferta seleccionada — SIN marco propio: vive
 * dentro de `DraggableWidget` (via OrdersWidget), que ya pone el doble bisel,
 * el titulo y el boton de cerrar el panel entero. El control "back" de aqui
 * es otra cosa: vuelve a la lista de dos columnas, no oculta el widget.
 *
 * Muestra el desglose del Score con el mismo signo con el que cada termino
 * entra a la formula (la tarifa suma, gasolina y tiempo restan), y una franja
 * con el veredicto del novato para la MISMA orden — la comparacion que pide
 * el panel dividido tambien aplica aqui, no solo en la lista.
 */
export function OrderDetailCard({ order, route, loading, error, deciding, onAccept, onReject, onBack }: Props) {
  const { t } = useTranslation();
  const worthIt = order.score >= 0;
  const novice = order.novice;

  return (
    <div className="p-4">
      <button
        onClick={onBack}
        className="flex items-center gap-1 text-[10px] font-medium uppercase tracking-[0.2em] text-plum/70 transition duration-200 ease-out hover:text-plum"
      >
        <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" aria-hidden="true">
          <path d="M15 6 9 12l6 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        {t("orderDetail.eyebrow")}
      </button>

      <div className="mt-1.5 flex items-center gap-2">
        <h2 className="min-w-0 flex-1 truncate text-[15px] font-semibold leading-tight tracking-tight text-ink">
          {order.pickup_name ?? t("orderDetail.newOrder")}
        </h2>
        <span className="shrink-0 rounded-full bg-dust/50 px-2 py-0.5 text-[10px] font-medium text-charcoal/60">
          {order.zone}
        </span>
      </div>

      {/* El numero que decide, con su veredicto al lado. */}
      <div className="mt-3 flex items-end justify-between gap-3 rounded-2xl bg-gradient-to-br from-blush/35 via-dust/20 to-transparent px-3 py-2.5">
        <div>
          <div className="text-[10px] uppercase tracking-[0.16em] text-charcoal/55">{t("orderDetail.score")}</div>
          <div
            className={`text-2xl font-semibold leading-none tracking-tight tabular-nums ${
              worthIt ? "text-plum" : "text-charcoal/70"
            }`}
          >
            ${order.score.toFixed(2)}
          </div>
        </div>
        <span
          className={`rounded-full px-2.5 py-1 text-[10px] font-medium tracking-wide ${
            order.should_accept ? "bg-plum text-paper" : "bg-paper text-charcoal/70 ring-1 ring-dust"
          }`}
        >
          {order.should_accept ? t("orderDetail.agentTakesIt") : t("orderDetail.agentSkips")}
        </span>
      </div>

      {/* Comparacion con el novato para esta MISMA orden — mismo dato que
          alimenta la columna derecha de la lista, aqui en una franja. */}
      <div className="mt-2 flex items-center justify-between gap-2 rounded-xl bg-dust/25 px-3 py-1.5">
        <span className="text-[10px] uppercase tracking-[0.14em] text-charcoal/50">
          {t("orderDetail.compareNovice")}
        </span>
        {novice.outcome === "accepted" ? (
          <span className="text-xs tabular-nums text-charcoal/70">${(novice.score ?? 0).toFixed(2)}</span>
        ) : (
          <span className="text-[11px] text-charcoal/50">
            {novice.outcome === "busy" ? t("orders.novice.busy") : t("orders.novice.unreachable")}
          </span>
        )}
      </div>

      <div className="mt-3 divide-y divide-dust/60">
        <div>
          <Row label={t("orderDetail.fare")} value={`+ $${order.fare.toFixed(2)}`} tone="gain" />
          <Row
            label={`${t("orderDetail.fuel")} · ${order.distance_km.toFixed(1)} km`}
            value={`− $${order.gas_cost.toFixed(2)}`}
            tone="cost"
          />
          <Row
            label={`${t("orderDetail.time")} · ${order.time_minutes.toFixed(0)} min`}
            value={`− $${order.time_cost.toFixed(2)}`}
            tone="cost"
          />
        </div>
        <div>
          <Row label={t("orderDetail.netEarnings")} value={`$${order.score.toFixed(2)}`} tone="total" />
        </div>
      </div>

      {/* Las paradas en orden de visita, con el ETA acumulado de cada una. */}
      <div className="mt-3 border-t border-dust/60 pt-3">
        <span className="text-[10px] font-medium uppercase tracking-[0.18em] text-charcoal/45">
          {t("orderDetail.route")}
        </span>

        {loading && !route && <LegSkeleton />}

        {error && <p className="mt-1.5 text-[11px] leading-snug text-charcoal/70">{error}</p>}

        {route && (
          <ol className="mt-1.5 space-y-1.5">
            {route.stops.map((stop, i) => (
              <li
                key={`${stop.kind}-${i}`}
                className="animate-fade-up flex items-baseline gap-2"
                style={{ animationDelay: `${i * 70}ms` }}
              >
                <span className="mt-[3px] flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-dust/60 text-[9px] font-semibold tabular-nums text-plum">
                  {i}
                </span>
                <span className="min-w-0 flex-1 truncate text-[11px] text-ink">
                  {translateStopLabel(stop, order.pickup_name, t)}
                </span>
                <span className="shrink-0 text-[10px] tabular-nums text-charcoal/55">
                  {stop.eta_minutes > 0 ? `${stop.eta_minutes.toFixed(0)} ${t("orderDetail.min")}` : t("orderDetail.now")}
                </span>
              </li>
            ))}
          </ol>
        )}
      </div>

      <div className="mt-4 flex items-center gap-2">
        <button
          onClick={onAccept}
          disabled={deciding}
          className="group flex flex-1 items-center justify-between gap-2 rounded-full bg-plum py-1.5 pl-4 pr-1.5 text-xs font-medium text-paper shadow-[0_6px_16px_-6px_rgba(104,73,89,0.9)] transition duration-300 ease-out hover:bg-ink active:scale-[0.98] disabled:opacity-50"
        >
          {deciding ? t("orderDetail.accepting") : t("orderDetail.accept")}
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-paper/15 transition duration-300 ease-out group-hover:-translate-y-[1px] group-hover:translate-x-[2px] group-hover:scale-105">
            <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" aria-hidden="true">
              <path
                d="M7 17 17 7M9 7h8v8"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
        </button>

        <button
          onClick={onReject}
          disabled={deciding}
          className="rounded-full px-3 py-2 text-xs font-medium text-charcoal/70 transition duration-200 ease-out hover:bg-dust/40 hover:text-ink active:scale-95 disabled:opacity-50"
        >
          {t("orderDetail.reject")}
        </button>
      </div>
    </div>
  );
}
