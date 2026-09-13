import { resetAllWidgets, toggleWidget } from "../../hooks/useDraggableWidget";
import { useTranslation } from "../../i18n/useTranslation";

const WIDGETS: { id: string; labelKey: "control.widgets.orders" | "control.widgets.liveLog" }[] = [
  { id: "orders", labelKey: "control.widgets.orders" },
  { id: "liveLog", labelKey: "control.widgets.liveLog" },
];

/**
 * Control de visibilidad de los widgets flotantes del mapa (Ofertas,
 * Bitacora): un chip por widget que lo cierra o lo reabre (recordando su
 * posicion), mas un boton aparte para "restablecer" que limpia toda posicion
 * guardada y reabre todo — la unica forma de recuperar un widget que alguien
 * arrastro fuera de la pantalla.
 *
 * No lee el estado abierto/cerrado de cada widget (viviria en
 * localStorage, no en el store global): los chips son solo el disparador, y
 * cada widget decide por si mismo si mostrarse via `useDraggableWidget`.
 */
export function WidgetControls() {
  const { t } = useTranslation();

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-[10px] font-medium uppercase tracking-[0.2em] text-plum/70">
        {t("control.widgets")}
      </span>
      {WIDGETS.map(({ id, labelKey }) => (
        <button
          key={id}
          onClick={() => toggleWidget(id)}
          className="rounded-full bg-paper/80 px-3.5 py-1.5 text-[13px] font-medium text-charcoal/75 ring-1 ring-plum/10 transition duration-300 ease-out hover:bg-paper hover:text-ink hover:ring-plum/25 active:scale-[0.97]"
        >
          {t(labelKey)}
        </button>
      ))}
      <button
        onClick={resetAllWidgets}
        className="rounded-full px-3 py-1.5 text-[12px] text-charcoal/55 transition duration-300 ease-out hover:text-plum active:scale-[0.97]"
      >
        {t("control.widgets.reset")}
      </button>
    </div>
  );
}
