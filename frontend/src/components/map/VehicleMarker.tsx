import { Marker } from "react-map-gl/maplibre";

import type { VehicleType } from "../../types";

interface Props {
  lat: number;
  lng: number;
  /** Grados desde el norte. El glifo se dibuja apuntando hacia arriba. */
  bearing?: number;
  vehicle: VehicleType;
  /** `ghost` = previsualizacion de una oferta que aun no se acepta. */
  variant?: "live" | "ghost";
  label?: string;
}

// Siluetas CENITALES, no de perfil: el mapa se ve desde arriba, y un icono de
// perfil apuntando siempre a la derecha delata que no esta orientado con la
// calle. Vistas desde arriba, rotar por el rumbo se lee correcto en cualquier
// direccion. Ambas se dibujan apuntando al NORTE en un lienzo de 24x24.
//
// Trazos GRUESOS y formas simples a proposito: la version anterior (chasis
// fino + ruedas como rectangulos delgados) se volvia ilegible al tamaño real
// del marcador (18px sobre un circulo de 36px) — a esa escala, el detalle
// fino de linea desaparece y solo quedaban un par de trazos sueltos que no
// se leian como "vehiculo". Aqui cada forma es lo bastante grande y solida
// para sobrevivir el achicado.
function ScooterGlyph() {
  return (
    <svg viewBox="0 0 24 24" className="h-[19px] w-[19px]" aria-hidden="true">
      {/* Llantas */}
      <rect x="11" y="2" width="2" height="4" rx="1" fill="currentColor" />
      <rect x="11" y="18" width="2" height="4" rx="1" fill="currentColor" />
      {/* Manubrio */}
      <path d="M 6 6 Q 12 4 18 6 L 17 7.5 Q 12 5.5 7 7.5 Z" fill="currentColor" />
      {/* Casco del conductor */}
      <circle cx="12" cy="11" r="3.5" fill="currentColor" />
      <circle cx="12" cy="11.5" r="2.5" className="fill-plum" opacity="0.7" />
      {/* Chasis */}
      <path d="M 10.5 7 L 13.5 7 L 12.5 17 L 11.5 17 Z" fill="currentColor" />
    </svg>
  );
}

function CarGlyph() {
  return (
    <svg viewBox="0 0 24 24" className="h-[19px] w-[19px]" aria-hidden="true">
      {/* Espejos laterales */}
      <path d="M 5 8 C 4 8 4 11 5.5 11 C 6 11 6 8 5 8 Z" fill="currentColor" />
      <path d="M 19 8 C 20 8 20 11 18.5 11 C 18 11 18 8 19 8 Z" fill="currentColor" />
      {/* Carroceria curva */}
      <path d="M 6.5 4 C 6.5 2 8.5 1 12 1 C 15.5 1 17.5 2 17.5 4 L 18 20 C 18 22 15.5 23 12 23 C 8.5 23 6 22 6 20 Z" fill="currentColor" />
      {/* Parabrisas */}
      <path d="M 8 7 L 16 7 L 15 11 L 9 11 Z" className="fill-plum" opacity="0.85" />
      {/* Medallon (vidrio trasero) */}
      <path d="M 8.5 17.5 L 15.5 17.5 L 14.5 14.5 L 9.5 14.5 Z" className="fill-plum" opacity="0.85" />
      {/* Faros delanteros */}
      <rect x="7.5" y="2" width="2.5" height="1.5" rx="0.5" className="fill-plum" opacity="0.5" />
      <rect x="14" y="2" width="2.5" height="1.5" rx="0.5" className="fill-plum" opacity="0.5" />
      {/* Luces traseras */}
      <rect x="7.5" y="21.5" width="3" height="1" rx="0.5" className="fill-plum" opacity="0.6" />
      <rect x="13.5" y="21.5" width="3" height="1" rx="0.5" className="fill-plum" opacity="0.6" />
    </svg>
  );
}

/**
 * El vehiculo sobre el mapa.
 *
 * Animacion (criterio de la skill `animate` del proyecto, igual que
 * DeliveryMarker):
 *  - Purpose: feedback de estado y de rumbo — de un vistazo se sabe que va en
 *    movimiento y hacia donde.
 *  - Tool: CSS para lo continuo (pulso, flotado); el rumbo y la posicion los
 *    manda React porque dependen de datos, no de un ciclo fijo.
 *  - Properties: solo `transform` y `opacity`, nada que dispare layout.
 *  - Easing: `ease-out` de la tabla del proyecto para el giro (un vehiculo
 *    entra al giro rapido y lo acomoda al final), nunca `transition-all`.
 */
export function VehicleMarker({ lat, lng, bearing = 0, vehicle, variant = "live", label }: Props) {
  const isGhost = variant === "ghost";

  return (
    <Marker latitude={lat} longitude={lng}>
      <div className="relative flex h-12 w-12 items-center justify-center font-sans">
        {/* Halo: solo en vivo. En el fantasma competiria con el pulso de las
            paradas y el mapa se vuelve ruido. */}
        {!isGhost && (
          <span className="absolute h-10 w-10 animate-pulse-ring rounded-full bg-plum/35" aria-hidden="true" />
        )}

        {/* Doble bisel: una bandeja clara translucida sostiene el nucleo
            oscuro, para que el vehiculo se despegue del mapa sin recurrir a
            una sombra dura. */}
        <div
          className={`relative rounded-full p-[3px] shadow-[0_6px_18px_-4px_rgba(104,73,89,0.55)] backdrop-blur-sm transition duration-300 ease-out ${
            isGhost ? "bg-paper/70 ring-1 ring-plum/25" : "bg-paper/95 ring-1 ring-plum/15"
          }`}
        >
          <div
            className={`flex h-9 w-9 items-center justify-center rounded-full shadow-[inset_0_1px_1px_rgba(250,246,243,0.25)] ${
              isGhost ? "bg-plum/65 text-paper" : "bg-plum text-paper"
            }`}
          >
            <span
              className="block transition-transform duration-500 ease-out will-change-transform"
              style={{ transform: `rotate(${bearing}deg)` }}
            >
              {vehicle === "auto" ? <CarGlyph /> : <ScooterGlyph />}
            </span>
          </div>
        </div>

        {label && (
          <span className="animate-fade-in pointer-events-none absolute -bottom-5 whitespace-nowrap rounded-full bg-paper/95 px-2 py-[3px] text-[10px] font-medium uppercase tracking-[0.14em] text-plum shadow-sm ring-1 ring-plum/10">
            {label}
          </span>
        )}
      </div>
    </Marker>
  );
}
