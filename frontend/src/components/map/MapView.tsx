import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Map, { type MapRef } from "react-map-gl/maplibre";
import type { StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { OrdersWidget } from "../dashboard/OrdersWidget";
import { useGhostRunner, usePrefersReducedMotion, useSmoothLngLat } from "../../hooks/useRouteAnimation";
import { useTranslation } from "../../i18n/useTranslation";
import { boundsOf, cumulative, pointAtFraction, projectFraction, type LngLat } from "../../lib/geo";
import { translateStopLabel } from "../../lib/stopLabel";
import { simulationApi } from "../../services/api";
import { useAppStore } from "../../state/store";
import type { RoutePreview } from "../../types";
import { OrderMarker } from "./OrderMarker";
import { ActiveRouteLine, PreviewRoute } from "./RouteLines";
import { StopMarker } from "./StopMarker";
import { VehicleMarker } from "./VehicleMarker";

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
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

// Centro por defecto: Monterrey, ZMM. Sin `pitch`: la vista inclinada se veia
// bien vacia, pero con una ruta encima deforma las distancias — el tramo
// lejano se ve corto — y esa lectura es justo la que hay que proteger.
const DEFAULT_VIEW = {
  longitude: -100.3095,
  latitude: 25.6714,
  zoom: 12.4,
  pitch: 0,
  bearing: 0,
};

// Salida cubica: el encuadre llega rapido y se asienta. Nunca `linear`.
const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);

// Padding asimetrico para centrar la vista en el hueco entre los widgets.
// Nunca debe consumir mas del 45 % del eje, o MapLibre aborta con -Infinity.
function safePadding(w: number, h: number) {
  const left  = Math.round(Math.min(300, w * 0.22));
  const right = Math.round(Math.min(220, w * 0.16));
  const top   = Math.round(Math.min(50, h * 0.06));
  const bottom = Math.round(Math.min(50, h * 0.06));

  // Si la suma pasa del 45 % del eje, escalar proporcionalmente.
  const hScale = (left + right) > w * 0.45 ? (w * 0.45) / (left + right) : 1;
  const vScale = (top + bottom) > h * 0.45 ? (h * 0.45) / (top + bottom) : 1;

  return {
    left: Math.round(left * hScale),
    right: Math.round(right * hScale),
    top: Math.round(top * vScale),
    bottom: Math.round(bottom * vScale),
  };
}

// Wrapper que impide que fitBounds crashee la app entera cuando las
// coordenadas quedan demasiado cerca y el padding no cabe.
function safeFitBounds(
  map: import("react-map-gl/maplibre").MapRef,
  bounds: [import("../../lib/geo").LngLat, import("../../lib/geo").LngLat],
  opts: Parameters<import("react-map-gl/maplibre").MapRef["fitBounds"]>[1],
) {
  try {
    map.fitBounds(bounds, opts);
  } catch {
    // Fallback: intentar sin padding
    try {
      map.fitBounds(bounds, { ...opts, padding: 40 });
    } catch {
      // Nada que hacer — el mapa se queda donde esta.
    }
  }
}

