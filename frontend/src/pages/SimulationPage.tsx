import { ControlPanel } from "../components/dashboard/ControlPanel";
import { MapView } from "../components/map/MapView";

export function SimulationPage() {
  return (
    <div className="flex h-screen flex-col bg-paper">
      <ControlPanel />
      <div className="flex-1 animate-fade-in" style={{ animationDelay: "150ms" }}>
        <MapView />
      </div>
    </div>
  );
}
