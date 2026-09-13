import { describe, expect, it } from "vitest";

import type { PendingOrder } from "../types";
import { groupByZone } from "./zoneGroups";

function order(overrides: Partial<PendingOrder> & { order_id: string; zone: string }): PendingOrder {
  return {
    pickup_name: null,
    pickup_lat: 0,
    pickup_lon: 0,
    dropoff_lat: 0,
    dropoff_lon: 0,
    fare: 50,
    distance_km: 2,
    time_minutes: 10,
    gas_cost: 1.6,
    time_cost: 15,
    score: 33.4,
    should_accept: true,
    novice: { outcome: "accepted", score: 30, fare: 50, distance_km: 2, time_minutes: 10 },
    ...overrides,
  };
}

describe("groupByZone", () => {
  it("returns an empty list for no orders", () => {
    expect(groupByZone([])).toEqual([]);
  });

  it("clusters orders sharing a zone into one group", () => {
    const orders = [
      order({ order_id: "a", zone: "Cumbres" }),
      order({ order_id: "b", zone: "Centro" }),
      order({ order_id: "c", zone: "Cumbres" }),
    ];

    const groups = groupByZone(orders);
    expect(groups).toHaveLength(2);
    expect(groups.find((g) => g.zone === "Cumbres")?.orders.map((o) => o.order_id)).toEqual(["a", "c"]);
    expect(groups.find((g) => g.zone === "Centro")?.orders.map((o) => o.order_id)).toEqual(["b"]);
  });

  it("orders groups by first appearance, not alphabetically or by count", () => {
    const orders = [
      order({ order_id: "a", zone: "San Nicolas" }),
      order({ order_id: "b", zone: "Centro" }),
      order({ order_id: "c", zone: "Centro" }),
      order({ order_id: "d", zone: "Centro" }),
    ];

    // "San Nicolas" aparece primero aunque "Centro" tenga mas ofertas — el
    // orden de lectura no debe saltar segun cual zona gana en conteo.
    expect(groupByZone(orders).map((g) => g.zone)).toEqual(["San Nicolas", "Centro"]);
  });

  it("keeps every order exactly once across all groups", () => {
    const orders = [
      order({ order_id: "a", zone: "Cumbres" }),
      order({ order_id: "b", zone: "Centro" }),
      order({ order_id: "c", zone: "Cumbres" }),
      order({ order_id: "d", zone: "Contry" }),
    ];

    const total = groupByZone(orders).reduce((sum, group) => sum + group.orders.length, 0);
    expect(total).toBe(orders.length);
  });
});
