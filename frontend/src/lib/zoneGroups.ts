import type { PendingOrder } from "../types";

export interface ZoneGroup {
  zone: string;
  orders: PendingOrder[];
}

/** Agrupa ofertas pendientes por zona, en el orden en que cada una aparece
 * por primera vez — no alfabetico ni por conteo, para que la lista no
 * reordene sola entre un sondeo y el siguiente y el conductor pierda el
 * lugar donde iba leyendo. Es el analisis que pide el reto: "hay 2 ofertas
 * en Cumbres, 1 en Centro" de un vistazo, sin comparar renglon por renglon.
 */
export function groupByZone(orders: PendingOrder[]): ZoneGroup[] {
  const groups: ZoneGroup[] = [];
  const index = new Map<string, ZoneGroup>();

  for (const order of orders) {
    let group = index.get(order.zone);
    if (!group) {
      group = { zone: order.zone, orders: [] };
      index.set(order.zone, group);
      groups.push(group);
    }
    group.orders.push(order);
  }

  return groups;
}