export function MapView() {
  const { t } = useTranslation();
  // OJO: el fallback `?? []` tiene que ir FUERA del selector de zustand.
  // Adentro, crea un arreglo nuevo en cada llamada -> useSyncExternalStore
  // ve una referencia distinta cada vez -> loop infinito de renders.
  const user = useAppStore((s) => s.user);
  const simulation = useAppStore((s) => s.simulation);
  const selectedOrderId = useAppStore((s) => s.selectedOrderId);
  const setSelectedOrderId = useAppStore((s) => s.setSelectedOrderId);
  const setSimulation = useAppStore((s) => s.setSimulation);

  const pendingOrders = simulation?.pending_orders ?? [];
  const activeRoutes = simulation?.active_routes ?? [];
  const vehicle = user?.vehicle_type ?? simulation?.vehicle ?? "moto";

  const mapRef = useRef<MapRef>(null);
  const reducedMotion = usePrefersReducedMotion();

  const [preview, setPreview] = useState<RoutePreview | null>(null);
  const [loadingRoute, setLoadingRoute] = useState(false);
  const [routeError, setRouteError] = useState<string | null>(null);
  const [deciding, setDeciding] = useState(false);
  const [previewEnabled, setPreviewEnabled] = useState(false);

  const selectedOrder = pendingOrders.find((o) => o.order_id === selectedOrderId) ?? null;
  const runId = simulation?.run_id ?? null;

  // --- Ruta de la oferta seleccionada -------------------------------------
  // Se pide solo al seleccionar, no en cada sondeo: son dos A* sobre el grafo
  // real de la ZMM por oferta, y el conductor mira una a la vez.
  // Se pide solo al seleccionar y pedir preview explícito, no en cada sondeo
  useEffect(() => {
    setPreviewEnabled(false);
  }, [selectedOrderId]);

  useEffect(() => {
    if (!runId || !selectedOrderId || !previewEnabled) {
      setPreview(null);
      setRouteError(null);
      return;
    }

    let cancelled = false;
    setLoadingRoute(true);
    setRouteError(null);

    simulationApi
      .getRoute(runId, selectedOrderId)
      .then(({ data }) => {
        if (!cancelled) setPreview(data);
      })
      .catch((error: { response?: { status?: number } }) => {
        if (cancelled) return;
        setPreview(null);
        setRouteError(
          error.response?.status === 409 ? t("orderDetail.routeError.closure") : t("orderDetail.routeError.generic"),
        );
      })
      .finally(() => {
        if (!cancelled) setLoadingRoute(false);
      });

    return () => {
      cancelled = true;
    };
  }, [runId, selectedOrderId, previewEnabled]);

  // --- Repartidor real (target actual para encuadre y animacion) ---
  const currentDelivery = activeRoutes.find((route) => route.is_current) ?? null;

  const courierTarget = currentDelivery
    ? { lng: currentDelivery.courier_lon, lat: currentDelivery.courier_lat }
    : simulation?.courier_lat != null && simulation?.courier_lon != null
      ? { lng: simulation.courier_lon, lat: simulation.courier_lat }
      : null;

  // Guardamos la ubicacion en un ref para poder leerla en el useEffect de
  // encuadre sin que cada actualizacion de GPS dispare un re-encuadre.
  const courierTargetRef = useRef(courierTarget);
  useEffect(() => {
    courierTargetRef.current = courierTarget;
  }, [courierTarget]);


  // --- Encuadre al seleccionar una orden -----------------------------------
  // Reacciona cuando selectedOrderId cambia (se selecciona una orden distinta).
  // Se incluye selectedOrder en deps para capturar el objeto correcto, pero
  // un ref evita que los re-renders por polls vuelvan a disparar el zoom.
  const lastZoomedOrderId = useRef<string | null>(null);
  useEffect(() => {
    // Reset the guard when there's no selection
    if (!selectedOrderId) {
      lastZoomedOrderId.current = null;
      return;
    }
    // Only zoom once per unique order selection, not on every poll re-render
    if (lastZoomedOrderId.current === selectedOrderId) return;
    if (!selectedOrder) return;

    const map = mapRef.current;
    if (!map) return;

    const points: LngLat[] = [
      [selectedOrder.pickup_lon, selectedOrder.pickup_lat],
      [selectedOrder.dropoff_lon, selectedOrder.dropoff_lat],
    ];
    if (courierTargetRef.current) {
      points.push([courierTargetRef.current.lng, courierTargetRef.current.lat]);
    }
    const bounds = boundsOf(points);
    if (!bounds) return;

    lastZoomedOrderId.current = selectedOrderId;
    const { clientWidth: width, clientHeight: height } = map.getContainer();
    map.stop();
    setTimeout(() => {
      safeFitBounds(map, bounds, {
        padding: safePadding(width, height),
        duration: reducedMotion ? 0 : 1000,
        easing: easeOutCubic,
        maxZoom: 14.5,
      });
    }, 50);
  }, [selectedOrderId, selectedOrder, reducedMotion]);

  // Encuadra la ruta completa (preview) cuando llega — efecto separado del
  // de seleccion para no mezclarse con los polls de GPS.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !preview) return;

    const points = [...(preview.coordinates as LngLat[])];
    if (courierTargetRef.current) {
      points.push([courierTargetRef.current.lng, courierTargetRef.current.lat]);
    }
    const bounds = boundsOf(points);
    if (!bounds) return;

    const { clientWidth: width, clientHeight: height } = map.getContainer();
    map.stop();
    setTimeout(() => {
      safeFitBounds(map, bounds, {
        padding: safePadding(width, height),
        duration: reducedMotion ? 0 : 1000,
        easing: easeOutCubic,
        maxZoom: 15.5,
      });
    }, 50);
  }, [preview, reducedMotion]);

  // --- Vehiculo fantasma sobre la ruta propuesta --------------------------
  const previewCoords = preview?.coordinates as LngLat[] | undefined;
  const previewCum = useMemo(() => (previewCoords ? cumulative(previewCoords) : null), [previewCoords]);
  const ghostFraction = useGhostRunner(Boolean(previewCoords));
  const ghost = useMemo(
    () => (previewCoords && previewCum ? pointAtFraction(previewCoords, previewCum, ghostFraction) : null),
    [previewCoords, previewCum, ghostFraction],
  );

  // --- Repartidor real (animacion suave) ----------------------------------
  const courier = useSmoothLngLat(courierTarget);

  const activeCoords = currentDelivery?.coordinates as LngLat[] | undefined;
  const activeCum = useMemo(() => (activeCoords ? cumulative(activeCoords) : null), [activeCoords]);
  // El avance de la LINEA se saca proyectando la posicion real del repartidor,
  // no de su avance en tiempo: si se usara el tiempo, en las calles lentas la
  // linea se adelantaria al vehiculo y se veria roto.
  const activeProgress = useMemo(() => {
    if (!activeCoords || !activeCum || !courier) return 0;
    return projectFraction(activeCoords, activeCum, courier.lng, courier.lat);
  }, [activeCoords, activeCum, courier]);

  // --- Fly back to courier when deselected ---
  const prevSelectedId = useRef(selectedOrderId);
  useEffect(() => {
    if (prevSelectedId.current && !selectedOrderId) {
      const map = mapRef.current;
      if (map && courierTarget) {
        const { clientWidth: width, clientHeight: height } = map.getContainer();
        map.stop();
        map.flyTo({
          center: [courierTarget.lng, courierTarget.lat],
          zoom: 13.5,
          padding: safePadding(width, height),
          duration: reducedMotion ? 0 : 1000,
        });
      }
    }
    prevSelectedId.current = selectedOrderId;
  }, [selectedOrderId, courierTarget, reducedMotion]);

  // Estables entre frames de animacion (ver useSmoothLngLat/VehicleMarker):
  // sin useCallback, cada re-render de MapView (60/s mientras el repartidor
  // se mueve) le pasaria una funcion nueva a OrderMarker/OrdersWidget y su
  // `memo` nunca podria saltarse el re-render.
  const handleSelectOrder = useCallback(
    (orderId: string) => {
      setSelectedOrderId(orderId === selectedOrderId ? null : orderId);
    },
    [selectedOrderId, setSelectedOrderId],
  );

  const decide = useCallback(
    async (accept: boolean) => {
      if (!simulation || !selectedOrder) return;
      setDeciding(true);
      try {
        const { data } = await simulationApi.decide({
          run_id: simulation.run_id,
          order_id: selectedOrder.order_id,
          accept,
        });
        // El store suelta la seleccion solo: la orden ya no esta pendiente.
        setSimulation(data);
      } finally {
        setDeciding(false);
      }
    },
    [simulation, selectedOrder, setSimulation],
  );

  const handleAccept = useCallback(() => decide(true), [decide]);
  const handleReject = useCallback(() => decide(false), [decide]);
  const handlePreviewRoute = useCallback(() => setPreviewEnabled(true), []);

  return (
    <div className="absolute inset-0">
      {/* Tiles OSM llevan sus colores naturales; se aplica un duotono sutil
          para que el mapa se sienta parte de la misma paleta de marca.
          `absolute inset-0` y no `h-full`: el contenedor padre (mapWrap en
          SimulationPage) obtiene su alto via `flex-1` (flex-basis:0), y ese
          alto NO cuenta como "especificado" para que un `height:100%` hijo
          lo herede — el mapa colapsaba a 0px. Posicionar en absoluto rellena
          el bloque posicionado mas cercano sin pasar por esa resolucion de
          porcentaje. */}
      <div className="absolute inset-0 [&_.maplibregl-canvas]:contrast-[1.02] [&_.maplibregl-canvas]:hue-rotate-[280deg] [&_.maplibregl-canvas]:saturate-[0.45] [&_.maplibregl-canvas]:sepia-[0.18]">
        <Map
          ref={mapRef}
          initialViewState={DEFAULT_VIEW}
          mapStyle={OSM_STYLE}
          style={{ width: "100%", height: "100%" }}
          onClick={() => setSelectedOrderId(null)}
        >
          {/* Entrega en curso: primero la linea, para que los marcadores
              queden encima de ella. */}
          {currentDelivery && activeCoords && (
            <ActiveRouteLine
              coordinates={activeCoords}
              progress={activeProgress}
              dimmed={Boolean(preview)}
            />
          )}

          {previewCoords && preview && (
            <PreviewRoute
              coordinates={previewCoords}
              pickupIndex={preview.pickup_index}
              progress={ghostFraction}
            />
          )}

          {pendingOrders.map((order) => (
            <OrderMarker
              key={order.order_id}
              order={order}
              selected={order.order_id === selectedOrderId}
              // Cuando hay una ruta en pantalla, el resto de las ofertas se
              // apaga: si no, el mapa compite consigo mismo.
              dimmed={Boolean(selectedOrderId) && order.order_id !== selectedOrderId}
              onSelect={handleSelectOrder}
            />
          ))}

          {currentDelivery?.stops
            .filter((stop) => stop.kind !== "courier")
            .map((stop, i) => (
              <StopMarker
                key={`active-${stop.kind}-${stop.order_id ?? i}`}
                stop={stop}
                index={i + 1}
                dimmed={Boolean(preview)}
                label={translateStopLabel(
                  stop,
                  stop.kind === "pickup" && stop.order_id !== currentDelivery.order_id
                    ? currentDelivery.extra_pickup_name
                    : currentDelivery.pickup_name,
                  t,
                )}
              />
            ))}

          {preview?.stops.map((stop, i) => (
            <StopMarker
              key={`preview-${stop.kind}-${i}`}
              stop={stop}
              index={i}
              detailed
              delayMs={i * 90}
              label={translateStopLabel(stop, preview.pickup_name, t)}
            />
          ))}

          {!preview && selectedOrder && (
            <>
              <StopMarker
                key={`selected-pickup-${selectedOrder.order_id}`}
                stop={{
                  kind: "pickup",
                  label: "Pickup",
                  lat: selectedOrder.pickup_lat,
                  lon: selectedOrder.pickup_lon,
                  eta_minutes: 0,
                  order_id: selectedOrder.order_id,
                }}
                index={0}
                detailed
                label={t("orderDetail.pickupOrder")}
              />
              <StopMarker
                key={`selected-dropoff-${selectedOrder.order_id}`}
                stop={{
                  kind: "dropoff",
                  label: "Dropoff",
                  lat: selectedOrder.dropoff_lat,
                  lon: selectedOrder.dropoff_lon,
                  eta_minutes: 0,
                  order_id: selectedOrder.order_id,
                }}
                index={0}
                detailed
                label={t("orderDetail.dropoffOrder")}
              />
            </>
          )}

          {/* El fantasma: recorre la ruta propuesta en bucle para enseñar como
              se entregaria el pedido antes de aceptarlo. */}
          {ghost && (
            <VehicleMarker
              lat={ghost.lat}
              lng={ghost.lng}
              bearing={ghost.bearing}
              vehicle={vehicle}
              variant="ghost"
              label={t("map.preview")}
            />
          )}

          {courier && (
            <VehicleMarker
              lat={courier.lat}
              lng={courier.lng}
              bearing={courier.bearing}
              vehicle={vehicle}
            />
          )}
        </Map>
      </div>

      <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-paper/50 via-transparent to-paper/10" />



      <OrdersWidget
        route={preview}
        loadingRoute={loadingRoute}
        routeError={routeError}
        previewEnabled={previewEnabled}
        onPreviewRoute={handlePreviewRoute}
        deciding={deciding}
        onAccept={handleAccept}
        onReject={handleReject}
      />
    </div>
  );
}
