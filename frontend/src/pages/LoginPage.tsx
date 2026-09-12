import { useState, type FormEvent } from "react";

import { authApi } from "../services/api";
import { useAppStore } from "../state/store";
import type { VehicleType } from "../types";

type Mode = "login" | "register";

// FastAPI manda `detail` como string para HTTPException (usuario duplicado,
// credenciales invalidas) pero como arreglo de objetos para errores 422 de
// validacion de Pydantic (username/password demasiado cortos) — sin esto,
// intentar renderizar el arreglo directo en el JSX tira el formulario.
function extractErrorMessage(err: unknown): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item === "object" && item && "msg" in item ? String(item.msg) : String(item)))
      .join(" · ");
  }
  return "Could not connect to the server.";
}

export function LoginPage() {
  const setUser = useAppStore((s) => s.setUser);
  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [vehicleType, setVehicleType] = useState<VehicleType>("moto");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { data } =
        mode === "login"
          ? await authApi.login({ username, password })
          : await authApi.register({ username, password, vehicle_type: vehicleType });
      setUser(data);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-paper bg-[radial-gradient(circle_at_top_right,rgba(229,202,217,0.35),transparent_45%),radial-gradient(circle_at_bottom_left,rgba(216,204,202,0.45),transparent_50%)] px-4">
      <div className="paper-grain" />

      <form
        onSubmit={handleSubmit}
        className="animate-fade-up relative w-full max-w-sm rounded-2xl border border-dust bg-paper/95 p-6 shadow-[0_8px_30px_rgba(104,73,89,0.15)] backdrop-blur"
      >
        <span className="absolute inset-x-0 top-0 h-1.5 rounded-t-2xl bg-gradient-to-r from-plum via-blush to-dust" />

        <div className="mb-6 flex items-center gap-3">
          <img src="/logo-mark.png" alt="Lynx" className="animate-pop-in h-11 w-11" />
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-ink">Lynx</h1>
            <p className="text-xs text-charcoal/70">
              {mode === "login" ? "Sign in to start delivering" : "Create your courier account"}
            </p>
          </div>
        </div>

        <label className="mb-3 block">
          <span className="mb-1 block text-xs font-medium uppercase tracking-[0.1em] text-charcoal/70">
            Username
          </span>
          <input
            required
            minLength={3}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            className="w-full rounded-md border border-dust bg-white px-3 py-2 text-sm text-ink transition duration-150 ease-out focus:border-plum focus:outline-none focus-visible:ring-2 focus-visible:ring-plum/20"
            placeholder="your_username"
          />
        </label>

        <label className="mb-4 block">
          <span className="mb-1 block text-xs font-medium uppercase tracking-[0.1em] text-charcoal/70">
            Password
          </span>
          <input
            required
            type="password"
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            className="w-full rounded-md border border-dust bg-white px-3 py-2 text-sm text-ink transition duration-150 ease-out focus:border-plum focus:outline-none focus-visible:ring-2 focus-visible:ring-plum/20"
            placeholder="••••••••"
          />
        </label>

        {mode === "register" && (
          <div className="animate-fade-up mb-4">
            <span className="mb-1.5 block text-xs font-medium uppercase tracking-[0.1em] text-charcoal/70">
              Vehicle
            </span>
            <div className="grid grid-cols-2 gap-2">
              <VehicleOption
                label="Moto"
                sublabel="$0.80 MXN/km"
                selected={vehicleType === "moto"}
                onClick={() => setVehicleType("moto")}
              />
              <VehicleOption
                label="Auto"
                sublabel="$2.00 MXN/km"
                selected={vehicleType === "auto"}
                onClick={() => setVehicleType("auto")}
              />
            </div>
          </div>
        )}

        {error && (
          <div className="animate-fade-up mb-4 rounded-md border border-plum/25 bg-blush/25 px-3 py-2 text-sm text-plum">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-full bg-plum py-2.5 text-sm font-medium text-paper shadow-[0_2px_10px_rgba(104,73,89,0.35)] transition duration-150 ease-out hover:bg-charcoal active:scale-95 disabled:opacity-50"
        >
          {loading ? "Connecting..." : mode === "login" ? "Sign in" : "Create account"}
        </button>

        <button
          type="button"
          onClick={() => {
            setError(null);
            setMode(mode === "login" ? "register" : "login");
          }}
          className="mt-3 w-full rounded-full py-2 text-sm text-charcoal transition duration-150 ease-out hover:bg-blush/30 hover:text-ink active:scale-95"
        >
          {mode === "login" ? "Don't have an account? Sign up" : "Already have an account? Sign in"}
        </button>
      </form>
    </div>
  );
}

function VehicleOption({
  label,
  sublabel,
  selected,
  onClick,
}: {
  label: string;
  sublabel: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg border px-3 py-2.5 text-left transition duration-150 ease-out active:scale-95 ${
        selected
          ? "border-plum bg-blush/30 shadow-[0_2px_8px_rgba(104,73,89,0.15)]"
          : "border-dust bg-white hover:border-plum/30 hover:bg-dust/20"
      }`}
    >
      <div className={`text-sm font-medium ${selected ? "text-plum" : "text-ink"}`}>{label}</div>
      <div className="text-xs text-charcoal/60">{sublabel}</div>
    </button>
  );
}
