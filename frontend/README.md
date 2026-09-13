# Frontend — Nova

React + Vite + TypeScript + Tailwind. Tablero de control con mapa en vivo
(tiles de OpenStreetMap via react-map-gl + MapLibre, sin token), panel de
comparación repartidor-inteligente-vs-novato en tiempo real, dashboard de
analítica (Tiger Data) y perfil. Tema claro ("paper"), bilingüe ES/EN.

## Estructura

```
src/
  App.tsx                 Gate de login + header global (reloj, ganancias,
                           mochila, botón de turno, nav, idioma, logout)
  pages/
    SimulationPage.tsx     Mapa + widgets flotantes (Ofertas, Bitácora)
    DashboardPage.tsx      Pulso en vivo del turno + tendencia histórica
    ProfilePage.tsx        Edición de perfil (tipo de vehículo)
  components/
    map/                   MapView, OrderMarker, StopMarker, VehicleMarker,
                            RouteLines, OrderDetailCard
    dashboard/              ShiftButton, VirtualClock, OrdersWidget, LiveLog,
                            WidgetControls, ScoreboardModal (sin montar)
    widgets/                DraggableWidget — marco común de los paneles
                            flotantes arrastrables sobre el mapa
    profile/                ProfileEdit, EarningsChart, TimeFilterSelector
    audit/                  AuditDecisionButton, AuditExplanationCard (sin montar)
  hooks/                   useDraggableWidget (drag + persistencia de
                           posición), useRouteAnimation (interpolación suave
                           de vehículos)
  lib/                     geo.ts (geometría de rutas), stopLabel.ts,
                           zoneGroups.ts (agrupar ofertas por zona)
  i18n/                    translations.ts (ES/EN) + useTranslation()
  services/api.ts          Cliente axios hacia el backend
  state/store.ts           Estado global (zustand), persiste user + language
  types/index.ts           Tipos compartidos con las respuestas del backend
```

## Setup

```bash
npm install
cp .env.example .env      # VITE_API_URL, default http://localhost:8000
npm run dev                # http://localhost:5173 (o el siguiente puerto libre)
```

`npm run lint` **no funciona todavía** — `eslint` está en las dependencias
pero no existe `eslint.config.js` (ESLint 9 requiere el formato flat). No
asumir que el lint pasa hasta que se agregue esa config.

## Tests

```bash
npm run test         # vitest run
npm run test:watch   # modo watch
```

Cubre las piezas de lógica pura sin red ni DOM real: `i18n/translations.ts`
(cobertura de llaves ES/EN), `lib/geo.ts`, `lib/stopLabel.ts`,
`lib/zoneGroups.ts` y `hooks/useDraggableWidget.ts` (persistencia en
localStorage). No hay tests de componentes con datos del backend todavía.

## Qué es real y qué no (nada queda en mock)

Toda la app consume el backend real — no quedan `SAMPLE_DATA` ni
placeholders. Lo único construido pero **no montado en ninguna página**:

- `ScoreboardModal.tsx` (consumiría `GET /stats/scoreboard`).
- `AuditDecisionButton.tsx` / `AuditExplanationCard.tsx` (consumirían
  `POST /audit/decision`, la explicación de Gemini para una decisión).

Tampoco hay entrada de UI todavía para dos capacidades que el backend ya
expone por completo: **modo autónomo** (`/simulation/start` con
`autonomous: true` — el agente decide solo, sin que el humano apruebe cada
oferta) y **`/simulation/benchmark`** (turno headless agente-vs-novato para
medir la ventaja sin esperar el reloj del mundo). Ver `backend/README.md` §
Pendiente para el detalle de ambos.

## App.tsx — header global, no un ControlPanel por página

El reloj virtual, las ganancias netas del turno, el indicador de mochila
(🎒 N/2) y el botón Iniciar/Terminar turno (`ShiftButton`) viven en el
**header de `App.tsx`**, visibles en las tres vistas — no solo en
Simulación. Antes existía un `ControlPanel.tsx` que dibujaba esa barra solo
dentro de `SimulationPage`; se retiró al fusionar el rediseño del menú
superior (`FixFrontEnd`) porque duplicaba lo que el header ya resuelve
globalmente. El único control que sigue siendo exclusivo de Simulación es
`WidgetControls` (mostrar/ocultar/resetear los paneles flotantes del mapa),
que aparece como un panel aparte arriba a la izquierda solo cuando hay un
turno activo.

## SimulationPage / MapView — el corazón de la app

`SimulationPage` sondea `GET /simulation/state` cada 2s mientras hay un
turno activo y le pasa el snapshot a `MapView` vía el store global. `MapView`
no es solo un mapa: orquesta vehículo real, vista fantasma de ruta y dos
paneles flotantes y arrastrables.

- **Vehículo real** (`VehicleMarker`): su posición viene de
  `simulation.courier_lat/lon` (o de la entrega activa,
  `active_routes[].courier_lat/lon`, mientras va en camino), animada con
  interpolación suave (`useSmoothLngLat`, `hooks/useRouteAnimation.ts`) para
  que no salte de punto a punto entre polls.
