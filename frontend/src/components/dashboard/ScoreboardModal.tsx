import { useEffect } from "react";

import { useTranslation } from "../../i18n/useTranslation";

interface Props {
  open: boolean;
  onClose: () => void;
  intelligentEarnings: number;
  noviceEarnings: number;
}

export function ScoreboardModal({ open, onClose, intelligentEarnings, noviceEarnings }: Props) {
  const { t } = useTranslation();

  // Escape cierra. Antes el unico modo de salir era el boton: si el foco se
  // perdia, el modal se volvia una trampa.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  // Lo "ahorrado": la ventaja del agente sobre el novato que corrio el MISMO
  // stream de ordenes (mismo session_id). Es la cifra que justifica el
  // producto, asi que va como titular y no como resta implicita.
  const saved = intelligentEarnings - noviceEarnings;
  const ahead = saved >= 0;

  return (
    <div
      className="animate-fade-in fixed inset-0 z-modal flex items-center justify-center bg-ink/35 px-4 backdrop-blur-md"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="scoreboard-title"
        onClick={(e) => e.stopPropagation()}
        className="animate-pop-in w-full max-w-sm rounded-[2rem] bg-paper/70 p-1.5 shadow-[0_30px_64px_-24px_rgba(24,21,26,0.65)] ring-1 ring-plum/15 backdrop-blur-xl"
      >
        <div className="rounded-[calc(2rem-0.375rem)] bg-paper/95 p-6 shadow-[inset_0_1px_1px_rgba(255,255,255,0.7)]">
          <span className="text-[10px] font-medium uppercase tracking-[0.2em] text-plum/70">
            {t("scoreboard.eyebrow")}
          </span>
          <h2 id="scoreboard-title" className="mt-1.5 text-xl font-semibold tracking-tight text-ink">
            {t("scoreboard.title")}
          </h2>

          <div className="mt-5 rounded-2xl bg-gradient-to-br from-blush/40 via-dust/20 to-transparent px-4 py-3">
            <div className="text-[10px] uppercase tracking-[0.16em] text-charcoal/55">
              {ahead ? t("scoreboard.ahead") : t("scoreboard.behind")}
            </div>
            <div
              className={`text-3xl font-semibold leading-none tracking-[-0.02em] tabular-nums ${
                ahead ? "text-plum" : "text-charcoal/70"
              }`}
            >
              {ahead ? "+" : "−"}${Math.abs(saved).toFixed(2)}
              <span className="ml-1.5 text-sm font-normal text-charcoal/55">MXN</span>
            </div>
          </div>

          <dl className="mt-4 divide-y divide-dust/60">
            <div className="flex items-baseline justify-between py-2.5">
              <dt className="text-[13px] text-ink">{t("scoreboard.smart")}</dt>
              <dd className="text-sm font-semibold tabular-nums text-plum">
                ${intelligentEarnings.toFixed(2)}
              </dd>
            </div>
            <div className="flex items-baseline justify-between py-2.5">
              <dt className="text-[13px] text-charcoal/75">{t("scoreboard.novice")}</dt>
              <dd className="text-sm tabular-nums text-charcoal/70">${noviceEarnings.toFixed(2)}</dd>
            </div>
          </dl>

          <button
            onClick={onClose}
            autoFocus
            className="mt-5 w-full rounded-full bg-paper/80 py-2 text-[13px] font-medium text-charcoal/75 ring-1 ring-plum/10 transition duration-300 ease-out hover:bg-paper hover:text-ink hover:ring-plum/25 active:scale-[0.98]"
          >
            {t("scoreboard.close")}
          </button>
        </div>
      </div>
    </div>
  );
}
