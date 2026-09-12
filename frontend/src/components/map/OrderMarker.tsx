import { Marker } from "react-map-gl/maplibre";

import type { Order } from "../../types";

interface Props {
  order: Order;
}

export function OrderMarker({ order }: Props) {
  return (
    <Marker latitude={order.pickup_lat} longitude={order.pickup_lon}>
      <div className="animate-pop-in relative flex h-6 w-6 items-center justify-center">
        <span className="absolute h-6 w-6 animate-pulse-ring rounded-full bg-blush/70" />
        <span className="relative z-10 h-3 w-3 rounded-full bg-blush ring-2 ring-plum" />
      </div>
    </Marker>
  );
}
