import { useEffect, useState } from "react";

import { EarningsChart } from "../components/profile/EarningsChart";
import { TimeFilterSelector } from "../components/profile/TimeFilterSelector";
import { useTranslation } from "../i18n/useTranslation";
import { statsApi } from "../services/api";
import type { HistoryResponse, LiveDashboardResponse, LiveDashboardSummary } from "../types";

const POLL_INTERVAL_MS = 4000;

export function DashboardPage() {
  const { t } = useTranslation();
  const [data, setData] = useState<LiveDashboardResponse | null>(null);
  const [error, setError] = useState(false);
  // Distingue "todavia no se sabe" de "se sabe y no hay nada": sin esto, el
  // primer render afirmaba "sin actividad en los ultimos 5 minutos" antes de
  // haber preguntado — una afirmacion falsa sobre datos que aun no llegaban.
  const [loading, setLoading] = useState(true);

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
      } finally {
        if (!cancelled) setLoading(false);
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
    <div className="mx-auto min-h-full w-full max-w-6xl space-y-7 px-5 py-8 text-ink lg:px-8 lg:py-10">
      <header className="animate-fade-up">
        <span className="text-[10px] font-medium uppercase tracking-[0.2em] text-plum/70">
          {t("dashboard.eyebrow")}
        </span>
        <div className="mt-2 flex items-center gap-3">
          <h2 className="text-2xl font-semibold tracking-[-0.02em] sm:text-3xl">{t("dashboard.title")}</h2>
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-plum" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-plum" />
          </span>
        </div>
        <p className="mt-2 max-w-[58ch] text-[13px] leading-relaxed text-charcoal/70">
          {t("dashboard.description")}
        </p>
      </header>

      {error && (
        <p
          role="alert"
          className="animate-fade-up rounded-2xl bg-blush/25 px-4 py-3 text-[13px] text-plum ring-1 ring-plum/20"
        >
          {t("dashboard.error", { seconds: POLL_INTERVAL_MS / 1000 })}
        </p>
      )}

      <SummaryGrid data={data} loading={loading} />
      <TrendsSection />
      <RecentTrips data={data} loading={loading} />
    </div>
  );
}

// Esqueletos con la FORMA de las tarjetas que van a llegar (incluida la
// asimetria), no un spinner: la pagina no cambia de alto al resolver y nada
// salta bajo el cursor.
function SummarySkeleton() {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-hidden="true">
      {[true, false, false].map((lead, i) => (
        <div
          key={i}
          className={`rounded-[1.5rem] p-1.5 ring-1 ring-plum/10 ${lead ? "bg-paper/70 sm:col-span-2" : "bg-paper/50"}`}
        >
          <div className="space-y-3 rounded-[calc(1.5rem-0.375rem)] bg-paper/95 p-4">
            <div className="h-2.5 w-1/3 animate-pulse rounded-full bg-dust/70" />
            <div className="h-6 w-2/3 animate-pulse rounded-full bg-dust/50" />
          </div>
        </div>
      ))}
    </div>
  );
}

function SummaryGrid({ data, loading }: { data: LiveDashboardResponse | null; loading: boolean }) {
  const { t } = useTranslation();
  const rows = data?.summary ?? [];

  const isActive = data?.is_active ?? false;

  if (loading && rows.length === 0) return <SummarySkeleton />;

  if (rows.length === 0) {
    return (
      <div
        className="animate-fade-up rounded-[1.75rem] bg-paper/60 p-1.5 ring-1 ring-plum/10"
        style={{ animationDelay: "80ms" }}
      >
        <div className="flex flex-col items-center justify-center gap-1.5 rounded-[calc(1.75rem-0.375rem)] bg-paper/90 px-6 py-10 text-center shadow-[inset_0_1px_1px_rgba(255,255,255,0.6)]">
          <span className="text-sm text-charcoal/75">{t("dashboard.summary.empty.title")}</span>
          <span className="max-w-[38ch] text-[12px] leading-relaxed text-charcoal/50">
            {t("dashboard.summary.empty.body")}
          </span>
        </div>
      </div>
    );
  }

  return (
    // Rejilla asimetrica a proposito: el agente inteligente ocupa el doble de
    // ancho porque es el sujeto de la comparacion — el novato es la linea base
    // contra la que se mide, no un igual. Tres columnas iguales contarian que
    // los dos pesan lo mismo.
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {rows.map((row, i) => (
        <SummaryCard key={`${row.agent_type}-${row.vehicle}`} row={row} index={i} isActive={isActive} />
      ))}
    </div>
  );
}

