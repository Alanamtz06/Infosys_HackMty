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
        className="rounded-md bg-indigo-500 px-3 py-1.5 text-sm text-white hover:bg-indigo-400 disabled:opacity-50"
      >
        {loading ? "Auditando..." : "Auditar Decisión"}
      </button>
      {explanation && <AuditExplanationCard text={explanation} />}
    </div>
  );
}
