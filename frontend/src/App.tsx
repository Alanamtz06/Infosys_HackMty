import { useState } from "react";

import { ProfilePage } from "./pages/ProfilePage";
import { SimulationPage } from "./pages/SimulationPage";

type View = "simulation" | "profile";

export default function App() {
  const [view, setView] = useState<View>("simulation");

  return (
    <div className="relative">
      <nav className="absolute right-4 top-4 z-10 flex gap-2">
        <button
          onClick={() => setView("simulation")}
          className="rounded-md bg-neutral-800/80 px-3 py-1.5 text-sm text-neutral-100 backdrop-blur"
        >
          Simulación
        </button>
        <button
          onClick={() => setView("profile")}
          className="rounded-md bg-neutral-800/80 px-3 py-1.5 text-sm text-neutral-100 backdrop-blur"
        >
          Perfil
        </button>
      </nav>
      {view === "simulation" ? <SimulationPage /> : <ProfilePage />}
    </div>
  );
}
