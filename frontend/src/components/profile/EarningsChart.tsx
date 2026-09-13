import { useMemo } from "react";
import { Area, AreaChart, CartesianGrid, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { useTranslation } from "../../i18n/useTranslation";
import type { HistoryPoint } from "../../types";

interface Props {
  data: HistoryPoint[];
}

function formatDate(iso: string, locale: string): string {
  if (iso.includes("T")) {
    const d = new Date(iso);
    return new Intl.DateTimeFormat(locale, { hour: "numeric" }).format(d);
  }
  // `T00:00:00` fija la hora a mediodia local... en realidad a medianoche,
  // pero evita que `new Date("2026-01-01")` (que Date.parse interpreta como
  // UTC medianoche) se corra un dia hacia atras en husos horarios negativos
  // (Mexico) al formatearla en hora local.
  const d = new Date(`${iso}T12:00:00`);
  return new Intl.DateTimeFormat(locale, { month: "short", day: "numeric" }).format(d);
}

// TODO: totals por dia ya vienen del backend (statsApi.getHistory) — este
// componente solo dibuja lo que le llega.
export function EarningsChart({ data }: Props) {
  const { t, language } = useTranslation();
  const locale = language === "es" ? "es-MX" : "en-US";

  // Rejilla de ticks adaptativa: un año son 365 puntos diarios, y ponerle una
  // etiqueta a cada uno los vuelve ilegibles. Con esto se muestran ~8 parejo
  // repartidas sin importar el largo del rango.
  const tickInterval = Math.max(Math.floor(data.length / 8), 0);

  const formatted = useMemo(
    () => data.map((p) => ({ ...p, label: formatDate(p.date, locale) })),
    [data, locale],
  );

  if (data.length === 0) {
    return (
      <div className="flex h-[280px] flex-col items-center justify-center gap-1.5 rounded-2xl bg-dust/15 text-center ring-1 ring-plum/10">
        <span className="text-[13px] text-charcoal/75">{t("profile.chart.empty.title")}</span>
        <span className="max-w-[36ch] text-[12px] leading-relaxed text-charcoal/50">
          {t("profile.chart.empty.body")}
        </span>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <AreaChart data={formatted}>
        <defs>
          <linearGradient id="earningsFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#E5CAD9" stopOpacity={0.65} />
            <stop offset="95%" stopColor="#E5CAD9" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#D8CCCA" strokeOpacity={0.6} strokeDasharray="2 6" vertical={false} />
        {/* Ejes sin linea propia: la rejilla ya da la referencia, y dos trazos
            para lo mismo ensucian un area chart. */}
        <XAxis
          dataKey="label"
          axisLine={false}
          tickLine={false}
          stroke="#3E3D41"
          tick={{ fontSize: 11, fill: "#3E3D41", opacity: 0.6 }}
          interval={tickInterval}
          dy={6}
        />
        <YAxis
          axisLine={false}
          tickLine={false}
          stroke="#3E3D41"
          tick={{ fontSize: 11, fill: "#3E3D41", opacity: 0.6 }}
          width={44}
        />
        <Tooltip
          cursor={{ stroke: "#684959", strokeOpacity: 0.25, strokeWidth: 1 }}
          contentStyle={{
            background: "#FAF6F3",
            border: "none",
            borderRadius: 14,
            // Sombra tintada en plum, no negro: misma luz que el resto de la app.
            boxShadow: "0 16px 34px -16px rgba(104,73,89,0.55)",
            fontSize: 12,
          }}
          labelStyle={{ color: "#18151A", fontWeight: 600 }}
          formatter={(value: number, key: string) => [
            `$${value.toFixed(2)} MXN`,
            key === "noviceNetEarnings" ? t("profile.chart.novice") : t("profile.chart.smart"),
          ]}
        />
        <Area
          type="monotone"
          dataKey="netEarnings"
          name={t("profile.chart.smart")}
          stroke="#684959"
          strokeWidth={2.5}
          fill="url(#earningsFill)"
          dot={false}
        />
        {/* El novato va como linea punteada, sin relleno: dos areas solidas
            encimadas se ven turbias, y la comparacion importa mas que el
            volumen bajo la curva del novato. */}
        <Line
          type="monotone"
          dataKey="noviceNetEarnings"
          name={t("profile.chart.novice")}
          stroke="#3E3D41"
          strokeOpacity={0.55}
          strokeWidth={1.75}
          strokeDasharray="4 4"
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
