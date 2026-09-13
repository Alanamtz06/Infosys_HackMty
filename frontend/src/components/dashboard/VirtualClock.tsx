interface Props {
  virtualHour: number;
}

// La hora del MUNDO simulado, no la del servidor: corre acelerada y nunca se
// detiene, asi que el punto late siempre (ver engine/virtual_clock.py).
//
// Sin `font-mono`: la familia mono no esta configurada en tailwind.config.js,
// asi que caia al mono por defecto del navegador — Courier en varias maquinas,
// que no se parece en nada al resto de la interfaz. Outfit con `tabular-nums`
// da cifras de ancho fijo (el reloj no baila al cambiar de minuto) sin salirse
// de la tipografia del proyecto.
export function VirtualClock({ virtualHour }: Props) {
  const hours = Math.floor(virtualHour);
  const minutes = Math.round((virtualHour - hours) * 60);
  const label = `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}`;

  return (
    <div className="rounded-2xl bg-paper/60 p-1 ring-1 ring-plum/10">
      <div className="flex items-center gap-2 rounded-[calc(1rem-0.25rem)] bg-paper/95 px-3 py-1.5 shadow-[inset_0_1px_1px_rgba(255,255,255,0.6)]">
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-plum" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-plum" />
        </span>
        <span className="text-base font-semibold tabular-nums tracking-[-0.01em] text-ink">{label}</span>
      </div>
    </div>
  );
}
