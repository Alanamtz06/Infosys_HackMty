import { Marker } from "react-map-gl/maplibre";

interface Props {
  lat: number;
  lon: number;
}

// Animacion via la skill `animate` del proyecto:
// - Purpose: state indication — distingue al repartidor (unico, en movimiento)
//   de los pedidos (estaticos) sin depender solo del color.
// - Tool: CSS animation (motion continuo, no ligado a una interaccion) —
//   la opcion mas barata que funciona, sin libreria de motion.
// - Properties: solo transform/opacity (bob, pulso del anillo).
// - Easing: pop-in usa una curva "back" (easings.co) para la entrada unica al
//   montar; bob usa la ease-in-out fuerte de la tabla para el balanceo
//   continuo; pulse-ring usa la ease-out fuerte porque cada ciclo "sale" del
//   centro y se desvanece.
// - Reduced motion: cubierto globalmente en index.css (las animaciones se
//   detienen pero el marcador y la gorrita siguen visibles en su estado
//   final, asi que no se pierde informacion).
export function DeliveryMarker({ lat, lon }: Props) {
  return (
    <Marker latitude={lat} longitude={lon}>
      <div className="animate-pop-in relative flex h-11 w-11 items-center justify-center">
        <span className="absolute h-9 w-9 animate-pulse-ring rounded-full bg-plum/40" />

        <div className="animate-bob relative z-10">
          {/* Gorrita: distingue al repartidor de un pedido a simple vista */}
          <svg
            viewBox="0 0 28 18"
            className="absolute -top-2.5 -right-1 z-20 h-4 w-6 rotate-[18deg] drop-shadow-sm"
          >
            <path
              d="M5 15C5 7.5 10 3 15 3s10 4.5 10 12"
              fill="none"
              stroke="#684959"
              strokeWidth="2.2"
              strokeLinecap="round"
            />
            <rect x="15" y="12.3" width="11.5" height="3.4" rx="1.7" fill="#E5CAD9" stroke="#684959" strokeWidth="1" />
          </svg>

          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-plum text-paper shadow-[0_2px_10px_rgba(104,73,89,0.45)] ring-2 ring-paper">
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor">
              <circle cx="12" cy="8.4" r="3.3" />
              <path d="M4.6 20.2c0-4.5 3.3-7.6 7.4-7.6s7.4 3.1 7.4 7.6a1 1 0 0 1-1 1H5.6a1 1 0 0 1-1-1Z" />
            </svg>
          </div>
        </div>
      </div>
    </Marker>
  );
}
