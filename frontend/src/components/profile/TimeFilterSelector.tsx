const PERIODS = [
  { key: "dia", label: "Day" },
  { key: "semana", label: "Week" },
  { key: "1_mes", label: "1 Month" },
  { key: "3_meses", label: "3 Months" },
  { key: "6_meses", label: "6 Months" },
  { key: "1_anio", label: "1 Year" },
];

interface Props {
  value: string;
  onChange: (period: string) => void;
}

export function TimeFilterSelector({ value, onChange }: Props) {
  return (
    <div className="animate-fade-up flex flex-wrap gap-1" style={{ animationDelay: "60ms" }}>
      {PERIODS.map((p) => (
        <button
          key={p.key}
          onClick={() => onChange(p.key)}
          className={`rounded-full border px-3 py-1 text-sm font-medium transition duration-150 ease-out active:scale-95 ${
            value === p.key
              ? "border-plum bg-plum text-paper shadow-[0_2px_8px_rgba(104,73,89,0.35)]"
              : "border-dust bg-white text-charcoal hover:border-plum/30 hover:bg-blush/25"
          }`}
        >
          {p.label}
        </button>
      ))}
    </div>
  );
}
