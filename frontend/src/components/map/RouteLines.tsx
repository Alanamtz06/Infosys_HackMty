import { useMemo } from "react";
import { Layer, Source } from "react-map-gl/maplibre";
import type { FeatureCollection } from "geojson";

import { cumulative, sliceTo, type LngLat } from "../../lib/geo";

const PLUM = "#684959";
const BLUSH = "#E5CAD9";
const PAPER = "#FAF6F3";

/** Una linea valida pero de largo cero: el primer punto repetido.
 *
 * Sirve para no desmontar la fuente cuando todavia no hay nada recorrido. Si
 * en vez de esto se devolviera un arreglo vacio, React quitaria el <Source> y
 * lo volveria a montar en cada vuelta del recorrido fantasma, y MapLibre
 * llega a quejarse de que la fuente ya existe cuando las dos cosas caen en el
 * mismo tick. */
function degenerate(coords: LngLat[]): LngLat[] {
  return coords.length ? [coords[0], coords[0]] : [];
}

function lineOf(coords: LngLat[]): FeatureCollection {
  return {
    type: "FeatureCollection",
    features: [{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: coords } }],
  };
}

interface SegmentProps {
  id: string;
  coords: LngLat[];
  color: string;
  width: number;
  opacity?: number;
  dashed?: boolean;
  /** Borde claro debajo de la linea: sin el, la ruta se pierde sobre las
   *  avenidas oscuras del mapa. Es lo que la vuelve legible en cualquier tile. */
  casing?: boolean;
}

function Segment({ id, coords, color, width, opacity = 1, dashed = false, casing = true }: SegmentProps) {
  const data = useMemo(() => lineOf(coords), [coords]);

  // Una LineString con menos de dos puntos es geometria invalida: MapLibre la
  // rechaza y tira la fuente entera, no solo ese tramo.
  if (coords.length < 2) return null;

  return (
    <Source id={id} type="geojson" data={data} lineMetrics>
      {casing && (
        <Layer
          id={`${id}-casing`}
          type="line"
          layout={{ "line-cap": "round", "line-join": "round" }}
          paint={{
            "line-color": PAPER,
            "line-width": width + 3.5,
            "line-opacity": 0.85 * opacity,
            "line-blur": 0.4,
          }}
        />
      )}
      <Layer
        id={`${id}-line`}
        type="line"
        layout={{ "line-cap": dashed ? "butt" : "round", "line-join": "round" }}
        paint={{
          "line-color": color,
          "line-width": width,
          "line-opacity": opacity,
          ...(dashed ? { "line-dasharray": [1.6, 1.4] } : {}),
        }}
      />
    </Source>
  );
}

interface PreviewProps {
  coordinates: LngLat[];
  pickupIndex: number;
  /** 0..1 del recorrido fantasma: pinta la ruta conforme el vehiculo avanza. */
  progress: number;
}

/**
 * La ruta de una oferta que todavia NO se acepta.
 *
 * Se dibuja en dos capas: la ruta completa tenue (a donde se va a ir) y
 * encima, el trazo vivo que el vehiculo fantasma va dejando. Ese contraste es
 * lo que convierte una linea estatica en una explicacion del recorrido.
 *
 * El tramo hasta el restaurante va punteado y el de la entrega solido: son
 * dos cosas distintas — uno es costo puro (ir por la comida), el otro es el
 * viaje que paga la tarifa.
 */
export function PreviewRoute({ coordinates, pickupIndex, progress }: PreviewProps) {
  const toPickup = useMemo(() => coordinates.slice(0, pickupIndex + 1), [coordinates, pickupIndex]);
  const toDropoff = useMemo(() => coordinates.slice(pickupIndex), [coordinates, pickupIndex]);

  const cum = useMemo(() => cumulative(coordinates), [coordinates]);
  const travelled = useMemo(() => {
    // Se redondea la fraccion antes de cortar: a 60fps, re-subir la polilinea
    // a MapLibre en cada frame no agrega nada visible y si trabajo de GPU.
    const slice = sliceTo(coordinates, cum, Math.round(progress * 200) / 200);
    return slice.length >= 2 ? slice : degenerate(coordinates);
  }, [coordinates, cum, progress]);

  return (
    <>
      <Segment id="preview-to-pickup" coords={toPickup} color={PLUM} width={3} opacity={0.34} dashed />
      <Segment id="preview-to-dropoff" coords={toDropoff} color={PLUM} width={3.5} opacity={0.34} />
      <Segment id="preview-travelled" coords={travelled} color={PLUM} width={4.5} casing={false} />
    </>
  );
}

interface ActiveProps {
  coordinates: LngLat[];
  /** Avance REAL del repartidor, proyectado sobre la linea. */
  progress: number;
  dimmed?: boolean;
}

/**
 * Una entrega en curso: lo recorrido en plum solido, lo que falta en blush.
 *
 * Es la misma distincion que hace cualquier app de reparto, y aqui ademas
 * sirve de comprobante — la parte solida es trabajo ya hecho que el Score ya
 * cobro.
 */
export function ActiveRouteLine({ coordinates, progress, dimmed = false }: ActiveProps) {
  const cum = useMemo(() => cumulative(coordinates), [coordinates]);
  const travelled = useMemo(() => {
    const slice = sliceTo(coordinates, cum, Math.round(progress * 200) / 200);
    return slice.length >= 2 ? slice : degenerate(coordinates);
  }, [coordinates, cum, progress]);

  const fade = dimmed ? 0.4 : 1;

  return (
    <>
      <Segment id="active-remaining" coords={coordinates} color={BLUSH} width={4} opacity={0.95 * fade} />
      <Segment id="active-travelled" coords={travelled} color={PLUM} width={4} opacity={fade} casing={false} />
    </>
  );
}
