from pydantic import BaseModel


class SimulationStart(BaseModel):
    user_id: str | None = None
    vehicle: str = "moto"  # "moto" | "auto" — viene del vehicle_type elegido al loguearse


class NoviceOutcomeOut(BaseModel):
    """Lo que el agente novato YA decidio para esta misma orden, al instante
    en que se genero — no una prediccion, el veredicto real (ver
    api/routes/simulation.py::_record_novice_decision)."""

    outcome: str  # "accepted" | "busy" | "unreachable"
    score: float | None = None
    fare: float | None = None
    distance_km: float | None = None
    time_minutes: float | None = None


class PendingOrderOut(BaseModel):
    order_id: str
    pickup_name: str | None
    # Zona nombrada de la ZMM mas cercana al restaurante (ver
    # engine/zones.py) — deja comparar ofertas por vecindario en vez de solo
    # como lista plana ("2 en Cumbres, 1 en Centro").
    zone: str
    pickup_lat: float
    pickup_lon: float
    dropoff_lat: float
    dropoff_lon: float
    fare: float
    distance_km: float
    time_minutes: float
    gas_cost: float
    time_cost: float
    score: float
    should_accept: bool
    # Veredicto del novato sobre la MISMA orden — la comparacion lado a lado
    # del panel de ofertas se arma con esto, no con una simulacion aparte.
    novice: NoviceOutcomeOut


class RouteStopOut(BaseModel):
    """Una parada de la ruta, en el orden en que se visita."""

    kind: str  # "courier" | "pickup" | "dropoff"
    label: str
    lat: float
    lon: float
    # Minutos (simulados) desde el inicio de la ruta hasta llegar aqui. Para
    # el punto de partida es 0.
    eta_minutes: float


class RouteLegOut(BaseModel):
    """Un tramo entre dos paradas consecutivas."""

    kind: str  # "to_pickup" | "to_dropoff"
    distance_km: float
    minutes: float


class RoutePreviewOut(BaseModel):
    """La ruta que se recorreria si se acepta una orden pendiente.

    Se calcula bajo demanda (GET /simulation/route), no en cada tick: ruteo
    sobre el grafo real para las 5 ordenes pendientes en cada sondeo de 2s
    seria caro y casi siempre desperdiciado, porque el conductor solo mira
    una a la vez.
    """

    order_id: str
    pickup_name: str | None
    # GeoJSON-style [lon, lat] — el orden que espera MapLibre.
    coordinates: list[list[float]]
    # Indice dentro de `coordinates` donde cae el pickup: parte la linea en
    # el tramo de ida (al restaurante) y el de entrega.
    pickup_index: int
    stops: list[RouteStopOut]
    legs: list[RouteLegOut]
    total_minutes: float
    distance_km: float
    fare: float
    score: float


class ActiveRouteOut(BaseModel):
    """Una entrega EN CURSO, con el avance real del repartidor sobre ella."""

    order_id: str
    pickup_name: str | None
    coordinates: list[list[float]]
    pickup_index: int
    stops: list[RouteStopOut]
    # 0..1 sobre el tiempo total de la entrega (incluye tiempo de servicio).
    progress: float
    phase: str  # "to_pickup" | "to_dropoff"
    courier_lat: float
    courier_lon: float
    eta_minutes: float
    fare: float
    # True solo para la entrega que el repartidor esta cursando ahora; las
    # demas estan encoladas y todavia no arrancan.
    is_current: bool


class SimEventOut(BaseModel):
    ts: str
    type: str
    message: str


class SimulationState(BaseModel):
    run_id: str
    vehicle: str
    virtual_hour: float
    virtual_minute: float
    is_finished: bool
    net_earnings: float
    pending_orders: list[PendingOrderOut]
    events: list[SimEventOut]

    # --- Campos aditivos (el frontend actual no los lee todavia) -------------
    # JSON extra no rompe nada en TypeScript: `SimulationState` en
    # frontend/src/types/index.ts simplemente no los declara. Estan aqui para
    # que el integrante que trabaje el frontend los pueda usar sin tocar el
    # backend otra vez.

    # Hora simulada completa (ISO sin zona horaria, a proposito: ver
    # engine/virtual_clock.py::WorldClock.iso_timestamp).
    sim_time: str
    time_acceleration: float

    # Posicion en vivo del repartidor, interpolada sobre su ruta real. Para
    # reemplazar PLACEHOLDER_RIDER_POSITION en MapView.tsx.
    courier_lat: float | None
    courier_lon: float | None
    active_deliveries: int
    deliveries_completed: int

    # Geometria de las entregas en curso: lo que el mapa necesita para dibujar
    # la ruta y mover el vehiculo encima de ella. Aditivo respecto a
    # `active_deliveries` (que sigue siendo solo el conteo).
    active_routes: list[ActiveRouteOut]

    orders_accepted: int

    # Acumulado del agente novato sobre el MISMO stream de ordenes: es lo que
    # ScoreboardModal.tsx necesita para `noviceEarnings`.
    novice_earnings: float
    session_id: str


class BenchmarkRequest(BaseModel):
    hours: float = 8.0  # horas simuladas de turno
    start_hour: float | None = None  # None = arranca en la hora del mundo
    vehicle: str = "moto"
    user_id: str | None = None


class AgentBenchmark(BaseModel):
    net_earnings: float
    accepted: int
    rejected: int
    missed_while_busy: int
    minutes_worked: float
    distance_km: float
    earnings_per_hour: float


class BenchmarkResult(BaseModel):
    """Resultado de un turno headless: agente autonomo vs novato sobre el
    mismo stream de ordenes."""

    session_id: str
    hours: float
    start_hour: float
    vehicle: str
    orders_offered: int
    inteligente: AgentBenchmark
    novato: AgentBenchmark
    advantage_mxn: float
    advantage_pct: float


class DecisionRequest(BaseModel):
    run_id: str
    order_id: str
    accept: bool


class RunIdRequest(BaseModel):
    run_id: str
