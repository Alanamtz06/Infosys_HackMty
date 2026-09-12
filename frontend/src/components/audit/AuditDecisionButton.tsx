import { useState } from "react";

import { auditApi } from "../../services/api";
import { AuditExplanationCard } from "./AuditExplanationCard";

interface Props {
  orderId: string;
}

export function AuditDecisionButton({ orderId }: Props) {
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
        className="rounded-md bg-plum px-3 py-1.5 text-sm font-medium text-paper shadow-[0_2px_8px_rgba(104,73,89,0.35)] transition duration-150 ease-out hover:bg-charcoal active:scale-95 disabled:opacity-50 disabled:shadow-none"
      >
        {loading ? "Auditing..." : "Audit decision"}
      </button>
      {explanation && <AuditExplanationCard text={explanation} />}
    </div>
  );
}
