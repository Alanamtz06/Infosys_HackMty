import { useState } from "react";

import { useAppStore } from "../../state/store";
import { EarningsChart, type EarningsPoint } from "./EarningsChart";
import { TimeFilterSelector } from "./TimeFilterSelector";

// Datos de muestra temporales solo para previsualizar el diseño de la
// gráfica y las tarjetas mientras no hay conexión real al backend.
// TODO: reemplazar por datos reales de statsApi.getHistory(period) y quitar
// este arreglo en cuanto el endpoint este disponible.
const SAMPLE_DATA: EarningsPoint[] = [
  { date: "Lun", netEarnings: 184.3, gasSaved: 2.1, timeSaved: 18 },
  { date: "Mar", netEarnings: 221.75, gasSaved: 2.6, timeSaved: 24 },
  { date: "Mié", netEarnings: 156.9, gasSaved: 1.8, timeSaved: 15 },
  { date: "Jue", netEarnings: 268.4, gasSaved: 3.2, timeSaved: 29 },
  { date: "Vie", netEarnings: 312.15, gasSaved: 3.9, timeSaved: 34 },
  { date: "Sáb", netEarnings: 289.6, gasSaved: 3.4, timeSaved: 31 },
  { date: "Dom", netEarnings: 198.25, gasSaved: 2.3, timeSaved: 20 },
];

const totals = SAMPLE_DATA.reduce(
  (acc, point) => ({
    netEarnings: acc.netEarnings + point.netEarnings,
    gasSaved: acc.gasSaved + point.gasSaved,
    timeSaved: acc.timeSaved + point.timeSaved,
  }),
  { netEarnings: 0, gasSaved: 0, timeSaved: 0 },
);

const STATS = [
  { label: "Ganancias netas", value: `$${totals.netEarnings.toFixed(2)}`, accent: "plum" as const },
  { label: "Gasolina ahorrada", value: `${totals.gasSaved.toFixed(1)} L`, accent: "blush" as const },
  { label: "Tiempo ahorrado", value: `${totals.timeSaved} min`, accent: "charcoal" as const },
];

export function ProfileStats() {
  const [period, setPeriod] = useState("semana");
  const hasData = SAMPLE_DATA.length > 0;
  const user = useAppStore((s) => s.user);

  return (
    <div className="space-y-5 p-6 text-ink">
      <div className="animate-fade-up flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-plum text-paper shadow-[0_2px_8px_rgba(104,73,89,0.35)]">
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor">
              <circle cx="12" cy="8.4" r="3.3" />
              <path d="M4.6 20.2c0-4.5 3.3-7.6 7.4-7.6s7.4 3.1 7.4 7.6a1 1 0 0 1-1 1H5.6a1 1 0 0 1-1-1Z" />
            </svg>
          </span>
          <div>
            <span className="inline-block rounded-full bg-blush/40 px-2.5 py-0.5 text-[10px] font-medium uppercase tracking-[0.15em] text-plum">
              Resumen
            </span>
            <h2 className="text-xl font-semibold tracking-tight">
              {user ? `Hola, ${user.username}` : "Perfil del repartidor"}
            </h2>
          </div>
        </div>

        {user && (
          <span className="flex items-center gap-1.5 rounded-full border border-dust bg-white px-3 py-1.5 text-xs font-medium text-charcoal">
            <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 text-plum" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              {user.vehicle_type === "moto" ? (
                <>
                  <circle cx="5.5" cy="17.5" r="3.5" />
                  <circle cx="18.5" cy="17.5" r="3.5" />
                  <path d="M15 6h4l-1 4.5M11 17.5h4l-3-8H8l-1.5 3M15 10.5H9" />
                </>
              ) : (
                <>
                  <path d="M5 17h14M6 17V9.5L8 5h8l2 4.5V17" />
                  <circle cx="8" cy="17" r="1.6" />
                  <circle cx="16" cy="17" r="1.6" />
                </>
              )}
            </svg>
            {user.vehicle_type === "moto" ? "Moto" : "Auto"} · ${user.vehicle_type === "moto" ? "0.80" : "2.00"}/km
          </span>
        )}
      </div>

      <TimeFilterSelector value={period} onChange={setPeriod} />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {STATS.map((stat, i) => (
          <StatCard
            key={stat.label}
            label={stat.label}
            value={stat.value}
            accent={stat.accent}
            hasData={hasData}
            delayMs={i * 80}
          />
        ))}
      </div>

      <div
        className="animate-fade-up rounded-xl border border-dust bg-gradient-to-br from-white via-white to-blush/15 p-4"
        style={{ animationDelay: "240ms" }}
      >
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium text-charcoal">Ganancias netas · esta semana</span>
          <span className="h-2 w-2 rounded-full bg-plum" />
        </div>
        <EarningsChart data={SAMPLE_DATA} />
      </div>
    </div>
  );
}

const ACCENT_BAR: Record<"plum" | "blush" | "charcoal", string> = {
  plum: "bg-plum",
  blush: "bg-blush",
  charcoal: "bg-charcoal",
};

const ACCENT_VALUE: Record<"plum" | "blush" | "charcoal", string> = {
  plum: "text-plum",
  blush: "text-plum",
  charcoal: "text-charcoal",
};

function StatCard({
  label,
  value,
  accent,
  hasData,
  delayMs,
}: {
  label: string;
  value: string;
  accent: "plum" | "blush" | "charcoal";
  hasData: boolean;
  delayMs: number;
}) {
  return (
    <div
      className="animate-fade-up overflow-hidden rounded-lg border border-dust bg-white transition duration-150 ease-out hover:border-plum/30 hover:shadow-[0_4px_14px_rgba(104,73,89,0.12)]"
      style={{ animationDelay: `${delayMs}ms` }}
    >
      <span className={`block h-1 w-full ${ACCENT_BAR[accent]}`} />
      <div className="p-4">
        <div className="text-sm text-charcoal/80">{label}</div>
        <div
          className={`text-2xl font-semibold tabular-nums ${hasData ? ACCENT_VALUE[accent] : "text-charcoal/40"}`}
        >
          {hasData ? value : "—"}
        </div>
      </div>
    </div>
  );
}
