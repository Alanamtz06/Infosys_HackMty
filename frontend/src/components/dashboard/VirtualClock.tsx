interface Props {
  virtualHour: number;
}

export function VirtualClock({ virtualHour }: Props) {
  const hours = Math.floor(virtualHour);
  const minutes = Math.round((virtualHour - hours) * 60);
  const label = `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}`;

  return (
    <div className="flex items-center gap-2 rounded-lg border border-dust bg-white px-4 py-2 font-mono text-lg tabular-nums text-ink">
      <span className="relative flex h-2 w-2">
        <span className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-plum" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-plum" />
      </span>
      {label}
    </div>
  );
}
