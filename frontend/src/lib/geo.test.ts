import { describe, expect, it } from "vitest";

import {
  boundsOf,
  cumulative,
  lerpAngle,
  pointAtFraction,
  projectFraction,
  sliceTo,
  totalLength,
  type LngLat,
} from "./geo";

// Linea recta al este a lo largo del ecuador: ahi `lonScale` es 1, asi que
// las distancias en grados coinciden 1 a 1 con las distancias euclideanas —
// evita tener que razonar sobre la correccion de longitud en cada asercion.
const EASTWARD: LngLat[] = [
  [0, 0],
  [1, 0],
  [3, 0], // segundo tramo mas largo, para que "por vertice" y "por fraccion" difieran
];

describe("cumulative / totalLength", () => {
  it("starts at zero and accumulates segment lengths", () => {
    const cum = cumulative(EASTWARD);
    expect(cum[0]).toBe(0);
    expect(cum[1]).toBeCloseTo(1, 6);
    expect(cum[2]).toBeCloseTo(3, 6);
  });

  it("totalLength matches the last cumulative value", () => {
    const cum = cumulative(EASTWARD);
    expect(totalLength(cum)).toBeCloseTo(3, 6);
  });

  it("returns 0 for an empty route", () => {
    expect(totalLength(cumulative([]))).toBe(0);
  });
});

describe("pointAtFraction", () => {
  it("returns the start point at t=0 and the end point at t=1", () => {
    const cum = cumulative(EASTWARD);
    expect(pointAtFraction(EASTWARD, cum, 0)).toMatchObject({ lng: 0, lat: 0 });
    const end = pointAtFraction(EASTWARD, cum, 1);
    expect(end.lng).toBeCloseTo(3, 6);
    expect(end.lat).toBeCloseTo(0, 6);
  });

  it("interpolates by LENGTH travelled, not by vertex index", () => {
    // A t=0.5 (mitad de los 3 grados totales) le toca el punto (1.5, 0), que
    // cae DENTRO del segundo tramo (1,0)->(3,0) — no en el vertice (1,0), que
    // es donde caeria si se interpolara por indice de vertice en vez de
    // longitud acumulada.
    const cum = cumulative(EASTWARD);
    const mid = pointAtFraction(EASTWARD, cum, 0.5);
    expect(mid.lng).toBeCloseTo(1.5, 6);
    expect(mid.lat).toBeCloseTo(0, 6);
  });

  it("clamps fractions outside [0, 1]", () => {
    const cum = cumulative(EASTWARD);
    expect(pointAtFraction(EASTWARD, cum, -0.5)).toMatchObject(pointAtFraction(EASTWARD, cum, 0));
    expect(pointAtFraction(EASTWARD, cum, 1.5)).toMatchObject(pointAtFraction(EASTWARD, cum, 1));
  });

  it("computes bearing 90° for due-east travel and 0° for due-north", () => {
    const cum = cumulative(EASTWARD);
    // A cualquier t estrictamente entre 0 y 1 (evitando el ultimo vertice,
    // donde no hay "siguiente" segmento que defina un rumbo) el rumbo debe
    // ser el este puro.
    expect(pointAtFraction(EASTWARD, cum, 0.25).bearing).toBeCloseTo(90, 6);

    const northward: LngLat[] = [
      [0, 0],
      [0, 1],
    ];
    const cumNorth = cumulative(northward);
    expect(pointAtFraction(northward, cumNorth, 0.25).bearing).toBeCloseTo(0, 6);
  });

  it("handles a single-point route without crashing", () => {
    const single: LngLat[] = [[5, 10]];
    expect(pointAtFraction(single, cumulative(single), 0.5)).toEqual({ lng: 5, lat: 10, bearing: 0 });
  });

  it("handles an empty route without crashing", () => {
    expect(pointAtFraction([], [], 0.5)).toEqual({ lng: 0, lat: 0, bearing: 0 });
  });
});

describe("sliceTo", () => {
  it("returns an empty slice at t=0 and the full route at t=1", () => {
    const cum = cumulative(EASTWARD);
    expect(sliceTo(EASTWARD, cum, 0)).toEqual([]);
    expect(sliceTo(EASTWARD, cum, 1)).toEqual(EASTWARD);
  });

  it("cuts EXACTLY at the fraction, not at the nearest vertex", () => {
    const cum = cumulative(EASTWARD);
    const slice = sliceTo(EASTWARD, cum, 0.5);
    // Debe traer el primer vertice completo (0,0), el vertice intermedio
    // (1,0) por el que ya paso, y terminar en el punto EXACTO interpolado
    // (1.5, 0) — no en (1,0) ni saltarse hasta (3,0).
    expect(slice).toEqual([
      [0, 0],
      [1, 0],
      [1.5, 0],
    ]);
  });

  it("returns the route as-is when it has fewer than 2 points", () => {
    const single: LngLat[] = [[1, 1]];
    expect(sliceTo(single, cumulative(single), 0.5)).toBe(single);
  });
});

describe("projectFraction", () => {
  it("is the inverse of pointAtFraction for a point that lies on the route", () => {
    const cum = cumulative(EASTWARD);
    const point = pointAtFraction(EASTWARD, cum, 0.5);
    expect(projectFraction(EASTWARD, cum, point.lng, point.lat)).toBeCloseTo(0.5, 3);
  });

  it("projects an off-route point onto its nearest segment", () => {
    // (1.5, 0.2) esta un poco al norte del segundo tramo — la proyeccion mas
    // cercana sigue siendo (1.5, 0), la misma fraccion que el punto exacto.
    const cum = cumulative(EASTWARD);
    expect(projectFraction(EASTWARD, cum, 1.5, 0.2)).toBeCloseTo(0.5, 2);
  });

  it("returns 0 for a route with fewer than 2 points", () => {
    expect(projectFraction([[0, 0]], [0], 1, 1)).toBe(0);
  });
});

describe("boundsOf", () => {
  it("returns null for an empty route", () => {
    expect(boundsOf([])).toBeNull();
  });

  it("computes the [west,south]-[east,north] envelope", () => {
    const coords: LngLat[] = [
      [-1, 2],
      [3, -4],
      [0, 0],
    ];
    expect(boundsOf(coords)).toEqual([
      [-1, -4],
      [3, 2],
    ]);
  });

  it("degenerates to a point for a single-coordinate route", () => {
    expect(boundsOf([[5, 5]])).toEqual([
      [5, 5],
      [5, 5],
    ]);
  });
});

describe("lerpAngle", () => {
  it("interpolates linearly when there is no wraparound", () => {
    expect(lerpAngle(0, 90, 0.5)).toBeCloseTo(45, 6);
  });

  it("takes the short way around the 0/360 seam", () => {
    // De 350 a 10 son 20 grados por el camino corto (cruzando el norte), no
    // 340 grados por el camino largo — a la mitad deberia estar en 0 (=360).
    const halfway = lerpAngle(350, 10, 0.5);
    const normalized = ((halfway % 360) + 360) % 360;
    expect(normalized).toBeCloseTo(0, 6);
  });

  it("returns the origin angle at amount=0 and the target at amount=1", () => {
    expect(lerpAngle(30, 200, 0)).toBeCloseTo(30, 6);
    expect(lerpAngle(30, 200, 1)).toBeCloseTo(200, 6);
  });
});
