import { useState } from "react";

import { simulationApi } from "../../services/api";
import { useAppStore } from "../../state/store";
import type { PendingOrder } from "../../types";

// Aqui es donde el conductor decide, no el agente: el Score ya viene
// calculado por el agente inteligente (should_accept es solo una
// recomendacion), pero aceptar o rechazar cada oferta es siempre del
// usuario — por eso cada pedido se queda "pendiente" hasta que el
// conductor elige, en vez de resolverse solo.
export function PendingOrdersPanel() {
  const simulation = useAppStore((s) => s.simulation);
  const setSimulation = useAppStore((s) => s.setSimulation);
  const [decidingId, setDecidingId] = useState<string | null>(null);

  const orders = simulation?.pending_orders ?? [];
  if (orders.length === 0) return null;

  async function decide(order: PendingOrder, accept: boolean) {
    if (!simulation) return;
    setDecidingId(order.order_id);
    try {
      const { data } = await simulationApi.decide({
        run_id: simulation.run_id,
        order_id: order.order_id,
        accept,
      });
      setSimulation(data);
    } finally {
      setDecidingId(null);
    }
  }

  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-6 z-10 flex flex-col items-center gap-2">
      {orders.map((order, i) => (
        <div
          key={order.order_id}
          className="animate-pop-in pointer-events-auto flex w-full max-w-md items-center gap-3 rounded-xl border border-dust bg-paper/95 p-3 shadow-[0_8px_24px_rgba(104,73,89,0.18)] backdrop-blur"
          style={{ animationDelay: `${i * 60}ms` }}
        >
          <span
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-paper ${
              order.should_accept ? "bg-plum" : "bg-charcoal/60"
            }`}
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor">
              <path d="M4 8h16l-1.4 11.1a2 2 0 0 1-2 1.9H7.4a2 2 0 0 1-2-1.9L4 8Z" />
              <path d="M8 8V6a4 4 0 0 1 8 0v2" fill="none" stroke="currentColor" strokeWidth="2" />
            </svg>
          </span>

          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium text-ink">{order.pickup_name ?? "New order"}</div>
            <div className="text-xs text-charcoal/60">
              {order.distance_km.toFixed(1)} km · {order.time_minutes.toFixed(0)} min · Score{" "}
              <span className={order.score >= 0 ? "text-plum" : "text-charcoal/60"}>
                ${order.score.toFixed(2)}
              </span>
            </div>
          </div>

          <button
            onClick={() => decide(order, false)}
            disabled={decidingId === order.order_id}
            className="rounded-full border border-dust bg-white px-3 py-1.5 text-xs font-medium text-charcoal transition duration-150 ease-out hover:border-plum/30 hover:bg-dust/30 active:scale-95 disabled:opacity-50"
          >
            Reject
          </button>
          <button
            onClick={() => decide(order, true)}
            disabled={decidingId === order.order_id}
            className="rounded-full bg-plum px-3 py-1.5 text-xs font-medium text-paper shadow-[0_2px_8px_rgba(104,73,89,0.35)] transition duration-150 ease-out hover:bg-charcoal active:scale-95 disabled:opacity-50"
          >
            Accept
          </button>
        </div>
      ))}
    </div>
  );
}