- **Vista previa de ruta** (`OrderDetailCard` → botón "ver ruta" →
  `GET /simulation/route`): se pide **solo bajo demanda**, nunca en cada
  sondeo (rutear las ofertas pendientes cada 2s sería caro y casi todo
  desperdiciado). Al llegar, dibuja la ruta completa (`PreviewRoute`) con un
  **vehículo fantasma** (`useGhostRunner`) recorriéndola en bucle para
  enseñar cómo se vería la entrega antes de aceptarla.
- **Encuadre automático** (`fitBounds`/`flyTo`): al seleccionar una oferta o
  al llegar un preview, la cámara encuadra pickup+dropoff+repartidor con
  padding asimétrico (deja espacio para los paneles flotantes) y vuelve a
  centrarse en el repartidor al deseleccionar. Envuelto en
  `safeFitBounds`/`safePadding` porque coordenadas muy cercanas pueden hacer
  que MapLibre aborte si el padding pedido no cabe.
- **`OrdersWidget`** (vive dentro de `MapView` porque necesita el estado de
  ruta que ésta calcula): lista las ofertas pendientes **agrupadas por zona**
  (`lib/zoneGroups.ts` — "2 en Cumbres, 1 en Centro" de un vistazo, sin
  reordenar entre sondeos) y, por cada una, muestra **el mismo pedido
  evaluado por los dos agentes lado a lado** — el score y la recomendación
  del inteligente contra el resultado real del novato (aceptó/ocupado/
  inalcanzable) — antes de que el conductor decida nada. Seleccionar una fila
  cambia el widget a `OrderDetailCard` (detalle, preview de ruta,
  Aceptar/Rechazar; deshabilita Aceptar si la mochila ya está llena, 2/2).
- **`LiveLog`**: bitácora de eventos en hora simulada (aceptaciones,
  rechazos, avisos de reevaluación de precio, tips de batching).
- Ambos paneles (`OrdersWidget`, `LiveLog`) son `DraggableWidget`:
  arrastrables con `transform: translate3d` (nunca `top`/`left`, para no
  disparar layout en cada frame), su posición se recuerda en localStorage
  por widget, y `WidgetControls` los cierra/reabre/resetea.

## DashboardPage — analítica en vivo, no del perfil individual

Sondea `GET /stats/live` cada 4s (tarjetas de resumen inteligente-vs-novato
del turno actual o el último cerrado, más los 25 viajes más recientes de
toda la plataforma) y `GET /stats/history/{period}` (tendencia histórica:
ganancia neta, gasolina ahorrada en MXN y tiempo ahorrado, inteligente contra
novato sobre el mismo flujo de órdenes). El filtro de periodo
(`TimeFilterSelector`) y la gráfica (`EarningsChart`) vivían antes en
`ProfilePage`; se movieron aquí porque son estadísticas del turno/negocio,
no del repartidor individual — `ProfilePage` ahora es solo edición de
vehículo (`ProfileEdit.tsx`), sin gráficas.

## Diseño e i18n

- **Tokens de color** en `tailwind.config.js`: `paper` (fondo), `ink`
  (texto), `plum` (acento primario), `blush` (acento secundario), `dust`
  (superficies/bordes), `charcoal` (texto secundario). No usar grises/azules
  crudos de Tailwind — todo pasa por estos tokens.
- Easings y animaciones custom (`fade-up`, `fade-in`, `pop-in`,
  `pulse-ring`, `bob`) también en `tailwind.config.js`; nunca `transition-all`,
  siempre la lista de propiedades explícita (`transition`/`transition-colors`).
- `MapView.tsx` aplica un filtro CSS duotono sobre los tiles crudos de OSM
  (`[&_.maplibregl-canvas]:...`) para que el mapa se sienta parte de la misma
  paleta, sin depender de un estilo vector con token.
- **Bilingüe ES/EN** (`i18n/translations.ts` + `useTranslation()`): default
  `es` (público de la ZMM), toggle en el header (`App.tsx`); el idioma se
  persiste junto al usuario en `state/store.ts`. Cada string nueva necesita
  su llave en **ambos** objetos (`es`/`en`) — `translations.test.ts` falla
  si a una le falta la otra.
- `.paper-grain` (en `src/styles/index.css`): overlay fijo de textura sutil,
  `pointer-events-none` y de opacidad baja.

## Mapa (detalle técnico)

`MapView` usa tiles rasterizados de `tile.openstreetmap.org` directamente vía
MapLibre (fork libre de Mapbox GL) — no requiere token ni cuenta. Si más
adelante se quiere un estilo vector con más control de color, cambiar
`OSM_STYLE` en `src/components/map/MapView.tsx` por un estilo vector
compatible con MapLibre (p. ej. OpenFreeMap), que también corre sin Mapbox.
