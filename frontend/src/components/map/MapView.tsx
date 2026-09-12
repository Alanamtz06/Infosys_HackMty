import Map from "react-map-gl/maplibre";
import type { StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { useAppStore } from "../../state/store";
import { DeliveryMarker } from "./DeliveryMarker";
import { OrderMarker } from "./OrderMarker";

// Tiles reales de OpenStreetMap (openstreetmap.org) via raster, sin necesidad
// de token ni cuenta de Mapbox. Si mas adelante se necesita un estilo vector
// con mas control de color, cambiar por un estilo vector compatible con
// MapLibre (p.ej. OpenFreeMap o MapTiler) que tambien corre sin Mapbox.
const OSM_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "&copy; OpenStreetMap contributors",
    },
  },
  layers: [
    {
      id: "osm",
      type: "raster",
      source: "osm",
    },
  ],
};

// Centro por defecto: Monterrey, ZMM
const DEFAULT_VIEW = {
  longitude: -100.3095,
  latitude: 25.6714,
  zoom: 12,
  pitch: 55,
  bearing: 0,
};

// Posicion placeholder del repartidor mientras el backend no transmite su
// ubicacion en vivo (ver TODO en state/store.ts). Un punto cercano al centro.
const PLACEHOLDER_RIDER_POSITION = {
  lat: 25.6688,
  lon: -100.3122,
};

export function MapView() {
  // OJO: el fallback `?? []` tiene que ir FUERA del selector de zustand.
  // Adentro, crea un arreglo nuevo en cada llamada -> useSyncExternalStore
  // ve una referencia distinta cada vez -> loop infinito de renders.
  const simulation = useAppStore((s) => s.simulation);
  const pendingOrders = simulation?.pending_orders ?? [];

  return (
    <div className="relative h-full w-full">
      {/* Tiles OSM llevan sus colores naturales; se aplica un duotono sutil
          para que el mapa se sienta parte de la misma paleta de marca. */}
      <div className="h-full w-full [&_.maplibregl-canvas]:saturate-[0.45] [&_.maplibregl-canvas]:sepia-[0.18] [&_.maplibregl-canvas]:hue-rotate-[280deg] [&_.maplibregl-canvas]:contrast-[1.02]">
        <Map initialViewState={DEFAULT_VIEW} mapStyle={OSM_STYLE} style={{ width: "100%", height: "100%" }}>
          {pendingOrders.map((order) => (
            <OrderMarker key={order.order_id} order={{ ...order, id: order.order_id }} />
          ))}
          <DeliveryMarker lat={PLACEHOLDER_RIDER_POSITION.lat} lon={PLACEHOLDER_RIDER_POSITION.lon} />
        </Map>
      </div>

      <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-paper/50 via-transparent to-paper/10" />

      {pendingOrders.length === 0 && (
        <div className="pointer-events-none absolute inset-x-0 bottom-6 flex justify-center">
          <span className="animate-fade-up rounded-full border border-dust bg-paper/95 px-4 py-1.5 text-xs text-charcoal shadow-sm backdrop-blur">
            No active orders right now
          </span>
        </div>
      )}

      <div className="animate-fade-up absolute left-4 top-4 flex items-center gap-3 rounded-full border border-plum/15 bg-paper/90 px-3 py-1.5 text-xs text-charcoal shadow-[0_2px_8px_rgba(104,73,89,0.12)] backdrop-blur">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-blush ring-1 ring-plum/30" /> Order
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-plum" /> Courier
        </span>
      </div>
    </div>
  );
}
