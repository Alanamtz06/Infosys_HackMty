import { useCallback, useEffect, useRef, useState } from "react";

export interface WidgetLayout {
  /** Desplazamiento en px desde la esquina de anclaje (nunca coordenadas
   * absolutas de pantalla): asi el layout sigue siendo correcto si la
   * ventana cambia de tamaño entre sesiones. */
  dx: number;
  dy: number;
  open: boolean;
}

const DEFAULT_LAYOUT: WidgetLayout = { dx: 0, dy: 0, open: true };

function storageKey(id: string): string {
  return `nova-widget:${id}`;
}

function readLayout(id: string): WidgetLayout {
  try {
    const raw = localStorage.getItem(storageKey(id));
    if (!raw) return DEFAULT_LAYOUT;
    const parsed = JSON.parse(raw);
    return {
      dx: typeof parsed.dx === "number" ? parsed.dx : 0,
      dy: typeof parsed.dy === "number" ? parsed.dy : 0,
      open: typeof parsed.open === "boolean" ? parsed.open : true,
    };
  } catch {
    // localStorage puede fallar (modo privado, cuota) o traer basura de una
    // version vieja del formato — en cualquier caso, el widget vuelve a su
    // posicion por defecto en vez de romper el render.
    return DEFAULT_LAYOUT;
  }
}

function writeLayout(id: string, layout: WidgetLayout): void {
  try {
    localStorage.setItem(storageKey(id), JSON.stringify(layout));
  } catch {
    // Conveniencia de sesion, no estado critico: si no se pudo guardar, el
    // widget simplemente no recuerda su posicion la proxima vez.
  }
}

// Eventos custom para que "Reset layout" (WidgetControls) y los widgets
// individuales que viven en componentes distintos se enteren entre si sin
// pasar por props ni por el store global — es puramente posicion de
// ventana, no estado de la aplicacion.
const RESET_EVENT = "nova-widget-reset";
const TOGGLE_EVENT = "nova-widget-toggle";

export function resetAllWidgets(): void {
  window.dispatchEvent(new CustomEvent(RESET_EVENT));
}

export function toggleWidget(id: string): void {
  window.dispatchEvent(new CustomEvent(TOGGLE_EVENT, { detail: id }));
}

/**
 * Estado + arrastre de un widget flotante: posicion (persistida en
 * localStorage, un desplazamiento desde su esquina de anclaje) y
 * abierto/cerrado. Devuelve lo necesario para que el componente se pinte con
 * `transform: translate3d(...)` (nunca `top`/`left`, para no disparar layout
 * en cada frame de arrastre) y un `dragHandleProps` para el asa.
 */
export function useDraggableWidget(id: string) {
  const [layout, setLayout] = useState<WidgetLayout>(() => readLayout(id));
  const draggingRef = useRef<{
    startX: number;
    startY: number;
    originDx: number;
    originDy: number;
    minDx: number;
    maxDx: number;
    minDy: number;
    maxDy: number;
  } | null>(null);

  useEffect(() => {
    function onReset() {
      writeLayout(id, DEFAULT_LAYOUT);
      setLayout(DEFAULT_LAYOUT);
    }
    function onToggle(event: Event) {
      const targetId = (event as CustomEvent<string>).detail;
      if (targetId !== id) return;
      setLayout((prev) => {
        const next = { ...prev, open: !prev.open };
        writeLayout(id, next);
        return next;
      });
    }
    window.addEventListener(RESET_EVENT, onReset);
    window.addEventListener(TOGGLE_EVENT, onToggle);
    return () => {
      window.removeEventListener(RESET_EVENT, onReset);
      window.removeEventListener(TOGGLE_EVENT, onToggle);
    };
  }, [id]);

  const close = useCallback(() => {
    setLayout((prev) => {
      const next = { ...prev, open: false };
      writeLayout(id, next);
      return next;
    });
  }, [id]);

  const onPointerDown = useCallback(
    (event: React.PointerEvent) => {
      // Solo el boton principal / el primer punto de contacto tactil.
      if (event.button !== undefined && event.button !== 0) return;

      let minDx = -Infinity, maxDx = Infinity, minDy = -Infinity, maxDy = Infinity;
      const widgetElement = (event.currentTarget as Element).closest(".z-panel") as HTMLElement;
      if (widgetElement && widgetElement.offsetParent) {
        const parent = widgetElement.offsetParent as HTMLElement;
        const padding = 8; // keep a small visual margin from the absolute edge
        minDx = -widgetElement.offsetLeft + padding;
        maxDx = parent.clientWidth - (widgetElement.offsetLeft + widgetElement.offsetWidth) - padding;
        minDy = -widgetElement.offsetTop + padding;
        maxDy = parent.clientHeight - (widgetElement.offsetTop + widgetElement.offsetHeight) - padding;
      }

      draggingRef.current = {
        startX: event.clientX,
        startY: event.clientY,
        originDx: layout.dx,
        originDy: layout.dy,
        minDx,
        maxDx,
        minDy,
        maxDy,
      };
      (event.currentTarget as Element).setPointerCapture(event.pointerId);
    },
    [layout.dx, layout.dy],
  );

  const onPointerMove = useCallback((event: React.PointerEvent) => {
    const drag = draggingRef.current;
    if (!drag) return;
    let dx = drag.originDx + (event.clientX - drag.startX);
    let dy = drag.originDy + (event.clientY - drag.startY);

    // Evitar que el widget se salga del area del mapa
    dx = Math.max(drag.minDx, Math.min(drag.maxDx, dx));
    dy = Math.max(drag.minDy, Math.min(drag.maxDy, dy));

    setLayout((prev) => ({ ...prev, dx, dy }));
  }, []);

  const onPointerUp = useCallback(
    (event: React.PointerEvent) => {
      if (!draggingRef.current) return;
      draggingRef.current = null;
      (event.currentTarget as Element).releasePointerCapture(event.pointerId);
      // Se persiste al SOLTAR, no en cada frame de movimiento — escribir a
      // localStorage 60 veces por segundo durante el arrastre es trabajo
      // desperdiciado que nadie ve.
      setLayout((current) => {
        writeLayout(id, current);
        return current;
      });
    },
    [id],
  );

  return {
    dx: layout.dx,
    dy: layout.dy,
    open: layout.open,
    close,
    dragHandleProps: { onPointerDown, onPointerMove, onPointerUp },
  };
}
