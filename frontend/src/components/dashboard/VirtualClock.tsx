interface Props {
  virtualHour: number;
}

export function VirtualClock({ virtualHour }: Props) {
  const hours = Math.floor(virtualHour);
  const minutes = Math.round((virtualHour - hours) * 60);
  const label = `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}`;

  return (
    <div className="rounded-lg bg-neutral-900 px-4 py-2 font-mono text-lg text-neutral-100">
      {label}
    </div>
  );
}
