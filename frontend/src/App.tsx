import { useState, type ReactNode } from "react";

import { useTranslation } from "./i18n/useTranslation";
import type { Language } from "./i18n/translations";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { ProfilePage } from "./pages/ProfilePage";
import { SimulationPage } from "./pages/SimulationPage";
import { useAppStore } from "./state/store";

type View = "simulation" | "profile" | "dashboard";

export default function App() {
  const { t, language } = useTranslation();
  const user = useAppStore((s) => s.user);
  const setUser = useAppStore((s) => s.setUser);
  const setLanguage = useAppStore((s) => s.setLanguage);
  const [view, setView] = useState<View>("simulation");

  if (!user) {
    return <LoginPage />;
  }

  // `100dvh` y no `h-screen`: con `vh`, en Safari de iOS la barra de
  // direcciones deja el mapa cortado y la app entera brinca al aparecer y
  // desaparecer. `min-h` y no `h` a secas: en paginas mas altas que un
  // viewport (Dashboard con su historial completo) el fondo con gradiente
  // tiene que crecer con el contenido, si no el degradado se corta justo en
  // el borde del viewport original y el resto de la pagina se ve con fondo
  // plano al hacer scroll.
  return (
    <div className="relative flex min-h-[100dvh] flex-col bg-paper bg-[radial-gradient(circle_at_top_right,rgba(229,202,217,0.35),transparent_45%),radial-gradient(circle_at_bottom_left,rgba(216,204,202,0.45),transparent_50%)]">
      <div className="paper-grain" />

      {/* Primer elemento tabulable de la pagina: deja saltarse la navegacion
          sin recorrerla tecla por tecla en cada cambio de vista. */}
      <a
        href="#main"
        className="skip-link rounded-full bg-plum px-4 py-2 text-[13px] font-medium text-paper shadow-[0_10px_24px_-10px_rgba(104,73,89,0.95)]"
      >
        {t("nav.skipToContent")}
      </a>

      {/* Header en flujo normal, no flotante: en la pagina de Simulacion,
          ControlPanel tambien es una barra de ancho completo — si el nav
          flotara encima con position:absolute, se encimarian. */}
      <header className="animate-fade-up relative z-header flex items-center justify-end gap-2 p-4">
        {/* Isla flotante con doble bisel: la bandeja translucida sostiene el
            riel opaco, mismo lenguaje que los paneles del mapa. */}
        <nav className="flex gap-1 rounded-full bg-paper/60 p-1 shadow-[0_10px_26px_-12px_rgba(104,73,89,0.5)] ring-1 ring-plum/10 backdrop-blur-xl">
          <NavButton active={view === "simulation"} onClick={() => setView("simulation")}>
            {t("nav.simulation")}
          </NavButton>
          <NavButton active={view === "dashboard"} onClick={() => setView("dashboard")}>
            {t("nav.dashboard")}
          </NavButton>
          <NavButton active={view === "profile"} onClick={() => setView("profile")}>
            {t("nav.profile")}
          </NavButton>
        </nav>

        <LanguageToggle language={language} onChange={setLanguage} />

        <button
          onClick={() => setUser(null)}
          title={t("nav.logout", { username: user.username })}
          className="flex h-9 w-9 items-center justify-center rounded-full bg-paper/70 text-charcoal/70 shadow-[0_10px_26px_-12px_rgba(104,73,89,0.5)] ring-1 ring-plum/10 backdrop-blur-xl transition duration-300 ease-out hover:bg-paper hover:text-plum hover:ring-plum/25 active:scale-95"
        >
          {/* Trazo fino: el grosor 2 de los sets por defecto se ve tosco al
              lado de los glifos del mapa, que van a 1.5. */}
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <path d="M16 17l5-5-5-5" />
            <path d="M21 12H9" />
          </svg>
        </button>
      </header>

      {/* `key={view}` reinicia la animacion de entrada en cada cambio de vista;
          `tabIndex={-1}` permite que el salto de arriba lleve el foco aqui
          (un <main> sin el no es enfocable y el salto no moveria nada). El
          anillo de foco global SI se deja: es la señal de que el salto ocurrio. */}
      <main id="main" tabIndex={-1} key={view} className="animate-fade-in flex min-h-0 flex-1 flex-col">
        {view === "simulation" && <SimulationPage />}
        {view === "dashboard" && <DashboardPage />}
        {view === "profile" && <ProfilePage />}
      </main>
    </div>
  );
}

function NavButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={`rounded-full px-4 py-1.5 text-[13px] font-medium transition duration-300 ease-out active:scale-[0.97] ${
        active
          ? "bg-plum text-paper shadow-[0_6px_16px_-8px_rgba(104,73,89,0.9)]"
          : "text-charcoal/75 hover:bg-blush/45 hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

/** Segmentado ES/EN, no una bandera: dos paises hablan español y "bandera de
 * Mexico = idioma español" es una asociacion que no siempre corresponde
 * (Argentina, España, etc.), ademas de que un icono de bandera pesa una
 * decision cultural que un rotulo de texto simple no carga. */
function LanguageToggle({ language, onChange }: { language: Language; onChange: (language: Language) => void }) {
  const { t } = useTranslation();

  return (
    <div
      role="group"
      aria-label={t("language.toggle")}
      className="flex gap-0.5 rounded-full bg-paper/60 p-1 shadow-[0_10px_26px_-12px_rgba(104,73,89,0.5)] ring-1 ring-plum/10 backdrop-blur-xl"
    >
      {(["es", "en"] as const).map((code) => (
        <button
          key={code}
          onClick={() => onChange(code)}
          aria-pressed={language === code}
          className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide transition duration-300 ease-out active:scale-[0.95] ${
            language === code ? "bg-plum text-paper" : "text-charcoal/60 hover:bg-blush/45 hover:text-ink"
          }`}
        >
          {code}
        </button>
      ))}
    </div>
  );
}
