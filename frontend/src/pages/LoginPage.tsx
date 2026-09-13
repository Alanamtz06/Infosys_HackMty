import { useState, type FormEvent } from "react";

import { useTranslation } from "../i18n/useTranslation";
import { authApi } from "../services/api";
import { useAppStore } from "../state/store";
import type { VehicleType } from "../types";

type Mode = "login" | "register";

// FastAPI manda `detail` como string para HTTPException (usuario duplicado,
// credenciales invalidas) pero como arreglo de objetos para errores 422 de
// validacion de Pydantic (username/password demasiado cortos) — sin esto,
// intentar renderizar el arreglo directo en el JSX tira el formulario. Los
// mensajes de FastAPI/Pydantic mismos NO se traducen (vienen en ingles del
// backend); solo el fallback generico usa i18n.
function extractErrorMessage(err: unknown, fallback: string): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item === "object" && item && "msg" in item ? String(item.msg) : String(item)))
      .join(" · ");
  }
  return fallback;
}

export function LoginPage() {
  const { t } = useTranslation();
  const setUser = useAppStore((s) => s.setUser);

  // Las constantes reales del modelo de costos (backend/app/config.py). Van
  // aqui porque son el argumento del producto: son los numeros con los que
  // se decide cada pedido, no adornos de landing.
  const costModel = [
    { value: "$0.80", unit: t("login.cost.perKm"), note: t("login.cost.moto") },
    { value: "$2.00", unit: t("login.cost.perKm"), note: t("login.cost.auto") },
    { value: "$1.50", unit: t("login.cost.perMin"), note: t("login.cost.time") },
  ];
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
      setError(extractErrorMessage(err, t("login.errorGeneric")));
    } finally {
      setLoading(false);
    }
  }

  return (
    // `100dvh` y no `100vh`: en Safari de iOS la barra de direcciones entra y
    // sale del viewport y con `vh` la pantalla brinca al enfocar un input.
    <div className="relative min-h-[100dvh] bg-paper bg-[radial-gradient(circle_at_top_right,rgba(229,202,217,0.38),transparent_48%),radial-gradient(circle_at_bottom_left,rgba(216,204,202,0.45),transparent_52%)]">
      <div className="paper-grain" />

      <div className="mx-auto grid min-h-[100dvh] w-full max-w-6xl grid-cols-1 items-center gap-10 px-4 py-12 lg:grid-cols-[1.1fr_auto] lg:gap-20 lg:px-8 lg:py-24">
        {/* --- Lado editorial ------------------------------------------- */}
        <section className="max-w-xl">
          <div className="animate-fade-up flex items-center gap-3">
            <img src="/nova-logo.svg" alt="" className="h-9 w-9" />
            <span className="text-[15px] font-semibold tracking-tight text-ink">Nova</span>
            <span className="ml-1 rounded-full bg-paper/80 px-3 py-1 text-[10px] font-medium uppercase tracking-[0.2em] text-plum ring-1 ring-plum/15">
              {t("login.eyebrow")}
            </span>
          </div>

          <h1
            className="animate-fade-up mt-7 text-[2.6rem] font-semibold leading-[0.98] tracking-[-0.03em] text-ink [text-wrap:balance] sm:text-6xl"
            style={{ animationDelay: "80ms" }}
          >
            {t("login.headline1")}
            <span className="block text-plum">{t("login.headline2")}</span>
          </h1>

          <p
            className="animate-fade-up mt-6 max-w-[46ch] text-[15px] leading-relaxed text-charcoal/75"
            style={{ animationDelay: "160ms" }}
          >
            {t("login.body")}
          </p>

          {/* Los costos del modelo, no metricas inventadas. */}
          <dl
            className="animate-fade-up mt-9 flex flex-wrap gap-2.5"
            style={{ animationDelay: "240ms" }}
          >
            {costModel.map(({ value, unit, note }) => (
              <div
                key={note}
                className="rounded-2xl bg-paper/70 p-1 ring-1 ring-plum/10 backdrop-blur-sm"
              >
                <div className="rounded-[calc(1rem-0.25rem)] bg-paper/90 px-3.5 py-2 shadow-[inset_0_1px_1px_rgba(255,255,255,0.6)]">
                  <dt className="text-[10px] uppercase tracking-[0.16em] text-charcoal/50">{note}</dt>
                  <dd className="mt-0.5 text-sm font-semibold tabular-nums tracking-tight text-ink">
                    {value}
                    <span className="ml-1 text-[11px] font-normal text-charcoal/55">{unit}</span>
                  </dd>
                </div>
              </div>
            ))}
          </dl>
        </section>

        {/* --- Formulario ------------------------------------------------ */}
        <form
          onSubmit={handleSubmit}
          className="animate-fade-up w-full rounded-[2rem] bg-paper/60 p-1.5 shadow-[0_28px_60px_-24px_rgba(104,73,89,0.5)] ring-1 ring-plum/10 backdrop-blur-xl lg:w-[24rem]"
          style={{ animationDelay: "140ms" }}
        >
          {/* Nucleo interior con radio concentrico (2rem menos el padding). */}
          <div className="rounded-[calc(2rem-0.375rem)] bg-paper/95 p-6 shadow-[inset_0_1px_1px_rgba(255,255,255,0.7)]">
            <span className="text-[10px] font-medium uppercase tracking-[0.2em] text-plum/70">
              {mode === "login" ? t("login.welcomeBack") : t("login.newCourier")}
            </span>
            <h2 className="mt-1.5 text-xl font-semibold tracking-tight text-ink">
              {mode === "login" ? t("login.signInTitle") : t("login.registerTitle")}
            </h2>

            <label className="mt-6 block">
              <span className="mb-1.5 block text-[10px] font-medium uppercase tracking-[0.16em] text-charcoal/60">
                {t("login.username")}
              </span>
              <input
                required
                minLength={3}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                placeholder={t("login.usernamePlaceholder")}
                className="w-full rounded-xl bg-white/80 px-3.5 py-2.5 text-sm text-ink shadow-[inset_0_1px_2px_rgba(104,73,89,0.07)] ring-1 ring-plum/10 transition duration-300 ease-out placeholder:text-charcoal/35 hover:ring-plum/20 focus:outline-none focus:ring-2 focus:ring-plum/45"
              />
            </label>

            <label className="mt-3.5 block">
              <span className="mb-1.5 block text-[10px] font-medium uppercase tracking-[0.16em] text-charcoal/60">
                {t("login.password")}
              </span>
              <input
                required
                type="password"
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                placeholder="••••••••"
                className="w-full rounded-xl bg-white/80 px-3.5 py-2.5 text-sm text-ink shadow-[inset_0_1px_2px_rgba(104,73,89,0.07)] ring-1 ring-plum/10 transition duration-300 ease-out placeholder:text-charcoal/35 hover:ring-plum/20 focus:outline-none focus:ring-2 focus:ring-plum/45"
              />
            </label>

            {mode === "register" && (
              <fieldset className="animate-fade-up mt-4">
                <legend className="mb-1.5 block text-[10px] font-medium uppercase tracking-[0.16em] text-charcoal/60">
                  {t("login.vehicle")}
                </legend>
                {/* El vehiculo fija el costo por km del turno entero y se
                    congela al arrancar: por eso se elige aqui y no despues. */}
                <div className="grid grid-cols-2 gap-2">
                  <VehicleOption
                    label={t("login.vehicle.moto")}
                    sublabel="$0.80 / km"
                    selected={vehicleType === "moto"}
                    onClick={() => setVehicleType("moto")}
                  />
                  <VehicleOption
                    label={t("login.vehicle.auto")}
                    sublabel="$2.00 / km"
                    selected={vehicleType === "auto"}
                    onClick={() => setVehicleType("auto")}
                  />
                </div>
              </fieldset>
            )}

            {error && (
              <p
                role="alert"
                className="animate-fade-up mt-4 rounded-xl bg-blush/30 px-3 py-2 text-[13px] leading-snug text-plum ring-1 ring-plum/20"
              >
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="group mt-5 flex w-full items-center justify-between gap-2 rounded-full bg-plum py-2 pl-5 pr-2 text-sm font-medium text-paper shadow-[0_10px_24px_-10px_rgba(104,73,89,0.95)] transition duration-300 ease-out hover:bg-ink active:scale-[0.98] disabled:opacity-50"
            >
              {loading ? t("login.connecting") : mode === "login" ? t("login.signIn") : t("login.createAccount")}
              {/* Icono anidado en su propio circulo, a ras del borde interno. */}
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-paper/15 transition duration-300 ease-out group-hover:-translate-y-[1px] group-hover:translate-x-[2px] group-hover:scale-105">
                <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" aria-hidden="true">
                  <path
                    d="M5 12h13M13 6.5 18.5 12 13 17.5"
                    stroke="currentColor"
                    strokeWidth="1.7"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
            </button>

            <button
              type="button"
              onClick={() => {
                setError(null);
                setMode(mode === "login" ? "register" : "login");
              }}
              className="mt-2.5 w-full rounded-full py-2 text-[13px] text-charcoal/70 transition duration-300 ease-out hover:bg-dust/35 hover:text-ink active:scale-[0.98]"
            >
              {mode === "login" ? t("login.switchToRegister") : t("login.switchToLogin")}
            </button>
          </div>
        </form>
      </div>
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
      aria-pressed={selected}
      className={`rounded-xl px-3 py-2.5 text-left transition duration-300 ease-out active:scale-[0.98] ${
        selected
          ? "bg-blush/40 shadow-[inset_0_1px_1px_rgba(255,255,255,0.6)] ring-2 ring-plum/45"
          : "bg-white/70 ring-1 ring-plum/10 hover:bg-white hover:ring-plum/25"
      }`}
    >
      <div className={`text-sm font-medium ${selected ? "text-plum" : "text-ink"}`}>{label}</div>
      <div className="text-[11px] tabular-nums text-charcoal/60">{sublabel}</div>
    </button>
  );
}
