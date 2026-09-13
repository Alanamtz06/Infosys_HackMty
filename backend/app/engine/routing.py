"""Calculo de rutas sobre el grafo afectado por trafico.

Usa A* (en vez del Dijkstra simple que habia antes) con una heuristica de
distancia great-circle sobre la velocidad maxima del grafo — una cota
inferior admisible del tiempo real, asi que A* sigue dando la ruta optima
pero explora muchos menos nodos que Dijkstra. Importa porque
`/simulation/state` se sondea cada 2s desde el frontend y cada tick puede
disparar un calculo de ruta nuevo.
"""

import math
import random

import networkx as nx
import numpy as np
import osmnx as ox

# Cota superior de velocidad en la ZMM, usada solo para que la heuristica de
# A* nunca sobreestime el tiempo real (si sobreestimara, A* dejaria de ser
# optimo).
_MAX_SPEED_KPH = 110.0


def _travel_time_heuristic(graph: nx.MultiDiGraph, max_speed_kph: float = _MAX_SPEED_KPH):
    max_speed_mps = max_speed_kph * 1000 / 3600

    def heuristic(u, v) -> float:
        y1, x1 = graph.nodes[u]["y"], graph.nodes[u]["x"]
        y2, x2 = graph.nodes[v]["y"], graph.nodes[v]["x"]
        dist_m = ox.distance.great_circle(y1, x1, y2, x2)
        return float(dist_m) / max_speed_mps

    return heuristic


def _path_time_and_distance(graph: nx.MultiDiGraph, route: list[int]) -> tuple[float, float]:
    """Devuelve floats de Python, no numpy.

    Los atributos del grafo de OSMnx llegan como `numpy.float64`, y si se
    dejan pasar contaminan todo lo que se calcule con ellos: el Score
    termina siendo un `np.float64` y `should_accept` un `np.bool_`, que
    Pydantic serializa con un DeprecationWarning en cada respuesta.
    """
    travel_time = sum(
        min(d["travel_time"] for d in graph.get_edge_data(u, v).values()) for u, v in zip(route[:-1], route[1:])
    )
    distance = sum(
        min(d["length"] for d in graph.get_edge_data(u, v).values()) for u, v in zip(route[:-1], route[1:])
    )
    return float(travel_time), float(distance)


def shortest_route(graph: nx.MultiDiGraph, origin_point: tuple[float, float], dest_point: tuple[float, float]):
    """Devuelve (nodos_de_ruta, tiempo_total_seg, distancia_total_m) usando A* sobre `travel_time`.

    Lanza `networkx.NetworkXNoPath` si un cierre de calle (ver
    `apply_road_closure`) deja a `dest_point` inalcanzable desde `origin_point`.
    """
    origin_node = ox.nearest_nodes(graph, origin_point[1], origin_point[0])
    dest_node = ox.nearest_nodes(graph, dest_point[1], dest_point[0])

    route = nx.astar_path(graph, origin_node, dest_node, heuristic=_travel_time_heuristic(graph), weight="travel_time")
    travel_time, distance = _path_time_and_distance(graph, route)
    return route, travel_time, distance


def try_shortest_route(
    graph: nx.MultiDiGraph,
    origin_point: tuple[float, float],
    dest_point: tuple[float, float],
) -> tuple[list[int], float, float] | None:
    """Igual que `shortest_route` pero devuelve `None` en vez de explotar
    cuando el destino es inalcanzable.

    Dos formas distintas de "inalcanzable" que hay que cubrir las dos:
      - `networkx.NetworkXNoPath` / `NodeNotFound`: no existe ningun camino.
      - un camino con peso infinito: si la UNICA arista que conecta dos
        puntos esta cerrada (`apply_road_closure`), A* igual devuelve ese
        camino, con tiempo infinito, sin lanzar excepcion.

    Usalo en cualquier parte que corra dentro del loop de la simulacion: un
    cierre de calle no debe tumbar `/simulation/state`.
    """
    try:
        route, travel_time, distance = shortest_route(graph, origin_point, dest_point)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None
    if not math.isfinite(travel_time):
        return None
    return route, travel_time, distance


