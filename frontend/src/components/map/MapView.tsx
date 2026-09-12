import Map from "react-map-gl/maplibre";
import type { StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

// Tiles reales de OpenStreetMap (openstreetmap.org) via raster, sin necesidad
// de token ni cuenta de Mapbox. Si mas adelante se necesita un estilo vector
// dark-mode "de verdad", cambiar por un estilo vector compatible con MapLibre
// (p.ej. OpenFreeMap o MapTiler) que tambien corre sin Mapbox.
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

export function MapView() {
  return (
    <Map
      initialViewState={DEFAULT_VIEW}
      mapStyle={OSM_STYLE}
      style={{ width: "100%", height: "100%" }}
    >
      {/* TODO: DeliveryMarker, OrderMarker y capa de rutas del agente repartidor */}
    </Map>
  );
}
