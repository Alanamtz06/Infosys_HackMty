import { ControlPanel } from "../components/dashboard/ControlPanel";
import { MapView } from "../components/map/MapView";

export function SimulationPage() {
  return (
    <div className="flex h-screen flex-col">
      <ControlPanel />
      <div className="flex-1">
        <MapView />
      </div>
    </div>
  );
}