def get_travel_time_matrix(graph: nx.MultiDiGraph, points: list[tuple[float, float]]) -> np.ndarray:
    """Matriz NxN de tiempos de viaje (segundos) entre `points` (lat, lon).

    Pensada como input directo para `decision.vrptw_solver.solve_route`
    (capa de batching): cada `points[i]` se snapea al nodo del grafo mas
    cercano una sola vez, y la diagonal es 0. `float('inf')` si un cierre de
    calle deja un par sin ruta.

    Hace UN Dijkstra por origen (a todos los destinos de una pasada) en vez
    de N*N busquedas A* independientes. La diferencia importa mucho: esto
    corre dentro del tick de `/simulation/state`, y con N*N A* un solo tick
    llegaba a tardar decenas de segundos — suficiente para que el reloj
    acelerado del mundo se comiera media hora simulada en una sola request.
    """
    nodes = [ox.nearest_nodes(graph, lon, lat) for lat, lon in points]
    targets = set(nodes)

    n = len(nodes)
    matrix = np.full((n, n), float("inf"))
    np.fill_diagonal(matrix, 0.0)

    for i, origin in enumerate(nodes):
        lengths = nx.single_source_dijkstra_path_length(graph, origin, weight="travel_time")
        for j, dest in enumerate(nodes):
            if i == j:
                continue
            if dest in targets and dest in lengths:
                matrix[i, j] = lengths[dest]
    return matrix


def get_travel_distance_matrix(graph: nx.MultiDiGraph, points: list[tuple[float, float]]) -> np.ndarray:
    """Matriz NxN de distancias (metros) entre `points` (lat, lon).

    Mismo patron que `get_travel_time_matrix` (un Dijkstra por origen, peso
    `length` en vez de `travel_time`) — usada por `decision.lp_shift_optimizer`
    para el costo de gasolina de cada arco. Nota: la ruta MAS CORTA en
    distancia no siempre coincide nodo-a-nodo con la ruta MAS RAPIDA en
    tiempo (`get_travel_time_matrix`) cuando hay vias con velocidades muy
    distintas — para el modelo de decision es una aproximacion aceptable
    (mismo criterio que el fare estimado con great-circle en
    `order_generator.generate_order`: barato y suficiente para decidir, no
    para trazar el mapa).
    """
    nodes = [ox.nearest_nodes(graph, lon, lat) for lat, lon in points]
    targets = set(nodes)

    n = len(nodes)
    matrix = np.full((n, n), float("inf"))
    np.fill_diagonal(matrix, 0.0)

    for i, origin in enumerate(nodes):
        lengths = nx.single_source_dijkstra_path_length(graph, origin, weight="length")
        for j, dest in enumerate(nodes):
            if i == j:
                continue
            if dest in targets and dest in lengths:
                matrix[i, j] = lengths[dest]
    return matrix


def route_total_time(graph: nx.MultiDiGraph, route: list[int]) -> float:
    """Tiempo total (segundos) de recorrer `route` con el trafico actual."""
    if len(route) < 2:
        return 0.0
    travel_time, _distance = _path_time_and_distance(graph, route)
    return travel_time


