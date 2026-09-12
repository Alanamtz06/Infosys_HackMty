# Lynx — Reto Infosys (HackMTY)

Simulador multiagente de un repartidor de plataforma en la Zona Metropolitana de
Monterrey (ZMM) que maximiza sus ganancias netas durante un turno mediante
decisiones rentables, usando un sistema multiagente sobre un grafo vial real
(OpenStreetMap) con tráfico dinámico por horario.

## Estructura del repositorio

```
backend/     Python + FastAPI — motor de simulación, agentes, routing, decisión, DB
frontend/    React + Vite + TS — tablero de control, mapa 3D, perfil de analítica
docs/        Notas de arquitectura adicionales (opcional)
```

Cada carpeta tiene su propio `README.md` con setup e instrucciones. Ver también
`.env.example` en cada una para las variables requeridas.

## Quickstart

```bash
# Backend
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload

# Frontend (en otra terminal)
cd frontend
npm install
cp .env.example .env
npm run dev
```

## Lo que ya está scaffolded

- **Backend:** FastAPI con routers stub (`simulation`, `orders`, `audit`, `stats`),
  reloj virtual, tabla de reglas de tráfico de Monterrey (las 9 vialidades dadas),
  fórmula de Score, esqueleto de batching y Q-Learning, capa de conexión a Tiger Data
  (SQLAlchemy), y el prompt de auditoría con Gemini.
- **Frontend:** App React con navegación Simulación/Perfil, mapa con tiles de
  OpenStreetMap (MapLibre, sin token) en dark mode con pitch 3D, panel de
  control con reloj virtual y botones de Modo Dios (separados en su propio
  grupo, arrancan en "Normal" — nunca activos por defecto), selector de agente
  (inteligente/novato), y página de perfil con gráfica de ganancias y filtros
  de tiempo (recharts + zustand).

Todo lo anterior es **estructura y contratos**, no el sistema completo — los
`TODO` en cada archivo marcan dónde falta conectar la lógica real.

## Cosas que yo (Claude) no puedo hacer por ti

Requieren credenciales, cuentas externas, o decisiones que solo tú puedes tomar:

1. **Cuenta y API key de Tiger Data / TimescaleDB.** Necesitas provisionar la
   instancia (la side quest de MLH pide usar Tiger Data específicamente) y
   ponerla en `backend/.env` como `DATABASE_URL`. Yo no puedo crear cuentas
   ni ejecutar migraciones contra una base de datos que no existe todavía.
2. **API key de Google Gemini.** Necesaria en `backend/.env` como
   `GEMINI_API_KEY` para que `app/services/gemini_service.py` funcione.
3. **Descarga de datos de OpenStreetMap para la ZMM.** `app/engine/graph_loader.py`
   usa OSMnx para descargar el grafo vial en tiempo real desde internet — la
   primera carga puede tardar y requiere que ejecutes el backend con acceso a
   red (yo no tengo forma de descargarlo y dejarlo cacheado en este entorno).
4. **Registro/entrega del hackathon** (formularios de Infosys/MLH, video demo,
   submission en Devpost, etc.) — son acciones administrativas fuera del código.
5. **Correr y probar la app end-to-end en un navegador real** para validar la
   experiencia de usuario del dashboard — puedo revisar el código pero no
   sustituyo una prueba manual tuya con los datos y tokens reales.
6. **Decisiones de producto no especificadas**, como el diseño visual exacto
   (colores, tipografía más allá de dark mode), el algoritmo fino de generación
   de órdenes, o los parámetros exactos de Q-Learning (tamaño de grilla,
   tasa de aprendizaje) — dejé valores por defecto razonables, pero deben
   calibrarse con datos/pruebas reales.

## Qué necesita cada parte para poder avanzar

| Parte | Qué necesita |
| :--- | :--- |
| `backend/app/db/*` | `DATABASE_URL` de Tiger Data + correr migraciones/`create_hypertable` |
| `backend/app/services/gemini_service.py` | `GEMINI_API_KEY` |
| `backend/app/engine/graph_loader.py` | Acceso a internet para descargar OSM (o un `.graphml` cacheado) |
| `backend/app/api/routes/*.py` | Conectar los stubs con una sesión de simulación real (in-memory o Redis) que orqueste `VirtualClock` + `TrafficAgent` + `DeliveryAgent` |
| `frontend/src/components/map/MapView.tsx` | Nada — usa tiles públicos de OpenStreetMap sin token |
| `frontend/src/state/store.ts` | Definir el mecanismo de tiempo real (WebSocket o polling) hacia el backend |
| `frontend/src/components/profile/*` | Datos reales desde `/stats/history/{period}` una vez haya registros en la base de datos |
