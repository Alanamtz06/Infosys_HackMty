interface Props {
  virtualHour: number;
}

export function VirtualClock({ virtualHour }: Props) {
  const hours = Math.floor(virtualHour);
  const minutes = Math.round((virtualHour - hours) * 60);
  const label = `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}`;

  const isDay = virtualHour >= 6 && virtualHour < 18;

  return (
    <div className="flex items-center gap-2 px-2">
      {isDay ? (
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-amber-500">
          <circle cx="12" cy="12" r="4"></circle>
          <path d="M12 2v2"></path>
          <path d="M12 20v2"></path>
          <path d="m4.93 4.93 1.41 1.41"></path>
          <path d="m17.66 17.66 1.41 1.41"></path>
          <path d="M2 12h2"></path>
          <path d="M20 12h2"></path>
          <path d="m6.34 17.66-1.41 1.41"></path>
          <path d="m19.07 4.93-1.41 1.41"></path>
        </svg>
      ) : (
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-indigo-400">
          <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"></path>
        </svg>
      )}
      <span className="text-sm font-semibold tabular-nums tracking-[-0.01em] text-ink/80">{label}</span>
    </div>
  );
}
