import { useTranslation } from "../../i18n/useTranslation";

// Estas llaves son EXACTAMENTE las de PERIOD_TO_TIMEDELTA en
// backend/app/db/repository.py — no inventar una nueva sin agregarla alla.
const PERIOD_KEYS = ["dia", "semana", "1_mes", "3_meses", "6_meses", "1_anio"] as const;

interface Props {
  value: string;
  onChange: (period: string) => void;
}

export function TimeFilterSelector({ value, onChange }: Props) {
  const { t } = useTranslation();

  return (
    <div className="animate-fade-up flex flex-wrap gap-1.5" style={{ animationDelay: "60ms" }}>
      {PERIOD_KEYS.map((key) => (
        <button
          key={key}
          onClick={() => onChange(key)}
          aria-pressed={value === key}
          className={`rounded-full px-3.5 py-1.5 text-[13px] font-medium transition duration-300 ease-out active:scale-[0.97] ${
            value === key
              ? "bg-plum text-paper shadow-[0_6px_16px_-8px_rgba(104,73,89,0.9)]"
              : "bg-paper/80 text-charcoal/75 ring-1 ring-plum/10 hover:bg-paper hover:text-ink hover:ring-plum/25"
          }`}
        >
          {t(`period.${key}`)}
        </button>
      ))}
    </div>
  );
}
