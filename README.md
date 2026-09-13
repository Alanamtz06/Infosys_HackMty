# Nova — Reto Infosys (HackMTY)

*(el proyecto se llamó "Lynx" al inicio del reto; se renombró a "Nova" a
mitad de desarrollo — ver la nota de sincronización en `CLAUDE.md` si vuelve
a cambiar.)*

Simulador multiagente de un repartidor de plataforma en la Zona Metropolitana
de Monterrey (ZMM) que maximiza sus ganancias netas durante un turno mediante
decisiones rentables, sobre un grafo vial real (OpenStreetMap) con tráfico
dinámico por horario. Corre **dos** agentes en paralelo sobre el mismo flujo
de órdenes — uno que decide con una regla de tarifa de reserva (MXN/hora) y
uno "novato" que acepta todo — para que la comparación sea sobre la calidad
de la decisión, no sobre la suerte del turno.

## Estructura del repositorio

```
backend/     Python + FastAPI — motor de simulación, agentes, routing, decisión, DB
frontend/    React + Vite + TS — tablero de control, mapa en vivo, dashboard, perfil
```

Cada carpeta tiene su propio `README.md` con el detalle técnico (arquitectura,
algoritmo, endpoints, tests, pendientes) y su propio `.env.example`.
`CLAUDE.md` en la raíz tiene la guía completa para trabajar en el repo con
Claude Code.

## Quickstart

```bash
# Backend
cd backend
python -m venv .venv && .venv\Scripts\activate       # Windows
pip install -r requirements.txt
cp .env.example .env                                  # completar DATABASE_URL (Tiger Data) + GEMINI_API_KEY
python -m app.db.init_db                               # tablas + DDL de Timescale (idempotente)
uvicorn app.main:app --reload                          # http://localhost:8000

# Frontend (en otra terminal)
cd frontend
npm install
cp .env.example .env      # VITE_API_URL, default http://localhost:8000
npm run dev                 # http://localhost:5173
```

Tests: `pytest -v` en `backend/`, `npm run test` en `frontend/`.

## Qué funciona de punta a punta

Esto ya no es un scaffold: el flujo completo login → turno → decisión →
persistencia → analítica corre contra datos reales.

- **Orquestación real del turno** (`backend/app/api/routes/simulation.py`):
  un reloj del mundo que corre siempre (no depende de "Start Shift"),
  generación de órdenes por proceso de Poisson sobre minutos simulados, A*
  sobre el grafo real de la ZMM con congestión por hora en 9 avenidas de
  Monterrey, y movimiento continuo del repartidor sobre su ruta — todo
  escribiendo de verdad en Tiger Data (`trip_records`), no en un dict
  desechable.
- **Dos agentes comparados en el mismo stream de órdenes**: el inteligente
  (regla de tarifa de reserva MXN/hora, no solo "Score > 0" — ver
  `backend/README.md`) y un novato que acepta todo, cada uno con su propio
  `TripRecord`.
- **Mochila de 2 pedidos**: el repartidor puede combinar un segundo pedido en
  la entrega en curso si conviene (VRPTW real vía OR-Tools), con un criterio
  geográfico barato antes de recoger el primero y costo marginal después.
- **Optimizador de turno completo (MILP)**: una herramienta offline
  (`backend/app/decision/lp_shift_optimizer.py` +
  `scripts/run_lp_shift_simulation.py`) que resuelve, con visibilidad total
  del flujo de ofertas de una ventana, el subconjunto óptimo a tomar — usada
  para medir qué tan cerca del óptimo teórico está la heurística que corre
  en vivo.
- **Dashboard en vivo** (Tiger Data): pulso del turno actual/último cerrado
  por agente, tabla de viajes recientes de toda la plataforma, y tendencia
  histórica (ganancia neta, gasolina y tiempo ahorrados) vía el continuous
  aggregate de TimescaleDB.
- **Mapa en vivo**: vehículo real animado sobre su ruta, vista previa de
  ruta bajo demanda con un vehículo fantasma recorriéndola, y un panel de
  ofertas que compara **el mismo pedido evaluado por los dos agentes lado a
  lado** antes de decidir.
- **Auditoría de decisiones vía Gemini** (`POST /audit/decision`): explicación
  en lenguaje natural de por qué el agente aceptaría/rechazaría una oferta,
  cacheada en `decision_audits`.
- **Auth real** (bcrypt, Postgres) y **bilingüe ES/EN** en todo el frontend.

## Qué falta (ver el detalle en cada README)

- **`decision/q_learning.py` sin implementar**: reposicionamiento predictivo
  del repartidor hacia zonas con mejores ofertas. El único pendiente grande
  de backend.
- **Modo autónomo y `/simulation/benchmark` sin entrada en la UI**: el
  backend ya soporta correr el agente solo (sin aprobación humana por
  oferta) y medir un turno completo agente-vs-baseline sin esperar el reloj
  del mundo; falta el botón en el frontend.
- **`ScoreboardModal` y los componentes de auditoría están construidos pero
  ninguna página los monta** todavía, aunque los endpoints que consumirían
  ya responden de verdad.
- **Redis (estado de turnos multi-worker) no se probó contra un servidor
  real** — la lógica de serialización sí está cubierta con `fakeredis`.
- **El reloj del mundo vive en el proceso**: reiniciar el backend "regresa"
  el mundo a la hora real actual; con varios workers cada uno tendría su
  propio ancla.
- **`npm run lint` no funciona** en el frontend — falta `eslint.config.js`
  (ESLint 9 requiere el formato flat).

## Variables de entorno / dependencias externas

- **Tiger Data (Postgres + TimescaleDB)**: `backend/.env` → `DATABASE_URL`.
- **Google Gemini**: `backend/.env` → `GEMINI_API_KEY`, para las
  explicaciones de auditoría.
- **OpenStreetMap**: `backend/app/engine/graph_loader.py` y `pois.py`
  descargan el grafo vial y los restaurantes de la ZMM en la primera llamada
  (vía OSMnx/Overpass) y cachean en memoria — necesita red, no necesita
  API key.

Ninguna de las tres requiere una cuenta propia del asistente: son
credenciales/decisiones que le corresponden a quien corre el proyecto.
