import { useEffect, useState } from "react";

import { EarningsChart } from "../components/profile/EarningsChart";
import { TimeFilterSelector } from "../components/profile/TimeFilterSelector";
import { useTranslation } from "../i18n/useTranslation";
import { simulationApi, statsApi } from "../services/api";
import { useAppStore } from "../state/store";
import type {
  AgentBenchmark,
  BenchmarkResult,
  HistoryResponse,
  LiveDashboardResponse,
  LiveDashboardSummary,
} from "../types";

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
      <BenchmarkPanel
        liveRate={data?.is_active ? (data.summary.find((r) => r.agent_type === "inteligente")?.earnings_per_hour ?? null) : null}
      />
      <TrendsSection />
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
    // ancho porque es el sujeto de la comparacion — novato y autonomo son las
    // dos lineas base contra las que se mide (aceptar todo vs. la misma
    // politica sin humano en el loop), no un tercer igual. Por eso van del
    // mismo ancho entre ellas, la mitad del inteligente.
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
  const label =
    row.agent_type === "inteligente"
      ? t("dashboard.agent.smart")
      : row.agent_type === "autonomo"
        ? t("dashboard.agent.autonomous")
        : t("dashboard.agent.novice");

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
            {label}
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

        <div className={`mt-3 grid gap-3 ${isSmart ? "grid-cols-3" : "grid-cols-2"}`}>
          <Stat label={t("dashboard.summary.trips")} value={row.trips.toString()} />
          <Stat label={t("dashboard.summary.accepted")} value={row.accepted.toString()} />
          <Stat
            label={t("dashboard.summary.acceptanceRate")}
            value={`${Math.round(row.acceptance_rate * 100)}%`}
          />
          <Stat label={t("dashboard.summary.netScore")} value={`$${row.net_score.toFixed(2)}`} accent />
          <Stat label={t("dashboard.summary.avg")} value={`$${row.avg_score.toFixed(2)}`} />
          <Stat
            label={t("dashboard.summary.perHour")}
            value={`$${row.earnings_per_hour.toFixed(2)}`}
            accent={isSmart}
          />
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

const BENCHMARK_HOURS_OPTIONS = [4, 8, 12] as const;

/** Comparacion de los TRES agentes: el turno asistido (humano + recomendacion,
 * ya en pantalla en SummaryGrid), el novato (baseline, ambos lados) y el
 * autonomo (misma decision/policy.py pero SIN humano en el loop, corrida bajo
 * demanda via /simulation/benchmark sobre un stream nuevo — no interfiere con
 * ningun turno en curso). Comparar totales entre columnas seria enganoso
 * (streams y duraciones distintas), asi que la unica cifra que cruza las tres
 * es MXN/hora — la misma tasa que decision/policy.py usa para aceptar/
 * rechazar — mientras que aceptados/rechazados/distancia se muestran solo
 * autonomo-vs-novato, que si comparten el mismo stream.
 */
