import { memo } from "react";
import { Marker } from "react-map-gl/maplibre";

import type { PendingOrder } from "../../types";

interface Props {
  order: PendingOrder;
  selected: boolean;
  /** Se atenua cuando hay OTRA oferta seleccionada: la ruta en pantalla es
   *  de esa, y las demas no deben competir con ella. */
  dimmed: boolean;
  // Recibe el id en vez de cerrar sobre el: asi el padre puede pasar UNA
  // funcion estable a todos los marcadores (ver MapView.tsx) y `memo` de
  // verdad evita re-renderizarlos en cada frame de la animacion del
  // repartidor, que no les afecta en nada.
  onSelect: (orderId: string) => void;
}

export const OrderMarker = memo(function OrderMarker({ order, selected, dimmed, onSelect }: Props) {
  return (
    <Marker
      latitude={order.pickup_lat}
      longitude={order.pickup_lon}
      // Sin esto, MapLibre se queda el clic para arrastrar el mapa y el
      // marcador nunca recibe el evento.
      onClick={(event) => {
        event.originalEvent.stopPropagation();
        onSelect(order.order_id);
      }}
    >
      <button
        aria-label={`Show route for ${order.pickup_name ?? "this order"}`}
        aria-pressed={selected}
        className={`animate-pop-in relative flex h-7 w-7 items-center justify-center rounded-full transition duration-300 ease-out hover:scale-110 ${
          dimmed ? "opacity-40" : "opacity-100"
        }`}
      >
        {!dimmed && (
          <span className="absolute h-6 w-6 animate-pulse-ring rounded-full bg-blush/70" aria-hidden="true" />
        )}
        {/* `z-10` local, no la escala del sistema (z-panel/header/modal): solo
            levanta el punto por encima de su propio anillo de pulso, dentro
            de este marcador. */}
        <span
          className={`relative z-10 rounded-full transition duration-300 ease-out ${
            selected ? "h-4 w-4 bg-plum ring-[3px] ring-paper" : "h-3 w-3 bg-blush ring-2 ring-plum"
          }`}
        />
      </button>
    </Marker>
  );
});
