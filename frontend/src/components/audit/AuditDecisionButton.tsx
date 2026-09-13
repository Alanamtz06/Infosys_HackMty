import { useState } from "react";

import { useTranslation } from "../../i18n/useTranslation";
import { auditApi } from "../../services/api";
import { AuditExplanationCard } from "./AuditExplanationCard";

interface Props {
  orderId: string;
}

export function AuditDecisionButton({ orderId }: Props) {
  const { t } = useTranslation();
  const [explanation, setExplanation] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleAudit() {
    setLoading(true);
    try {
      const { data } = await auditApi.auditDecision(orderId);
      setExplanation(data.explanation);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-2">
      <button
        onClick={handleAudit}
        disabled={loading}
        className="group flex items-center gap-2 rounded-full bg-plum py-1.5 pl-4 pr-1.5 text-[13px] font-medium text-paper shadow-[0_10px_24px_-10px_rgba(104,73,89,0.95)] transition duration-300 ease-out hover:bg-ink active:scale-[0.98] disabled:opacity-50 disabled:shadow-none"
      >
        {loading ? t("audit.loading") : t("audit.button")}
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-paper/15 transition duration-300 ease-out group-hover:-translate-y-[1px] group-hover:translate-x-[2px] group-hover:scale-105">
          <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" aria-hidden="true">
            <path
              d="M5 12h13M13 6.5 18.5 12 13 17.5"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
      </button>
      {explanation && <AuditExplanationCard text={explanation} />}
    </div>
  );
}