function SummaryCard({ row, index, isActive }: { row: LiveDashboardSummary; index: number; isActive: boolean }) {
  const { t } = useTranslation();
  const isSmart = row.agent_type === "inteligente";

  return (
    <article
      className={`animate-fade-up group rounded-[1.5rem] p-1.5 ring-1 transition duration-500 ease-out ${
        isSmart
          ? "bg-paper/70 shadow-[0_18px_38px_-20px_rgba(104,73,89,0.5)] ring-plum/15 sm:col-span-2"
          : "bg-paper/50 ring-plum/10"
      }`}
      style={{ animationDelay: `${index * 70}ms` }}
    >
      <div className="h-full rounded-[calc(1.5rem-0.375rem)] bg-paper/95 p-4 shadow-[inset_0_1px_1px_rgba(255,255,255,0.6)]">
        <div className="flex items-center justify-between gap-2">
          <span className="text-[13px] font-medium text-ink">
            {isSmart ? t("dashboard.agent.smart") : t("dashboard.agent.novice")}
            <span className="ml-1.5 text-charcoal/50">{row.vehicle}</span>
          </span>
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.12em] ${
              isSmart ? "bg-plum text-paper" : "bg-dust/50 text-charcoal/65"
            }`}
          >
            {isActive ? t("dashboard.summary.currentShift") : t("dashboard.summary.pastShift")}
          </span>
        </div>

        <div className={`mt-3 grid gap-3 ${isSmart ? "grid-cols-4" : "grid-cols-2"}`}>
          <Stat label={t("dashboard.summary.trips")} value={row.trips.toString()} />
          <Stat label={t("dashboard.summary.accepted")} value={row.accepted.toString()} />
          <Stat label={t("dashboard.summary.netScore")} value={`$${row.net_score.toFixed(2)}`} accent />
          <Stat label={t("dashboard.summary.avg")} value={`$${row.avg_score.toFixed(2)}`} />
        </div>
      </div>
    </article>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-[0.14em] text-charcoal/50">{label}</div>
      <div
        className={`mt-0.5 text-[15px] font-semibold tabular-nums tracking-[-0.01em] ${
          accent ? "text-plum" : "text-ink"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

/** Tendencia historica: inteligente vs novato sobre el MISMO stream, dia por
 * dia. Reusa EarningsChart/TimeFilterSelector (misma forma de dato, mismo
 * endpoint /stats/history/{period}) — antes vivian en el Perfil, se movieron
 * aqui porque son estadisticas del NEGOCIO (el turno, el flujo de ordenes),
 * no del repartidor individual. Las tres tarjetas de totales comparten el
 * mismo selector de periodo que el grafico: un solo control, no dos filtros
 * diciendo cosas distintas en la misma pantalla.
 */
function TrendsSection() {
  const { t } = useTranslation();
  const [period, setPeriod] = useState("dia");
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function poll() {
      try {
        const { data } = await statsApi.getHistory(period);
        if (!cancelled) setHistory(data);
      } catch {
        if (!cancelled) setHistory(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [period]);

  const points = history?.points ?? [];
  const totals = history?.totals ?? null;
  const hasData = points.length > 0;

  const stats = [
    { label: t("profile.stat.netEarnings"), value: `$${(totals?.netEarnings ?? 0).toFixed(2)}`, lead: true },
    { label: t("profile.stat.fuelSaved"), value: `$${(totals?.gasSaved ?? 0).toFixed(2)}`, lead: false },
    { label: t("profile.stat.timeSaved"), value: `${(totals?.timeSaved ?? 0).toFixed(0)} min`, lead: false },
  ];

  return (
    <section
      className="animate-fade-up rounded-[1.75rem] bg-paper/60 p-1.5 ring-1 ring-plum/10"
      style={{ animationDelay: "120ms" }}
    >
      <div className="rounded-[calc(1.75rem-0.375rem)] bg-paper/95 p-5 shadow-[inset_0_1px_1px_rgba(255,255,255,0.6)]">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <span className="text-[10px] font-medium uppercase tracking-[0.2em] text-plum/70">
              {t("dashboard.trends.title")}
            </span>
            <p className="mt-1 max-w-[46ch] text-[12px] leading-relaxed text-charcoal/60">
              {t("dashboard.trends.description")}
            </p>
          </div>
          <TimeFilterSelector value={period} onChange={setPeriod} />
        </div>

        {/* Bento asimetrico: las ganancias netas pesan el doble que los
            ahorros derivados, porque es la cifra que decide si el turno
            valio la pena. */}
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((stat, i) => (
            <TotalStatCard
              key={stat.label}
              label={stat.label}
              value={stat.value}
              lead={stat.lead}
              hasData={hasData}
              loading={loading}
              delayMs={i * 60}
            />
          ))}
        </div>

        <div className="mt-4">
          {loading && points.length === 0 ? (
            <div className="flex h-[280px] items-end gap-2 px-1" aria-hidden="true">
              {Array.from({ length: 14 }).map((_, i) => (
                <div
                  key={i}
                  className="flex-1 animate-pulse rounded-t-md bg-dust/50"
                  style={{ height: `${28 + ((i * 41) % 55)}%` }}
                />
              ))}
            </div>
          ) : (
            <EarningsChart data={points} />
          )}
        </div>
      </div>
    </section>
  );
}

function TotalStatCard({
  label,
  value,
  lead,
  hasData,
  loading,
  delayMs,
}: {
  label: string;
  value: string;
  lead: boolean;
  hasData: boolean;
  loading: boolean;
  delayMs: number;
}) {
  return (
    <article
      className={`animate-fade-up rounded-[1.5rem] p-1.5 ring-1 transition duration-500 ease-out ${
        lead
          ? "bg-paper/70 shadow-[0_18px_38px_-20px_rgba(104,73,89,0.5)] ring-plum/15 sm:col-span-2"
          : "bg-paper/50 ring-plum/10"
      }`}
      style={{ animationDelay: `${delayMs}ms` }}
    >
      <div className="h-full rounded-[calc(1.5rem-0.375rem)] bg-paper/95 p-4 shadow-[inset_0_1px_1px_rgba(255,255,255,0.6)]">
        <div className="text-[10px] uppercase tracking-[0.14em] text-charcoal/50">{label}</div>
        {loading ? (
          <div className={`mt-1.5 animate-pulse rounded-full bg-dust/50 ${lead ? "h-8 w-28" : "h-6 w-16"}`} />
        ) : (
          <div
            className={`mt-1 font-semibold tabular-nums tracking-[-0.02em] ${lead ? "text-3xl" : "text-2xl"} ${
              hasData ? (lead ? "text-plum" : "text-ink") : "text-charcoal/35"
            }`}
          >
            {hasData ? value : "—"}
          </div>
        )}
      </div>
    </article>
  );
}

function RecentTrips({ data, loading }: { data: LiveDashboardResponse | null; loading: boolean }) {
  const { t } = useTranslation();
  const trips = data?.recent_trips ?? [];

  return (
    <section
      className="animate-fade-up rounded-[1.75rem] bg-paper/60 p-1.5 ring-1 ring-plum/10"
      style={{ animationDelay: "200ms" }}
    >
      <div className="overflow-hidden rounded-[calc(1.75rem-0.375rem)] bg-paper/95 shadow-[inset_0_1px_1px_rgba(255,255,255,0.6)]">
        <header className="px-5 pb-2.5 pt-4">
          <span className="text-[10px] font-medium uppercase tracking-[0.2em] text-plum/70">
            {t("dashboard.recentTrips.title")}
          </span>
          <p className="mt-1 text-[12px] text-charcoal/60">{t("dashboard.recentTrips.description")}</p>
        </header>

        {loading && trips.length === 0 ? (
          <div className="space-y-2.5 px-5 pb-5 pt-2" aria-hidden="true">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-2.5 animate-pulse rounded-full bg-dust/60" style={{ width: `${92 - i * 14}%` }} />
            ))}
          </div>
        ) : trips.length === 0 ? (
          <p className="px-5 pb-6 pt-2 text-[13px] text-charcoal/50">{t("dashboard.recentTrips.empty")}</p>
        ) : (
          // Solo la tabla scrollea en horizontal, nunca la pagina.
          <div className="overflow-x-auto">
            <div className="min-w-[560px] divide-y divide-dust/50">
              {trips.map((trip) => (
                <div
                  key={trip.id}
                  className="flex items-center gap-4 px-5 py-2.5 text-[13px] transition-colors duration-300 ease-out hover:bg-dust/20"
                >
                  <span
                    className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                      trip.accepted ? "bg-plum" : "bg-transparent ring-1 ring-charcoal/35"
                    }`}
                  />
                  <span className="w-14 shrink-0 capitalize text-charcoal/70">{trip.vehicle}</span>
                  <span className="w-20 shrink-0 text-charcoal/70">
                    {trip.agent_type === "inteligente" ? t("dashboard.agent.smart") : t("dashboard.agent.novice")}
                  </span>
                  <span className="flex-1 truncate text-charcoal/55">{trip.username ?? "—"}</span>
                  <span className="w-20 shrink-0 tabular-nums text-charcoal/70">
                    {trip.distance_km.toFixed(1)} km
                  </span>
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
          </div>
        )}
      </div>
    </section>
  );
}
