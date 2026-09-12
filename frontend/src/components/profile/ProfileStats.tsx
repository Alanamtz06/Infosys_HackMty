import { useState } from "react";

import { EarningsChart, type EarningsPoint } from "./EarningsChart";
import { TimeFilterSelector } from "./TimeFilterSelector";

// TODO: reemplazar por datos reales de statsApi.getHistory(period)
const MOCK_DATA: EarningsPoint[] = [];

export function ProfileStats() {
  const [period, setPeriod] = useState("semana");

  return (
    <div className="space-y-4 p-6 text-neutral-100">
      <h2 className="text-xl font-semibold">Perfil del Repartidor</h2>
      <TimeFilterSelector value={period} onChange={setPeriod} />
      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Ganancias netas" value="$0.00" />
        <StatCard label="Gasolina ahorrada" value="0.0 L" />
        <StatCard label="Tiempo ahorrado" value="0 min" />
      </div>
      <EarningsChart data={MOCK_DATA} />
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-neutral-900 p-4">
      <div className="text-sm text-neutral-400">{label}</div>
      <div className="text-2xl font-semibold text-emerald-400">{value}</div>
    </div>
  );
}
