import { useState } from "react";

import { useTranslation } from "../../i18n/useTranslation";
import { authApi } from "../../services/api";
import { useAppStore } from "../../state/store";
import type { VehicleType } from "../../types";

function VehicleGlyph({ vehicle }: { vehicle: VehicleType }) {
  // Trazo 1.5 en todo el proyecto: el 2 de los sets por defecto se ve tosco
  // al lado de los glifos del mapa.
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-5 w-5"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {vehicle === "moto" ? (
        <>
          <circle cx="5.5" cy="17.5" r="3.5" />
          <circle cx="18.5" cy="17.5" r="3.5" />
          <path d="M15 6h4l-1 4.5M11 17.5h4l-3-8H8l-1.5 3M15 10.5H9" />
        </>
      ) : (
        <>
          <path d="M5 17h14M6 17V9.5L8 5h8l2 4.5V17" />
          <circle cx="8" cy="17" r="1.6" />
          <circle cx="16" cy="17" r="1.6" />
        </>
      )}
    </svg>
  );
}

function VehicleOption({
  vehicle,
  costPerKm,
  selected,
  onClick,
}: {
  vehicle: VehicleType;
  costPerKm: string;
  selected: boolean;
  onClick: () => void;
}) {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={`flex items-center gap-3 rounded-2xl px-4 py-3 text-left transition duration-300 ease-out active:scale-[0.98] ${
        selected
          ? "bg-blush/40 shadow-[inset_0_1px_1px_rgba(255,255,255,0.6)] ring-2 ring-plum/45"
          : "bg-paper/70 ring-1 ring-plum/10 hover:bg-paper hover:ring-plum/25"
      }`}
    >
      <span
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition duration-300 ease-out ${
          selected ? "bg-plum text-paper" : "bg-dust/50 text-charcoal/60"
        }`}
      >
        <VehicleGlyph vehicle={vehicle} />
      </span>
      <span>
        <span className={`block text-sm font-medium ${selected ? "text-plum" : "text-ink"}`}>
          {vehicle === "moto" ? t("login.vehicle.moto") : t("login.vehicle.auto")}
        </span>
        <span className="block text-[11px] tabular-nums text-charcoal/55">{costPerKm} / km</span>
      </span>
    </button>
  );
}

/**
 * Edicion de perfil: por ahora solo el vehiculo. Cambiarlo aqui es lo que
 * despues determina el costo de gasolina por km (calculate_score()) de
 * cualquier turno NUEVO que arranque esta cuenta — los turnos ya corridos no
 * se recalculan (TripRecord.vehicle queda congelado a como era, ver
 * comentario en backend/app/db/models.py).
 */
export function ProfileEdit() {
  const { t } = useTranslation();
  const user = useAppStore((s) => s.user);
  const setUser = useAppStore((s) => s.setUser);

  const [vehicleType, setVehicleType] = useState<VehicleType>(user?.vehicle_type ?? "moto");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!user) return null;

  const dirty = vehicleType !== user.vehicle_type;

  async function handleSave() {
    if (!user) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const { data } = await authApi.updateProfile({ user_id: user.id, vehicle_type: vehicleType });
      setUser(data);
      setSaved(true);
    } catch {
      setError(t("profile.edit.error"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-2xl px-5 py-8 text-ink lg:px-8 lg:py-10">
      <header className="animate-fade-up">
        <span className="text-[10px] font-medium uppercase tracking-[0.2em] text-plum/70">
          {t("profile.eyebrow")}
        </span>
        <h2 className="mt-1.5 text-2xl font-semibold tracking-[-0.02em] sm:text-3xl">
          {t("profile.greeting", { username: user.username })}
        </h2>
      </header>

      <section
        className="animate-fade-up mt-6 rounded-[1.75rem] bg-paper/60 p-1.5 ring-1 ring-plum/10"
        style={{ animationDelay: "80ms" }}
      >
        <div className="rounded-[calc(1.75rem-0.375rem)] bg-paper/95 p-5 shadow-[inset_0_1px_1px_rgba(255,255,255,0.6)]">
          <span className="text-[10px] font-medium uppercase tracking-[0.2em] text-plum/70">
            {t("profile.edit.title")}
          </span>

          <fieldset className="mt-3">
            <legend className="mb-2 block text-[11px] font-medium uppercase tracking-[0.14em] text-charcoal/55">
              {t("login.vehicle")}
            </legend>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <VehicleOption
                vehicle="moto"
                costPerKm="$0.80"
                selected={vehicleType === "moto"}
                onClick={() => {
                  setVehicleType("moto");
                  setSaved(false);
                }}
              />
              <VehicleOption
                vehicle="auto"
                costPerKm="$2.00"
                selected={vehicleType === "auto"}
                onClick={() => {
                  setVehicleType("auto");
                  setSaved(false);
                }}
              />
            </div>
          </fieldset>

          {error && (
            <p role="alert" className="animate-fade-up mt-3 text-[12px] leading-snug text-plum">
              {error}
            </p>
          )}

          <div className="mt-5 flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={!dirty || saving}
              className="group flex items-center gap-2 rounded-full bg-plum py-2 pl-5 pr-2 text-sm font-medium text-paper shadow-[0_10px_24px_-10px_rgba(104,73,89,0.95)] transition duration-300 ease-out hover:bg-ink active:scale-[0.98] disabled:opacity-40"
            >
              {saving ? t("profile.edit.saving") : t("profile.edit.save")}
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-paper/15 transition duration-300 ease-out group-hover:-translate-y-[1px] group-hover:translate-x-[2px] group-hover:scale-105">
                <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" aria-hidden="true">
                  <path
                    d="m5 12.5 4.5 4.5L19.5 7"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
            </button>

            {saved && !dirty && (
              <span className="animate-fade-in text-[12px] font-medium text-plum">{t("profile.edit.saved")}</span>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
