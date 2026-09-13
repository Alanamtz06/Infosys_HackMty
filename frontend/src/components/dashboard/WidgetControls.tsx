import { useState } from "react";
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
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="flex items-center rounded-[1.75rem] bg-paper/70 p-1.5 shadow-[0_20px_44px_-18px_rgba(104,73,89,0.55)] ring-1 ring-plum/10 backdrop-blur-xl transition-all duration-300">
      <div 
        className={`flex items-center overflow-hidden rounded-[calc(1.75rem-0.375rem)] bg-paper/95 shadow-[inset_0_1px_1px_rgba(255,255,255,0.6)] transition-all duration-500 ease-[cubic-bezier(0.23,1,0.32,1)] ${
          isExpanded ? "max-w-[600px] px-3 py-1.5" : "max-w-[46px] p-1.5"
        }`}
      >
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className={`shrink-0 flex h-[34px] w-[34px] items-center justify-center rounded-full text-charcoal/70 transition-all duration-300 hover:bg-dust/40 hover:text-ink active:scale-95 ${
            isExpanded ? "mr-2 bg-dust/20" : ""
          }`}
          aria-label="Toggle Widget Controls"
          title="Configuración"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className={`h-[18px] w-[18px] transition-transform duration-500 ${isExpanded ? "rotate-90" : "rotate-0"}`}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>

        <div className={`flex flex-nowrap items-center gap-2 whitespace-nowrap transition-opacity duration-300 ${isExpanded ? "opacity-100" : "opacity-0"}`}>
          <span className="text-[10px] font-medium uppercase tracking-[0.2em] text-plum/70 pr-1">
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
      </div>
    </div>
  );
}
