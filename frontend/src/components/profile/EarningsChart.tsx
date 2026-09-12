import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export interface EarningsPoint {
  date: string;
  netEarnings: number;
  gasSaved: number;
  timeSaved: number;
}

interface Props {
  data: EarningsPoint[];
}

// TODO: alimentar con app.db.repository.get_trips_since via /stats/history/{period}
export function EarningsChart({ data }: Props) {
  if (data.length === 0) {
    return (
      <div className="flex h-[280px] flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-dust bg-dust/10 text-charcoal/70">
        <span className="text-sm">Todavía no hay viajes registrados en este periodo.</span>
        <span className="text-xs text-charcoal/50">
          El historial aparecerá aquí cuando el repartidor complete su primera entrega.
        </span>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="earningsFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#E5CAD9" stopOpacity={0.65} />
            <stop offset="95%" stopColor="#E5CAD9" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#D8CCCA" strokeDasharray="3 5" vertical={false} />
        <XAxis dataKey="date" stroke="#3E3D41" tick={{ fontSize: 12 }} />
        <YAxis stroke="#3E3D41" tick={{ fontSize: 12 }} />
        <Tooltip
          contentStyle={{ background: "#FAF6F3", border: "1px solid #D8CCCA", borderRadius: 8 }}
          labelStyle={{ color: "#18151A" }}
        />
        <Area
          type="monotone"
          dataKey="netEarnings"
          stroke="#684959"
          strokeWidth={2.5}
          fill="url(#earningsFill)"
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
