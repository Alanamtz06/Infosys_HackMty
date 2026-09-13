import type { ReactNode } from "react";

import { useDraggableWidget } from "../../hooks/useDraggableWidget";
import { useTranslation } from "../../i18n/useTranslation";

interface Props {
  id: string;
  title: string;
  /** Clases de posicionamiento absoluto respecto al mapa (ancla + offset
   * base) — el drag SUMA un `transform` encima de esto, nunca lo reemplaza. */
  anchorClassName: string;
  width?: string;
  children: ReactNode;
  headerRight?: ReactNode;
}

/**
 * Marco comun de los widgets flotantes del mapa (Ofertas, Bitacora): doble
 * bisel, asa de arrastre en el header, boton de cerrar. La posicion se
 * anima con `transform: translate3d` — nunca `top`/`left` — para que
 * arrastrar no dispare layout en cada frame (ver useDraggableWidget).
 *
 * Cerrar solo cambia `open` (queda recordado en localStorage); quien
 * necesite reabrirlo usa el control "Paneles" del ControlPanel, que llama a
 * `toggleWidget(id)` — este componente no dibuja su propio affordance de
 * reapertura porque, cerrado, no hay nada en pantalla sobre lo cual pintarlo.
 */
export function DraggableWidget({ id, title, anchorClassName, width, children, headerRight }: Props) {
  const { dx, dy, open, close, dragHandleProps } = useDraggableWidget(id);
  const { t } = useTranslation();

  if (!open) return null;

  return (
    <div
      className={`pointer-events-auto absolute z-panel ${anchorClassName} ${width ?? "w-[20.5rem]"} max-w-[calc(100vw-2rem)]`}
      style={{ transform: `translate3d(${dx}px, ${dy}px, 0)` }}
    >
      <div className="animate-fade-up rounded-[1.75rem] bg-paper/70 p-1.5 shadow-[0_20px_44px_-18px_rgba(104,73,89,0.55)] ring-1 ring-plum/10 backdrop-blur-xl">
        <div className="overflow-hidden rounded-[calc(1.75rem-0.375rem)] bg-paper/95 shadow-[inset_0_1px_1px_rgba(255,255,255,0.6)]">
          <header
            {...dragHandleProps}
            className="flex touch-none items-center justify-between gap-2 px-4 pb-2 pt-3 [cursor:grab] active:[cursor:grabbing]"
            title={t("widget.drag")}
          >
            <span className="text-[10px] font-medium uppercase tracking-[0.2em] text-plum/70">{title}</span>
            <div className="flex items-center gap-2">
              {headerRight}
              <button
                // El boton de cerrar no debe arrastrar: para el evento antes
                // de que llegue al header.
                onPointerDown={(e) => e.stopPropagation()}
                onClick={close}
                aria-label={t("widget.close")}
                className="flex h-5 w-5 items-center justify-center rounded-full text-charcoal/40 transition duration-200 ease-out hover:bg-dust/50 hover:text-ink active:scale-95"
              >
                <svg viewBox="0 0 24 24" className="h-3 w-3" fill="none" aria-hidden="true">
                  <path d="m7 7 10 10M17 7 7 17" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                </svg>
              </button>
            </div>
          </header>

          {children}
        </div>
      </div>
    </div>
  );
}
