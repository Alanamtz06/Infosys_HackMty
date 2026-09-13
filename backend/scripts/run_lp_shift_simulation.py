"""Simulacion de varios turnos (distinta hora de inicio y duracion) para
probar `decision.lp_shift_optimizer` con datos realistas: reusa el MISMO
generador de ofertas probabilistico que usa el turno en vivo
(`agents.order_generator`) sobre el grafo real de la ZMM, en vez de datos
inventados a mano.

Para cada escenario:
  1. Se fija una hora de inicio y una duracion (la "ventana" del turno).
  2. Se deja "aparecer" ofertas minuto a minuto (Poisson, igual que
     `_tick` en `api/routes/simulation.py`), sesgadas a una zona --
     "el area donde estuvo" el repartidor -- guardando en que segundo de
     la ventana broto cada una.
  3. Se corre `optimize_shift`: greedy -> reduccion del grafo -> MILP exacto.
  4. Se imprime un reporte comparando la mejor heuristica greedy contra el
     optimo exacto, y cuanto se redujo el grafo antes de resolverlo.

Uso:
    cd backend && .venv/Scripts/activate && python scripts/run_lp_shift_simulation.py
"""

from __future__ import annotations

import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.order_generator import generate_order, orders_to_generate  # noqa: E402
from app.config import settings  # noqa: E402
from app.decision.lp_shift_optimizer import OrderSpec, optimize_shift  # noqa: E402
from app.engine.graph_loader import apply_traffic, load_graph  # noqa: E402
from app.engine.pois import load_restaurants  # noqa: E402


@dataclass
class Scenario:
    label: str
    start_hour: float  # hora del dia (0-24) en que arranca la ventana
    duration_minutes: float  # cuanto dura la ventana
    zone_center: tuple[float, float] | None  # "el area donde estuvo"; None = centro de la ciudad


MAX_ORDERS_PER_SCENARIO = 16
# Con N pedidos hay 2N+1 nodos; construir el grafo cuesta 2 Dijkstra
# "single-source" por nodo (tiempo + distancia) sobre el grafo REAL de la
# ZMM (~29k nodos) — tratable para un puñado de decenas de nodos, pero una
# ventana de hora pico muy larga puede generar demasiadas ofertas para que
# esto siga siendo interactivo. Recortar aqui (muestreo aleatorio, no las
# primeras N) es la salvaguarda simple; en un turno real esto no aplica —
# ahi las ofertas SE VAN resolviendo una a la vez conforme aparecen (ver
# `batching.py`/`lp_shift_optimizer` corriendo sobre una ventana movil mas
# chica), no de golpe sobre todo el turno.


def _simulate_order_stream(graph, restaurants, scenario: Scenario, seed: int) -> tuple[list[OrderSpec], int]:
    """Reproduce, minuto a minuto, EXACTAMENTE el mismo proceso de aparicion
    de ofertas que corre el turno en vivo (`orders_to_generate` +
    `generate_order`), pero de una sola vez para toda la ventana en vez de
    ir tick por tick — total determinismo controlado por `seed` para que la
    corrida sea reproducible."""
    random.seed(seed)
    orders: list[OrderSpec] = []
    minute = 0.0
    while minute < scenario.duration_minutes:
        virtual_hour = (scenario.start_hour + minute / 60.0) % 24
        how_many = orders_to_generate(virtual_hour, 1.0)  # 1 minuto simulado por paso
        for _ in range(how_many):
            raw = generate_order(graph, restaurants, virtual_hour=virtual_hour, near_point=scenario.zone_center)
            orders.append(
                OrderSpec(
                    id=raw["id"],
                    pickup=(raw["pickup_lat"], raw["pickup_lon"]),
                    dropoff=(raw["dropoff_lat"], raw["dropoff_lon"]),
                    fare=raw["fare"],
                    emerged_at=minute * 60.0,
                )
            )
        minute += 1.0
    raw_count = len(orders)
    if len(orders) > MAX_ORDERS_PER_SCENARIO:
        orders = random.sample(orders, MAX_ORDERS_PER_SCENARIO)
        orders.sort(key=lambda o: o.emerged_at)
    return orders, raw_count


