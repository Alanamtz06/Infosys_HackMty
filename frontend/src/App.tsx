import { useState, type ReactNode } from "react";

import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { ProfilePage } from "./pages/ProfilePage";
import { SimulationPage } from "./pages/SimulationPage";
import { useAppStore } from "./state/store";

type View = "simulation" | "profile" | "dashboard";

export default function App() {
  const user = useAppStore((s) => s.user);
  const setUser = useAppStore((s) => s.setUser);
  const [view, setView] = useState<View>("simulation");

  if (!user) {
    return <LoginPage />;
  }

  return (
    <div className="relative flex h-screen flex-col bg-paper bg-[radial-gradient(circle_at_top_right,rgba(229,202,217,0.35),transparent_45%),radial-gradient(circle_at_bottom_left,rgba(216,204,202,0.45),transparent_50%)]">
      <div className="paper-grain" />

      {/* Header en flujo normal, no flotante: en la pagina de Simulacion,
          ControlPanel tambien es una barra de ancho completo — si el nav
          flotara encima con position:absolute, se encimarian. */}
      <header className="animate-fade-up relative z-20 flex items-center justify-end gap-2 p-4">
        <nav className="flex gap-1 rounded-full border border-plum/15 bg-paper/90 p-1 shadow-[0_2px_10px_rgba(104,73,89,0.12)] backdrop-blur">
          <NavButton active={view === "simulation"} onClick={() => setView("simulation")}>
            Simulation
          </NavButton>
          <NavButton active={view === "dashboard"} onClick={() => setView("dashboard")}>
            Dashboard
          </NavButton>
          <NavButton active={view === "profile"} onClick={() => setView("profile")}>
            Profile
          </NavButton>
        </nav>

        <button
          onClick={() => setUser(null)}
          title={`Log out (${user.username})`}
          className="flex h-8 w-8 items-center justify-center rounded-full border border-dust bg-paper/90 text-charcoal shadow-[0_2px_8px_rgba(104,73,89,0.1)] backdrop-blur transition duration-150 ease-out hover:border-plum/30 hover:text-plum active:scale-95"
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <path d="M16 17l5-5-5-5" />
            <path d="M21 12H9" />
          </svg>
        </button>
      </header>

      <main key={view} className="animate-fade-in min-h-0 flex-1">
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
      className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition duration-150 ease-out active:scale-95 ${
        active
          ? "bg-plum text-paper shadow-[0_2px_8px_rgba(104,73,89,0.35)]"
          : "text-charcoal hover:bg-blush/50 hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}
