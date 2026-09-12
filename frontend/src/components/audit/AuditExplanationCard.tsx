interface Props {
  text: string;
}

export function AuditExplanationCard({ text }: Props) {
  return (
    <div className="animate-fade-up max-w-md rounded-lg border border-plum/25 bg-blush/20 p-3 text-sm text-ink">
      {text}
    </div>
  );
}
