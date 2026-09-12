import { Marker } from "react-map-gl/maplibre";

import type { Order } from "../../types";

interface Props {
  order: Order;
}

export function OrderMarker({ order }: Props) {
  return (
    <Marker latitude={order.pickup_lat} longitude={order.pickup_lon}>
      <div className="h-3 w-3 rounded-full bg-amber-400 shadow-lg shadow-amber-400/50" />
    </Marker>
  );
}
