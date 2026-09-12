const PERIODS = [
  { key: "dia", label: "Día" },
  { key: "semana", label: "Semana" },
  { key: "1_mes", label: "1 Mes" },
  { key: "3_meses", label: "3 Meses" },
  { key: "6_meses", label: "6 Meses" },
  { key: "1_anio", label: "1 Año" },
];

interface Props {
  value: string;
  onChange: (period: string) => void;
}

export function TimeFilterSelector({ value, onChange }: Props) {
  return (
    <div className="flex gap-1">
      {PERIODS.map((p) => (
        <button
          key={p.key}
          onClick={() => onChange(p.key)}
          className={`rounded-md px-3 py-1 text-sm ${
            value === p.key ? "bg-emerald-500 text-black" : "bg-neutral-800 text-neutral-200"
          }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}
