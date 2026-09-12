import { useEffect, useState } from "react";

import { statsApi } from "../services/api";
import type { LiveDashboardResponse } from "../types";

const POLL_INTERVAL_MS = 4000;

export function DashboardPage() {
  const [data, setData] = useState<LiveDashboardResponse | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const { data: response } = await statsApi.getLive();
        if (!cancelled) {
          setData(response);
          setError(false);
        }
      } catch {
        if (!cancelled) setError(true);
      }
    }

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="min-h-screen space-y-5 p-6 text-ink">
      <div className="animate-fade-up flex items-center gap-3">
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-plum" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-plum" />
        </span>
        <h2 className="text-xl font-semibold tracking-tight">Dashboard en vivo</h2>
        <span className="rounded-full bg-dust/40 px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-[0.15em] text-charcoal/70">
          Tiger Data
        </span>
      </div>

      {error && (
        <div className="animate-fade-up rounded-lg border border-dust bg-dust/20 px-4 py-3 text-sm text-charcoal/70">
          No se pudo conectar con el backend. Reintentando cada {POLL_INTERVAL_MS / 1000}s…
        </div>
      )}

      <SummaryGrid data={data} />
      <RecentTrips data={data} />
    </div>
  );
}

function SummaryGrid({ data }: { data: LiveDashboardResponse | null }) {
  const rows = data?.summary ?? [];

  if (rows.length === 0) {
    return (
      <div
        className="animate-fade-up flex h-28 flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-dust bg-dust/10 text-charcoal/70"
        style={{ animationDelay: "80ms" }}
      >
        <span className="text-sm">Sin actividad en los últimos 5 minutos.</span>
        <span className="text-xs text-charcoal/50">
          Corre una simulación para ver el Score calculado en vivo por Tiger Data.
        </span>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {rows.map((row, i) => (
        <div
          key={`${row.agent_type}-${row.vehicle}`}
          className="animate-fade-up overflow-hidden rounded-lg border border-dust bg-white transition duration-150 ease-out hover:border-plum/30 hover:shadow-[0_4px_14px_rgba(104,73,89,0.12)]"
          style={{ animationDelay: `${i * 70}ms` }}
        >
          <span className="block h-1 w-full bg-gradient-to-r from-plum via-blush to-dust" />
          <div className="p-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-medium capitalize text-ink">
                {row.agent_type} · {row.vehicle}
              </span>
              <span className="rounded-full bg-blush/30 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-plum">
                5 min
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <Stat label="Viajes" value={row.trips_last_5min.toString()} />
              <Stat label="Aceptados" value={row.accepted_last_5min.toString()} />
              <Stat label="Score neto" value={`$${row.net_score_last_5min.toFixed(2)}`} accent />
              <Stat label="Score prom." value={`$${row.avg_score_last_5min.toFixed(2)}`} />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <div className="text-[11px] text-charcoal/60">{label}</div>
      <div className={`font-semibold tabular-nums ${accent ? "text-plum" : "text-ink"}`}>{value}</div>
    </div>
  );
}

function RecentTrips({ data }: { data: LiveDashboardResponse | null }) {
  const trips = data?.recent_trips ?? [];

  return (
    <div className="animate-fade-up rounded-xl border border-dust bg-white" style={{ animationDelay: "160ms" }}>
      <div className="border-b border-dust px-4 py-3 text-sm font-medium text-charcoal">
        Últimos viajes (calculados por <code className="text-plum">calculate_score()</code> en Postgres)
      </div>

      {trips.length === 0 ? (
        <div className="flex h-24 items-center justify-center text-sm text-charcoal/50">
          Todavía no hay viajes registrados.
        </div>
      ) : (
        <div className="divide-y divide-dust overflow-x-auto">
          {trips.map((trip) => (
            <div
              key={trip.id}
              className="flex min-w-[560px] items-center gap-4 px-4 py-2.5 text-sm transition-colors hover:bg-dust/15"
            >
              <span
                className={`h-2 w-2 shrink-0 rounded-full ${trip.accepted ? "bg-plum" : "bg-charcoal/30"}`}
                title={trip.accepted ? "Aceptado" : "Rechazado"}
              />
              <span className="w-16 shrink-0 capitalize text-charcoal/70">{trip.vehicle}</span>
              <span className="w-24 shrink-0 capitalize text-charcoal/70">{trip.agent_type}</span>
              <span className="flex-1 truncate text-charcoal/60">{trip.username ?? "—"}</span>
              <span className="w-20 shrink-0 tabular-nums text-charcoal/70">{trip.distance_km.toFixed(1)} km</span>
              <span className="w-24 shrink-0 tabular-nums text-charcoal/70">
                ${trip.gas_cost_live.toFixed(2)} gas
              </span>
              <span
                className={`w-24 shrink-0 text-right font-semibold tabular-nums ${
                  trip.score_live >= 0 ? "text-plum" : "text-charcoal/50"
                }`}
              >
                ${trip.score_live.toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
