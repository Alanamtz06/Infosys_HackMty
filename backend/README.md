# Backend — Delivery Sim ZMM

Python + FastAPI. Motor de simulacion multiagente sobre un grafo de OSMnx de la
Zona Metropolitana de Monterrey.

## Estructura

```
app/
  main.py            FastAPI app + CORS + routers
  config.py           Variables de entorno (.env)
  api/routes/          Endpoints HTTP (simulation, orders, audit, stats)
  agents/              Agentes: generador de ordenes, trafico, repartidor, novato
  engine/              Reloj virtual, carga del grafo (OSMnx), reglas de trafico MTY, routing
  decision/            Formula de Score, batching, Q-Learning (reposicionamiento)
  db/                  Conexion a Tiger Data (Postgres/TimescaleDB), modelos, queries
  services/            Integracion con Gemini (auditoria de decisiones)
  schemas/             Modelos Pydantic de request/response
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
cp .env.example .env         # completar DATABASE_URL y GEMINI_API_KEY
uvicorn app.main:app --reload
```

## Pendiente (ver lista general en el README raiz)

- Provisionar base de datos Tiger Data y correr migraciones (`app/db/models.py`).
- Obtener API key de Gemini.
- Cargar/cachear el grafo OSMnx real de la ZMM (`app/engine/graph_loader.py`) — requiere
  descarga de OpenStreetMap la primera vez.
- Conectar los routers stub (`app/api/routes/*.py`) con el estado real de la simulacion
  (actualmente son placeholders sin logica de negocio).
- Definir el streaming en tiempo real hacia el frontend (WebSocket o polling).