def _print_report(scenario: Scenario, orders: list[OrderSpec], raw_order_count: int, result, elapsed: float) -> None:
    plan = result.plan
    print(f"\n{'=' * 70}")
    print(f"Escenario: {scenario.label}")
    print(f"  hora de inicio={scenario.start_hour:.1f}h  duracion={scenario.duration_minutes:.0f} min")
    if raw_order_count > len(orders):
        print(f"  ofertas aparecidas durante la ventana: {raw_order_count} (recortado a {len(orders)} al azar, ver MAX_ORDERS_PER_SCENARIO)")
    else:
        print(f"  ofertas aparecidas durante la ventana: {len(orders)}")
    print(f"  arcos: {result.full_arc_count} -> reducidos a {result.reduced_arc_count} "
          f"({100 * result.reduced_arc_count / max(result.full_arc_count, 1):.1f}% del grafo completo)")
    print("  --- heuristicas greedy ---")
    for g in result.greedy_solutions:
        served = sum(1 for _ in g.path) // 2  # aprox: cada pedido = 2 nodos
        print(f"    {g.name:<22} ganancia neta = ${g.net_profit:,.2f} MXN  (paradas visitadas: {len(g.path) - 1})")
    print(f"  mejor greedy: ${result.best_greedy_profit:,.2f} MXN")
    print("  --- MILP exacto (OR-Tools/CBC) ---")
    print(f"    status={plan.status}  tiempo de resolver={plan.solve_seconds:.2f}s")
    print(f"    pedidos servidos: {len(plan.served_order_ids)} de {len(orders)} aparecidos")
    print(f"    ingreso bruto=${plan.total_revenue:,.2f}  gasolina=${plan.total_money_cost:,.2f}")
    print(f"    GANANCIA NETA = ${plan.net_profit:,.2f} MXN")
    if result.best_greedy_profit > 0:
        improvement = 100 * (plan.net_profit - result.best_greedy_profit) / result.best_greedy_profit
        print(f"    mejora sobre la mejor heuristica greedy: {improvement:+.1f}%")
    print(f"  tiempo total del escenario (greedy + reduccion + MILP): {elapsed:.2f}s")


def main() -> None:
    print("Cargando grafo real de la ZMM y restaurantes (una sola vez para todos los escenarios)...")
    t0 = time.time()
    graph = load_graph()
    restaurants = load_restaurants()
    print(f"listo en {time.time() - t0:.1f}s — {len(graph.nodes)} nodos, {len(restaurants)} restaurantes")

    center = (settings.city_center_lat, settings.city_center_lon)
    # Ventanas moderadas a proposito (ver MAX_ORDERS_PER_SCENARIO arriba):
    # el objetivo es demostrar el pipeline completo (greedy -> reduccion ->
    # MILP exacto) en distintas horas del dia, no forzar el peor caso de
    # tamano de grafo en una sola corrida de demo.
    scenarios = [
        Scenario("Manana tranquila, turno corto", start_hour=9.0, duration_minutes=30, zone_center=center),
        Scenario("Hora pico de comida", start_hour=13.5, duration_minutes=25, zone_center=center),
        Scenario("Tarde fuera de pico", start_hour=17.0, duration_minutes=30, zone_center=center),
        Scenario("Pico de cena", start_hour=20.0, duration_minutes=25, zone_center=center),
        Scenario("Madrugada, casi sin demanda", start_hour=2.0, duration_minutes=45, zone_center=center),
    ]

    for idx, scenario in enumerate(scenarios):
        apply_traffic(graph, scenario.start_hour)
        orders, raw_count = _simulate_order_stream(graph, restaurants, scenario, seed=1000 + idx)
        print(f"\nEscenario '{scenario.label}': {raw_count} ofertas generadas, optimizando...", flush=True)
        if not orders:
            print(f"\n{'=' * 70}\nEscenario: {scenario.label} — no aparecio ninguna oferta en esta ventana, se omite.")
            continue

        t0 = time.time()
        result = optimize_shift(
            graph,
            orders=orders,
            start_position=scenario.zone_center or center,
            window_seconds=scenario.duration_minutes * 60.0,
        )
        elapsed = time.time() - t0
        _print_report(scenario, orders, raw_count, result, elapsed)
        sys.stdout.flush()


if __name__ == "__main__":
    main()