function BenchmarkPanel({ liveRate }: { liveRate: number | null }) {
  const { t } = useTranslation();
  const user = useAppStore((s) => s.user);
  const [hours, setHours] = useState<number>(8);
  const [result, setResult] = useState<BenchmarkResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  async function runBenchmark() {
    setLoading(true);
    setError(false);
    try {
      const { data } = await simulationApi.benchmark({ hours, vehicle: user?.vehicle_type ?? "moto" });
      setResult(data);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  const rateRows: { key: string; label: string; value: number | null }[] = result
    ? [
        { key: "assisted", label: t("dashboard.benchmark.assisted"), value: liveRate },
        { key: "autonomous", label: t("dashboard.agent.autonomous"), value: result.inteligente.earnings_per_hour },
        { key: "novice", label: t("dashboard.agent.novice"), value: result.novato.earnings_per_hour },
      ]
    : [];
  const maxRate = Math.max(1, ...rateRows.map((r) => r.value ?? 0));

  return (
    <section
      className="animate-fade-up rounded-[1.75rem] bg-paper/60 p-1.5 ring-1 ring-plum/10"
      style={{ animationDelay: "100ms" }}
    >
      <div className="rounded-[calc(1.75rem-0.375rem)] bg-paper/95 p-5 shadow-[inset_0_1px_1px_rgba(255,255,255,0.6)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <span className="text-[10px] font-medium uppercase tracking-[0.2em] text-plum/70">
              {t("dashboard.benchmark.eyebrow")}
            </span>
            <h3 className="mt-1 text-[15px] font-semibold tracking-[-0.01em] text-ink">
              {t("dashboard.benchmark.title")}
            </h3>
            <p className="mt-1.5 max-w-[54ch] text-[12px] leading-relaxed text-charcoal/60">
              {t("dashboard.benchmark.description")}
            </p>
          </div>

          <div className="flex shrink-0 flex-col items-end gap-2">
            <div className="flex gap-1.5">
              {BENCHMARK_HOURS_OPTIONS.map((h) => (
                <button
                  key={h}
                  onClick={() => setHours(h)}
                  aria-pressed={hours === h}
                  className={`rounded-full px-3 py-1 text-[12px] font-medium transition duration-300 ease-out active:scale-[0.97] ${
                    hours === h
                      ? "bg-plum text-paper shadow-[0_6px_16px_-8px_rgba(104,73,89,0.9)]"
                      : "bg-paper/80 text-charcoal/75 ring-1 ring-plum/10 hover:bg-paper hover:text-ink hover:ring-plum/25"
                  }`}
                >
                  {t("dashboard.benchmark.hoursValue", { hours: h })}
                </button>
              ))}
            </div>
            <button
              onClick={runBenchmark}
              disabled={loading}
              className="group flex items-center gap-1.5 rounded-full bg-plum py-1 pl-3 pr-1 text-[12px] font-medium text-paper shadow-[0_6px_16px_-8px_rgba(104,73,89,0.9)] transition duration-300 ease-out hover:bg-plum/90 active:scale-[0.98] disabled:opacity-50"
            >
              {loading
                ? t("dashboard.benchmark.running")
                : result
                  ? t("dashboard.benchmark.rerun")
                  : t("dashboard.benchmark.run")}
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-paper/15 transition duration-300 ease-out group-hover:-translate-y-[1px] group-hover:translate-x-[2px] group-hover:scale-105">
                <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" aria-hidden="true">
                  <path
                    d="M5 12h13M13 6.5 18.5 12 13 17.5"
                    stroke="currentColor"
                    strokeWidth="1.7"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
            </button>
          </div>
        </div>

        {error && (
          <p
            role="alert"
            className="mt-4 rounded-2xl bg-blush/25 px-4 py-3 text-[13px] text-plum ring-1 ring-plum/20"
          >
            {t("dashboard.benchmark.error")}
          </p>
        )}

        {loading && !result && (
          <div className="mt-5 space-y-2.5" aria-hidden="true">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-2.5 animate-pulse rounded-full bg-dust/60" style={{ width: `${88 - i * 16}%` }} />
            ))}
          </div>
        )}

        {result && (
          <div className="mt-5 animate-fade-up space-y-5">
            <div>
              <div className="space-y-2.5">
                {rateRows.map((r) =>
                  r.value != null ? (
                    <RateBar key={r.key} label={r.label} value={r.value} max={maxRate} />
                  ) : (
                    <div key={r.key} className="flex items-center gap-3">
                      <span className="w-28 shrink-0 text-[12px] text-charcoal/65">{r.label}</span>
                      <span className="text-[11px] italic text-charcoal/40">
                        {t("dashboard.benchmark.assistedEmpty")}
                      </span>
                    </div>
                  ),
                )}
              </div>
              <p className="mt-2.5 text-[11px] leading-relaxed text-charcoal/45">
                {t("dashboard.benchmark.rateNote")}
              </p>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <BenchmarkAgentCard label={t("dashboard.agent.autonomous")} data={result.inteligente} lead />
              <BenchmarkAgentCard label={t("dashboard.agent.novice")} data={result.novato} lead={false} />
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-dust/50 pt-3.5 text-[12px] text-charcoal/60">
              <span>
                {t("dashboard.benchmark.detail.orders", {
                  count: result.orders_offered,
                  hours: result.hours,
                  start: result.start_hour,
                })}
              </span>
              <span className={`font-semibold tabular-nums ${result.advantage_mxn >= 0 ? "text-plum" : "text-charcoal/60"}`}>
                {t("dashboard.benchmark.advantage", {
                  mxn: result.advantage_mxn.toFixed(2),
                  pct: result.advantage_pct.toFixed(1),
                })}
              </span>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function RateBar({ label, value, max }: { label: string; value: number; max: number }) {
  const width = Math.max(4, (Math.max(value, 0) / max) * 100);
  return (
    <div className="flex items-center gap-3">
      <span className="w-28 shrink-0 text-[12px] text-charcoal/65">{label}</span>
      <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-dust/40">
        <div
          className="h-full rounded-full bg-plum transition-[width] duration-500 ease-out"
          style={{ width: `${width}%` }}
        />
      </div>
      <span className="w-20 shrink-0 text-right text-[13px] font-semibold tabular-nums text-ink">
        ${value.toFixed(2)}
      </span>
    </div>
  );
}

function BenchmarkAgentCard({ label, data, lead }: { label: string; data: AgentBenchmark; lead: boolean }) {
  const { t } = useTranslation();
  return (
    <div
      className={`rounded-[1.25rem] p-1.5 ring-1 ${
        lead ? "bg-paper/70 shadow-[0_14px_30px_-20px_rgba(104,73,89,0.5)] ring-plum/15" : "bg-paper/50 ring-plum/10"
      }`}
    >
      <div className="rounded-[calc(1.25rem-0.375rem)] bg-paper/95 p-3.5 shadow-[inset_0_1px_1px_rgba(255,255,255,0.6)]">
        <span className="text-[12px] font-medium text-ink">{label}</span>
        <div className="mt-2.5 grid grid-cols-2 gap-2.5">
          <Stat label={t("dashboard.benchmark.detail.accepted")} value={data.accepted.toString()} accent={lead} />
          <Stat label={t("dashboard.benchmark.detail.rejected")} value={data.rejected.toString()} />
          <Stat label={t("dashboard.benchmark.detail.missed")} value={data.missed_while_busy.toString()} />
          <Stat label={t("dashboard.benchmark.detail.distance")} value={`${data.distance_km.toFixed(1)} km`} />
        </div>
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
      style={{ animationDelay: "180ms" }}
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