def position_along_route(
    graph: nx.MultiDiGraph,
    route: list[int],
    elapsed_seconds: float,
    dwell_checkpoints: list[tuple[float, float]] | None = None,
) -> tuple[float, float]:
    """(lat, lon) del punto donde va el repartidor tras `elapsed_seconds` sobre `route`.

    Interpola linealmente DENTRO de la arista en curso, en proporcion al
    tiempo de viaje de esa arista — no es exacto sobre la geometria real de
    la calle (ignora la curvatura intermedia de OSM), pero es suficiente
    para mover un marcador en el mapa de forma continua y creible.

    `dwell_checkpoints` = [(tiempo_fisico_acumulado_al_llegar, segundos_de_pausa), ...]
    (ver `app.decision.batching.plan_backpack_route` / `_start_delivery`):
    pausas de servicio (esperar la comida en el restaurante) que ocurren EN el
    nodo donde se llega a esa marca de tiempo fisico, no acumuladas al final
    de la ruta. Sin esto, `elapsed_seconds` (que incluye esas pausas via
    `total_seconds`) simplemente se sale del presupuesto fisico de `route` y
    el repartidor queda congelado en el ULTIMO nodo durante todo ese tiempo
    de mas — un bug real que se veia como "se congela y luego sigue en otro
    lado", facil de confundir con un teletransporte.
    """
    if not route:
        raise ValueError("route vacia")
    if len(route) == 1 or elapsed_seconds <= 0:
        node = graph.nodes[route[0]]
        return float(node["y"]), float(node["x"])

    checkpoints = sorted(dwell_checkpoints or [])
    checkpoint_idx = 0
    remaining = elapsed_seconds
    physical_elapsed = 0.0

    for u, v in zip(route[:-1], route[1:]):
        # Cualquier pausa de servicio que ocurra al llegar a este nodo (antes
        # de tomar la siguiente arista) se consume aqui, congelado en `u`.
        while checkpoint_idx < len(checkpoints) and checkpoints[checkpoint_idx][0] <= physical_elapsed + 1e-6:
            dwell = checkpoints[checkpoint_idx][1]
            checkpoint_idx += 1
            if remaining <= dwell:
                node = graph.nodes[u]
                return float(node["y"]), float(node["x"])
            remaining -= dwell

        edge_time = min(d["travel_time"] for d in graph.get_edge_data(u, v).values())
        if not math.isfinite(edge_time):
            edge_time = 0.0
        if remaining <= edge_time or edge_time == 0:
            fraction = (remaining / edge_time) if edge_time > 0 else 1.0
            fraction = min(max(fraction, 0.0), 1.0)
            start, end = graph.nodes[u], graph.nodes[v]
            return (
                float(start["y"] + (end["y"] - start["y"]) * fraction),
                float(start["x"] + (end["x"] - start["x"]) * fraction),
            )
        remaining -= edge_time
        physical_elapsed += edge_time

    last = graph.nodes[route[-1]]
    return float(last["y"]), float(last["x"])


def apply_road_closure(graph: nx.MultiDiGraph, u: int, v: int) -> None:
    """Simula el cierre de una calle: pone `travel_time` (y `base_travel_time`,
    para que sobreviva al siguiente `apply_traffic`) de `(u, v)` en infinito.

    Cierra tambien las aristas paralelas si las hay (MultiDiGraph). Si hay
    una ruta alterna, `shortest_route`/A* la usa automaticamente en la
    siguiente consulta.
    """
    if not graph.has_edge(u, v):
        raise ValueError(f"No existe arista ({u}, {v}) en el grafo")
    for _key, data in graph[u][v].items():
        data["base_travel_time"] = float("inf")
        data["travel_time"] = float("inf")


def clear_road_closure(graph: nx.MultiDiGraph, u: int, v: int) -> None:
    """Reabre una calle cerrada con `apply_road_closure`, recalculando su
    `base_travel_time` real a partir de `length`/`speed_kph`."""
    if not graph.has_edge(u, v):
        return
    for _key, data in graph[u][v].items():
        speed_kph = data.get("speed_kph")
        length_m = data.get("length")
        if speed_kph and length_m:
            data["base_travel_time"] = length_m / (speed_kph * 1000 / 3600)
        data["travel_time"] = data["base_travel_time"]


