import type { RouteStop } from "../types";

/** Traduce una parada de ruta.
 *
 * El backend manda `stop.label` ya resuelto en ingles fijo ("You are here",
 * "Pick up the order", "Drop off to the customer" — ver _stops_for en
 * api/routes/simulation.py), porque no sabe el idioma de quien pregunta. Se
 * ignora ese texto para las dos paradas genericas y se reconstruye aqui con
 * `t()`; solo el pickup usa un dato real del backend (`pickupName`, el
 * nombre del restaurante), que no se puede inventar del lado del cliente.
 */
export function translateStopLabel(
  stop: RouteStop,
  pickupName: string | null,
  t: (key: "orderDetail.pickupHere" | "orderDetail.pickupOrder" | "orderDetail.dropoffOrder") => string,
): string {
  switch (stop.kind) {
    case "courier":
      return t("orderDetail.pickupHere");
    case "pickup":
      return pickupName ?? t("orderDetail.pickupOrder");
    case "dropoff":
      return t("orderDetail.dropoffOrder");
  }
}
