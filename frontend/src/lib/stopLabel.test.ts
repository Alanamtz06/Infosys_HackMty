import { describe, expect, it, vi } from "vitest";

import type { RouteStop } from "../types";
import { translateStopLabel } from "./stopLabel";

function stop(kind: RouteStop["kind"]): RouteStop {
  return { kind, label: "backend english label — must be ignored", lat: 0, lon: 0, eta_minutes: 0, order_id: null };
}

describe("translateStopLabel", () => {
  it("ignores the backend's fixed-English label for the courier stop", () => {
    const t = vi.fn(() => "Aquí estás");
    expect(translateStopLabel(stop("courier"), "Taquería El Buen Sabor", t)).toBe("Aquí estás");
    expect(t).toHaveBeenCalledWith("orderDetail.pickupHere");
  });

  it("ignores the backend's fixed-English label for the dropoff stop", () => {
    const t = vi.fn(() => "Entregar al cliente");
    expect(translateStopLabel(stop("dropoff"), "Taquería El Buen Sabor", t)).toBe("Entregar al cliente");
    expect(t).toHaveBeenCalledWith("orderDetail.dropoffOrder");
  });

  it("uses the real restaurant name for the pickup stop when present", () => {
    const t = vi.fn(() => "should not be used");
    expect(translateStopLabel(stop("pickup"), "Taquería El Buen Sabor", t)).toBe("Taquería El Buen Sabor");
    expect(t).not.toHaveBeenCalled();
  });

  it("falls back to the translated generic label when the restaurant has no name", () => {
    const t = vi.fn(() => "Recoger el pedido");
    expect(translateStopLabel(stop("pickup"), null, t)).toBe("Recoger el pedido");
    expect(t).toHaveBeenCalledWith("orderDetail.pickupOrder");
  });
});
