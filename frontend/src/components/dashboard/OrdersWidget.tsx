import { useTranslation } from "../../i18n/useTranslation";
import { groupByZone } from "../../lib/zoneGroups";
import { OrderDetailCard } from "../map/OrderDetailCard";
import { DraggableWidget } from "../widgets/DraggableWidget";
import { useAppStore } from "../../state/store";
import type { PendingOrder, RoutePreview } from "../../types";

interface Props {
  route: RoutePreview | null;
  loadingRoute: boolean;
  routeError: string | null;
  deciding: boolean;
  onAccept: () => void;
  onReject: () => void;
}

function NoviceCell({ order }: { order: PendingOrder }) {
  const { t } = useTranslation();
  const novice = order.novice;

  if (novice.outcome === "accepted") {
    return (
      <div className="rounded-xl bg-dust/30 px-2 py-1.5 text-center">
        <div className="text-[9px] uppercase tracking-[0.12em] text-charcoal/45">{t("orders.col.novice")}</div>
        <div className="text-[13px] font-semibold tabular-nums text-charcoal/70">${(novice.score ?? 0).toFixed(0)}</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center rounded-xl bg-dust/20 px-2 py-1.5 text-center">
      <div className="text-[9px] uppercase tracking-[0.12em] text-charcoal/45">{t("orders.col.novice")}</div>
      <div className="text-[11px] text-charcoal/50">
        {novice.outcome === "busy" ? t("orders.novice.busy") : t("orders.novice.unreachable")}
      </div>
    </div>
  );
}

function SmartCell({ order }: { order: PendingOrder }) {
  const { t } = useTranslation();
  const worthIt = order.score >= 0;

  return (
    <div
      className={`rounded-xl px-2 py-1.5 text-center transition duration-300 ease-out ${
        order.should_accept ? "bg-plum/90" : "bg-charcoal/15"
      }`}
    >
      <div
        className={`text-[9px] uppercase tracking-[0.12em] ${order.should_accept ? "text-paper/70" : "text-charcoal/50"}`}
      >
        {t("orders.col.smart")}
      </div>
      <div
        className={`text-[13px] font-semibold tabular-nums ${
          order.should_accept ? "text-paper" : worthIt ? "text-ink" : "text-charcoal/70"
        }`}
      >
        ${order.score.toFixed(0)}
      </div>
    </div>
  );
}

function OrderRow({
  order,
  index,
  selected,
  onSelect,
}: {
  order: PendingOrder;
  index: number;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <li>
      <button
        onClick={onSelect}
        aria-pressed={selected}
        className={`animate-fade-up group flex w-full flex-col gap-1.5 rounded-[1.05rem] px-2.5 py-2 text-left transition duration-300 ease-out ${
          selected
            ? "bg-paper shadow-[0_6px_18px_-10px_rgba(104,73,89,0.7)] ring-1 ring-plum/25"
            : "ring-1 ring-transparent hover:bg-paper/70 hover:ring-plum/10"
        }`}
        style={{ animationDelay: `${index * 55}ms` }}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="min-w-0 flex-1 truncate text-[13px] font-medium leading-tight text-ink">
            {order.pickup_name ?? "—"}
          </span>
          <span className="shrink-0 text-[10px] tabular-nums text-charcoal/50">
            {order.distance_km.toFixed(1)} km · {order.time_minutes.toFixed(0)} min
          </span>
        </div>

        {/* La comparacion: mismo pedido, dos veredictos lado a lado. */}
        <div className="grid grid-cols-2 gap-1.5">
          <SmartCell order={order} />
          <NoviceCell order={order} />
        </div>
      </button>
    </li>
  );
}

function ZoneGroupHeader({ zone, count }: { zone: string; count: number }) {
  return (
    <div className="flex items-center gap-2 px-2.5 pb-1 pt-2 first:pt-0">
      <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-charcoal/50">{zone}</span>
      <span className="rounded-full bg-dust/50 px-1.5 py-[1px] text-[9px] font-semibold tabular-nums text-charcoal/55">
        {count}
      </span>
      <span className="h-px flex-1 bg-dust/50" />
    </div>
  );
}

function EmptyState() {
  const { t } = useTranslation();
  return (
    <div className="flex items-center gap-3 px-2.5 py-3">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-dust/50 text-plum/70">
        <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="7.5" stroke="currentColor" strokeWidth="1.4" />
          <path d="M12 8.4v4l2.4 1.6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
      </span>
      <p className="text-[11px] leading-snug text-charcoal/60">
        {t("orders.empty.title")}
        <br />
        {t("orders.empty.body")}
      </p>
    </div>
  );
}

/**
 * Panel flotante de ofertas: lista comparativa (inteligente | novato) o,
 * cuando hay una seleccionada, el detalle completo de esa orden — las dos
 * vistas viven en el MISMO widget arrastrable/cerrable, por eso ya no puede
 * traslaparse con nada mas (antes `OrderDetailCard` flotaba aparte, arriba a
 * la izquierda, y esta lista abajo a la izquierda; en una ventana baja las
 * dos podian tocarse).
 */
export function OrdersWidget({ route, loadingRoute, routeError, deciding, onAccept, onReject }: Props) {
  const { t } = useTranslation();
  const simulation = useAppStore((s) => s.simulation);
  const selectedOrderId = useAppStore((s) => s.selectedOrderId);
  const setSelectedOrderId = useAppStore((s) => s.setSelectedOrderId);

  const orders = simulation?.pending_orders ?? [];
  const activeRoutes = simulation?.active_routes ?? [];
  const isActive = simulation !== null && !simulation.is_finished;

  if (!isActive) return null;

  const selectedOrder = orders.find((o) => o.order_id === selectedOrderId) ?? null;
  const current = activeRoutes.find((r) => r.is_current);

  const title = selectedOrder ? t("orderDetail.eyebrow") : t("orders.title");

  return (
    <DraggableWidget
      id="orders"
      title={title}
      anchorClassName="bottom-5 left-4"
      width="w-[23rem]"
      headerRight={
        !selectedOrder ? (
          <span className="flex items-center gap-1.5 text-[10px] tabular-nums text-charcoal/50">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-plum" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-plum" />
            </span>
            {t("orders.live", { count: orders.length })}
          </span>
        ) : undefined
      }
    >
      {selectedOrder ? (
        <OrderDetailCard
          order={selectedOrder}
          route={route}
          loading={loadingRoute}
          error={routeError}
          deciding={deciding}
          onAccept={onAccept}
          onReject={onReject}
          onBack={() => setSelectedOrderId(null)}
        />
      ) : (
        <>
          {orders.length === 0 ? (
            <EmptyState />
          ) : (
            <div className="max-h-[19rem] overflow-y-auto px-1.5 pb-1.5">
              {groupByZone(orders).map((group) => (
                <div key={group.zone}>
                  <ZoneGroupHeader zone={group.zone} count={group.orders.length} />
                  <ol className="space-y-1">
                    {group.orders.map((order, i) => (
                      <OrderRow
                        key={order.order_id}
                        order={order}
                        index={i}
                        selected={order.order_id === selectedOrderId}
                        onSelect={() => setSelectedOrderId(order.order_id)}
                      />
                    ))}
                  </ol>
                </div>
              ))}
            </div>
          )}

          {current && (
            <footer className="flex items-center justify-between gap-2 border-t border-dust/60 px-4 py-2">
              <span className="min-w-0 truncate text-[11px] text-charcoal/65">
                {current.phase === "to_pickup" ? t("orders.heading.to") : t("orders.delivering")}
                <span className="text-ink">{current.pickup_name ?? t("orders.theOrder")}</span>
              </span>
              <span className="shrink-0 text-[11px] font-medium tabular-nums text-plum">
                {current.eta_minutes.toFixed(0)} min
              </span>
            </footer>
          )}
        </>
      )}
    </DraggableWidget>
  );
}
