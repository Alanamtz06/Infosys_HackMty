import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

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
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data}>
        <XAxis dataKey="date" stroke="#a3a3a3" />
        <YAxis stroke="#a3a3a3" />
        <Tooltip contentStyle={{ background: "#171717", border: "none" }} />
        <Line type="monotone" dataKey="netEarnings" stroke="#34d399" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
