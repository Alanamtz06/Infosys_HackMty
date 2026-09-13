/** Hooks de movimiento del mapa.
 *
 * Dos problemas distintos, dos hooks:
 *   - `useGhostRunner` anima un vehiculo fantasma sobre una ruta que TODAVIA
 *     no se acepta, para enseñar como se recorreria.
 *   - `useSmoothLngLat` interpola al repartidor REAL entre dos sondeos: el
 *     backend manda su posicion cada 2s y con el reloj del mundo a 30x eso
 *     son 60s simulados de salto — sin interpolar, el marcador teletransporta.
 */

import { useEffect, useRef, useState } from "react";

import { lerpAngle } from "../lib/geo";

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() =>
    typeof window !== "undefined"
      ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
      : false,
  );

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onChange = (event: MediaQueryListEvent) => setReduced(event.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  return reduced;
}

/** Fraccion 0..1 que recorre la ruta en bucle, con una pausa al llegar.
 *
 * La pausa no es decorativa: sin ella el fantasma reaparece de golpe en el
 * origen y se lee como un glitch en vez de como una repeticion.
 *
 * Con `prefers-reduced-motion` devuelve 1 fijo — la ruta se ve completa y el
 * vehiculo descansa en el destino, asi que no se pierde ninguna informacion,
 * solo el movimiento.
 */
export function useGhostRunner(active: boolean, durationMs = 5200, pauseMs = 900): number {
  const reducedMotion = usePrefersReducedMotion();
  const [fraction, setFraction] = useState(0);
  const frameRef = useRef(0);

  useEffect(() => {
    if (!active) {
      setFraction(0);
      return;
    }
    if (reducedMotion) {
      setFraction(1);
      return;
    }

    const cycle = durationMs + pauseMs;
    let start = 0;

    function tick(now: number) {
      if (!start) start = now;
      const elapsed = (now - start) % cycle;
      setFraction(Math.min(elapsed / durationMs, 1));
      frameRef.current = requestAnimationFrame(tick);
    }

    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
  }, [active, durationMs, pauseMs, reducedMotion]);

  return fraction;
}

export interface SmoothPosition {
  lng: number;
  lat: number;
  bearing: number;
}

/**
 * Lleva el marcador desde donde esta hasta `target` en `durationMs`.
 *
 * La interpolacion es LINEAL a proposito, aunque el resto de la app use
 * curvas propias: esto no es una transicion de interfaz que deba sentirse
 * "suave", es estimacion de posicion entre dos muestras reales. Con una
 * curva de aceleracion, el vehiculo frenaria y arrancaria cada 2 segundos
 * sin que nada en el mundo simulado lo justifique.
 */
export function useSmoothLngLat(
  target: { lng: number; lat: number } | null,
  durationMs = 2000,
): SmoothPosition | null {
  const reducedMotion = usePrefersReducedMotion();
  const [position, setPosition] = useState<SmoothPosition | null>(null);
  const positionRef = useRef<SmoothPosition | null>(null);
  const frameRef = useRef(0);

  useEffect(() => {
    positionRef.current = position;
  }, [position]);

  const lng = target?.lng ?? null;
  const lat = target?.lat ?? null;

  useEffect(() => {
    if (lng === null || lat === null) {
      setPosition(null);
      return;
    }

    const from = positionRef.current;
    // Primera muestra (o salto tras reduced-motion): se coloca directo, sin
    // animar desde un origen que no significa nada.
    if (!from || reducedMotion) {
      setPosition({ lng, lat, bearing: from?.bearing ?? 0 });
      return;
    }

    const deltaLng = lng - from.lng;
    const deltaLat = lat - from.lat;
    const moved = Math.hypot(deltaLng * Math.cos((lat * Math.PI) / 180), deltaLat);

    // Umbral ~1 metro en grados: por debajo de eso el "rumbo" que saldria es
    // puro ruido de redondeo y haria girar el icono estando quieto.
    const heading =
      moved > 1e-5
        ? (Math.atan2(deltaLng * Math.cos((lat * Math.PI) / 180), deltaLat) * 180) / Math.PI
        : from.bearing;

    let start = 0;

    function tick(now: number) {
      if (!start) start = now;
      const amount = Math.min((now - start) / durationMs, 1);

      setPosition({
        lng: from!.lng + deltaLng * amount,
        lat: from!.lat + deltaLat * amount,
        // El rumbo si se suaviza (y por el camino corto): el giro del icono
        // es interfaz, el desplazamiento es dato.
        bearing: lerpAngle(from!.bearing, heading, Math.min(amount * 2, 1)),
      });

      if (amount < 1) frameRef.current = requestAnimationFrame(tick);
    }

    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
  }, [lng, lat, durationMs, reducedMotion]);

  return position;
}
