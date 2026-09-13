import { useTranslation } from "../../i18n/useTranslation";

interface Props {
  text: string;
}

export function AuditExplanationCard({ text }: Props) {
  const { t } = useTranslation();

  return (
    <div className="animate-fade-up max-w-md rounded-[1.5rem] bg-paper/60 p-1.5 ring-1 ring-plum/10">
      <div className="rounded-[calc(1.5rem-0.375rem)] bg-gradient-to-br from-blush/35 via-dust/15 to-transparent p-4 shadow-[inset_0_1px_1px_rgba(255,255,255,0.6)]">
        <span className="text-[10px] font-medium uppercase tracking-[0.2em] text-plum/70">
          {t("audit.why")}
        </span>
        {/* `text` viene del backend (Gemini o el fallback deterministico en
            gemini_service.py), siempre en ingles — no hay i18n de este lado
            que pueda traducirlo sin volver a llamar al modelo con otro idioma. */}
        <p className="mt-1.5 text-[13px] leading-relaxed text-ink">{text}</p>
      </div>
    </div>
  );
}
