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
      {/* rueda delantera y trasera: circulos solidos, no rectangulos finos */}
      <circle cx="12" cy="5" r="2.6" fill="currentColor" />
      <circle cx="12" cy="19" r="2.6" fill="currentColor" />
      {/* chasis grueso conectando las dos ruedas */}
      <rect x="9.7" y="4.5" width="4.6" height="15" rx="2.3" fill="currentColor" />
      {/* caja de reparto: el unico detalle que distingue moto-de-reparto de moto a secas */}
      <rect x="7.6" y="10.4" width="8.8" height="6" rx="1.8" className="fill-plum" opacity="0.9" />
    </svg>
  );
}

function CarGlyph() {
  return (
    <svg viewBox="0 0 24 24" className="h-[19px] w-[19px]" aria-hidden="true">
      {/* carroceria: una sola forma solida, ancha, sin detalle fino que se pierda */}
      <rect x="6" y="2.5" width="12" height="19" rx="5" fill="currentColor" />
      {/* parabrisas + medallon: dos cortes anchos, no lineas delgadas */}
      <rect x="8.3" y="6.2" width="7.4" height="4" rx="1.8" className="fill-plum" />
      <rect x="8.3" y="14" width="7.4" height="3.6" rx="1.6" className="fill-plum" opacity="0.85" />
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
      <div className="relative flex h-12 w-12 items-center justify-center">
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
