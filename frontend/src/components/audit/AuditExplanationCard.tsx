interface Props {
  text: string;
}

export function AuditExplanationCard({ text }: Props) {
  return (
    <div className="max-w-md rounded-lg border border-indigo-500/30 bg-indigo-500/10 p-3 text-sm text-neutral-100">
      {text}
    </div>
  );
}
