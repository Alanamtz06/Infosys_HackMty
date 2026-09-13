# Frontend — Nova

React + Vite + TypeScript + Tailwind. Tablero con mapa 3D (tiles de OpenStreetMap
via react-map-gl + MapLibre, sin token) en dark mode, panel de control y perfil
de analítica.

## Estructura

```
src/
  App.tsx                Navegacion entre Simulacion y Perfil
  pages/                  SimulationPage, ProfilePage
  components/
    map/                  MapView, DeliveryMarker, OrderMarker
    dashboard/            ControlPanel, VirtualClock, GodModeButtons, ScoreboardModal
    profile/              ProfileStats, EarningsChart, TimeFilterSelector
    audit/                AuditDecisionButton, AuditExplanationCard
  services/api.ts         Cliente axios hacia el backend
  state/store.ts          Estado global (zustand)
  types/                  Tipos compartidos
```

## Setup

```bash
npm install
cp .env.example .env
npm run dev
```

## Mapa

`MapView` usa tiles rasterizados de `tile.openstreetmap.org` directamente vía
MapLibre (fork libre de Mapbox GL) — no requiere token ni cuenta. Si más
adelante se quiere un estilo vector "dark mode" real con edificios 3D, se
puede cambiar `OSM_STYLE` en `src/components/map/MapView.tsx` por un estilo
vector compatible con MapLibre (p.ej. OpenFreeMap), que también corre sin
Mapbox.

## Pendiente (ver lista general en el README raiz)

- Conectar `services/api.ts` y `state/store.ts` a datos reales via WebSocket/polling
  una vez el backend exponga el estado vivo de la simulacion.
- Reemplazar los datos mock de `ProfileStats`/`EarningsChart` por `statsApi.getHistory`.