def simulate_random_closure(graph: nx.MultiDiGraph, near_point: tuple[float, float] | None = None) -> dict | None:
    """Cierra una calle real al azar (opcionalmente cerca de `near_point`) para
    la demo de "God Mode" — un accidente/obra que fuerza un desvio a mitad
    de turno.

    Devuelve `{"u", "v", "street_name"}` de lo que se cerro, o `None` si no
    se encontro ninguna arista candidata (grafo vacio). Guarda ese dict y
    pasalo a `clear_road_closure(graph, closure["u"], closure["v"])` despues
    para reabrir la calle.
    """
    if near_point is not None:
        center_node = ox.nearest_nodes(graph, near_point[1], near_point[0])
        candidates = list(graph.out_edges(center_node, keys=False))
        # si el nodo mas cercano no tiene salidas utiles, cae al azar sobre todo el grafo
        if not candidates:
            candidates = list(graph.edges(keys=False))
    else:
        candidates = list(graph.edges(keys=False))

    # evita cerrar una arista que ya esta cerrada (travel_time infinito)
    open_candidates = [
        (u, v) for u, v in candidates if all(d.get("travel_time", 0) != float("inf") for d in graph[u][v].values())
    ]
    if not open_candidates:
        return None

    u, v = random.choice(open_candidates)
    street_name = None
    for data in graph[u][v].values():
        name = data.get("name")
        street_name = name[0] if isinstance(name, list) and name else (name if isinstance(name, str) else None)
        if street_name:
            break

    apply_road_closure(graph, u, v)
    return {"u": u, "v": v, "street_name": street_name}


# --------------------------------------------------------------------------
# Geometria para el mapa
# --------------------------------------------------------------------------


def _best_edge(graph: nx.MultiDiGraph, u: int, v: int) -> dict:
    """La arista paralela que realmente se recorre: la mas rapida, igual que
    `_path_time_and_distance`. Si se tomara otra, la linea dibujada en el
    mapa no seria la calle que el Score cobro."""
    return min(graph.get_edge_data(u, v).values(), key=lambda d: d.get("travel_time", float("inf")))


def _node_xy(graph: nx.MultiDiGraph, node: int) -> tuple[float, float]:
    data = graph.nodes[node]
    return float(data["x"]), float(data["y"])


def _sq_dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def route_coordinates(graph: nx.MultiDiGraph, route: list[int]) -> list[tuple[float, float]]:
    """La ruta como `[(lon, lat), ...]` lista para pintar en MapLibre.

    Sigue la geometria REAL de la calle cuando OSMnx la trae (`geometry` de
    la arista, una LineString con los puntos intermedios de la via); solo cae
    al segmento recto nodo-a-nodo cuando no existe. La diferencia se ve: sin
    esto, una avenida curva como Constitucion se dibuja como una sucesion de
    rectas que cortan por encima del rio.

    Ojo con el sentido: OSMnx no garantiza que `geometry` este orientada de
    `u` a `v` (una via bidireccional guarda la MISMA LineString en las dos
    aristas), asi que cada tramo se voltea si su primer punto quedo mas lejos
    de `u` que el ultimo. Sin ese chequeo la ruta sale en zigzag.
    """
    if not route:
        return []
    if len(route) == 1:
        return [_node_xy(graph, route[0])]

    coords: list[tuple[float, float]] = []
    for u, v in zip(route[:-1], route[1:]):
        geometry = _best_edge(graph, u, v).get("geometry")
        if geometry is not None:
            segment = [(float(x), float(y)) for x, y in geometry.coords]
            start = _node_xy(graph, u)
            if len(segment) > 1 and _sq_dist(segment[0], start) > _sq_dist(segment[-1], start):
                segment.reverse()
        else:
            segment = [_node_xy(graph, u), _node_xy(graph, v)]

        if coords and segment and coords[-1] == segment[0]:
            segment = segment[1:]
        coords.extend(segment)

    return coords


def downsample_coordinates(
    coords: list[tuple[float, float]], max_points: int = 400
) -> list[tuple[float, float]]:
    """Adelgaza una polilinea conservando SIEMPRE el primer y el ultimo punto.

    `/simulation/state` se sondea cada 2s y arrastra la ruta de cada entrega
    en curso; una ruta larga con geometria real puede pasar de mil puntos y
    no se distingue de una de 400 al zoom al que se ve el mapa.
    """
    if len(coords) <= max_points:
        return coords
    step = len(coords) / (max_points - 1)
    thinned = [coords[int(i * step)] for i in range(max_points - 1)]
    thinned.append(coords[-1])
    return thinned
