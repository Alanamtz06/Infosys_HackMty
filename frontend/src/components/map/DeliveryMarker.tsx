import { Marker } from "react-map-gl/maplibre";

interface Props {
  lat: number;
  lon: number;
}

export function DeliveryMarker({ lat, lon }: Props) {
  return (
    <Marker latitude={lat} longitude={lon}>
      <div className="h-3 w-3 rounded-full bg-emerald-400 shadow-lg shadow-emerald-400/50" />
    </Marker>
  );
}
