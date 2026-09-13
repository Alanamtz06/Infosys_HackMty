/** Matematica de polilineas para el mapa: avanzar sobre una ruta, cortarla en
 * un punto y encuadrarla.
 *
 * Todo trabaja en `[lon, lat]` (el orden de GeoJSON/MapLibre, y el que manda
 * el backend en `coordinates`). Las distancias se miden en un plano
 * equirectangular corrigiendo la longitud por `cos(lat)`: a escala de una
 * ciudad el error contra la distancia real es despreciable, y evita meter
 * trigonometria esferica en un bucle que corre en cada frame.
 */

export type LngLat = [number, number];

/** Escala para que un grado de longitud pese lo mismo que uno de latitud. */
function lonScale(lat: number): number {
  return Math.cos((lat * Math.PI) / 180);
}

function segmentLength(a: LngLat, b: LngLat): number {
  const scale = lonScale((a[1] + b[1]) / 2);
  const dx = (b[0] - a[0]) * scale;
  const dy = b[1] - a[1];
  return Math.hypot(dx, dy);
}

/** Distancias acumuladas por vertice. `cum[i]` = largo de `coords[0..i]`. */
export function cumulative(coords: LngLat[]): number[] {
  const cum = new Array<number>(coords.length);
  cum[0] = 0;
  for (let i = 1; i < coords.length; i++) {
    cum[i] = cum[i - 1] + segmentLength(coords[i - 1], coords[i]);
  }
  return cum;
}

export function totalLength(cum: number[]): number {
  return cum.length ? cum[cum.length - 1] : 0;
}

/** Indice del ultimo vertice que queda ANTES de la distancia `target`.
 *
 * Busqueda binaria, no lineal: `cum` puede traer 400 puntos y esto se llama
 * en cada frame del recorrido fantasma. */
function segmentAt(cum: number[], target: number): number {
  let lo = 0;
  let hi = cum.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (cum[mid] <= target) lo = mid;
    else hi = mid - 1;
  }
  return Math.min(lo, cum.length - 2);
}

export interface PointOnRoute {
  lng: number;
  lat: number;
  /** Grados desde el norte, en sentido horario — listo para rotar un icono. */
  bearing: number;
}

/** El punto que cae a la fraccion `t` (0..1) del LARGO de la ruta. */
export function pointAtFraction(coords: LngLat[], cum: number[], t: number): PointOnRoute {
  if (coords.length === 0) return { lng: 0, lat: 0, bearing: 0 };
  if (coords.length === 1) return { lng: coords[0][0], lat: coords[0][1], bearing: 0 };

  const total = totalLength(cum);
  const target = Math.min(Math.max(t, 0), 1) * total;
  const i = segmentAt(cum, target);

  const a = coords[i];
  const b = coords[i + 1];
  const span = cum[i + 1] - cum[i];
  const local = span > 0 ? (target - cum[i]) / span : 0;

  const scale = lonScale(a[1]);
  return {
    lng: a[0] + (b[0] - a[0]) * local,
    lat: a[1] + (b[1] - a[1]) * local,
    // atan2(este, norte) da el angulo horario desde el norte, que es
    // justo la convencion de `rotate` sobre un icono que apunta hacia arriba.
    bearing: (Math.atan2((b[0] - a[0]) * scale, b[1] - a[1]) * 180) / Math.PI,
  };
}

/** La porcion de ruta desde el inicio hasta la fraccion `t`, cortada EXACTO
 * en ese punto (no en el vertice mas cercano) para que la linea recorrida
 * termine justo debajo del vehiculo. */
export function sliceTo(coords: LngLat[], cum: number[], t: number): LngLat[] {
  if (coords.length < 2) return coords;
  const clamped = Math.min(Math.max(t, 0), 1);
  if (clamped <= 0) return [];
  if (clamped >= 1) return coords;

  const target = clamped * totalLength(cum);
  const i = segmentAt(cum, target);
  const head = coords.slice(0, i + 1);
  const { lng, lat } = pointAtFraction(coords, cum, clamped);
  head.push([lng, lat]);
  return head;
}

/** Que tan avanzada esta la ruta en un punto dado (0..1).
 *
 * Proyecta `[lng, lat]` sobre el segmento mas cercano. Se usa para que la
 * linea de "ya recorrido" termine exactamente donde el backend dice que va
 * el repartidor: si en vez de esto se usara su avance en TIEMPO, la linea y
 * el marcador se separarian en las calles lentas, que es justo donde el ojo
 * lo nota. */
export function projectFraction(coords: LngLat[], cum: number[], lng: number, lat: number): number {
  if (coords.length < 2) return 0;

  let best = { distance: Infinity, travelled: 0 };

  for (let i = 0; i < coords.length - 1; i++) {
    const a = coords[i];
    const b = coords[i + 1];
    const scale = lonScale(a[1]);

    const ax = a[0] * scale;
    const ay = a[1];
    const bx = b[0] * scale;
    const by = b[1];
    const px = lng * scale;
    const py = lat;

    const dx = bx - ax;
    const dy = by - ay;
    const lengthSq = dx * dx + dy * dy;
    const local = lengthSq > 0 ? Math.min(Math.max(((px - ax) * dx + (py - ay) * dy) / lengthSq, 0), 1) : 0;

    const distance = Math.hypot(px - (ax + dx * local), py - (ay + dy * local));
    if (distance < best.distance) {
      best = { distance, travelled: cum[i] + (cum[i + 1] - cum[i]) * local };
    }
  }

  const total = totalLength(cum);
  return total > 0 ? best.travelled / total : 0;
}

/** Encuadre `[[oeste, sur], [este, norte]]` para `map.fitBounds`. */
export function boundsOf(coords: LngLat[]): [[number, number], [number, number]] | null {
  if (coords.length === 0) return null;

  let west = coords[0][0];
  let east = coords[0][0];
  let south = coords[0][1];
  let north = coords[0][1];

  for (const [lng, lat] of coords) {
    if (lng < west) west = lng;
    if (lng > east) east = lng;
    if (lat < south) south = lat;
    if (lat > north) north = lat;
  }

  return [
    [west, south],
    [east, north],
  ];
}

/** Interpolacion angular por el camino corto: sin esto, un giro que cruza
 * 359°→1° hace que el icono gire 358 grados para el otro lado. */
export function lerpAngle(from: number, to: number, amount: number): number {
  let delta = ((to - from + 540) % 360) - 180;
  return from + delta * amount;
}
