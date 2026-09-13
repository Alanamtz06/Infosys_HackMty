import { useCallback } from "react";

import { useAppStore } from "../state/store";
import { es, en, translations, type TranslationKey } from "./translations";

/** Sustituye `{{var}}`... en realidad usa `{var}` simple (un solo par de
 * llaves) porque ninguna copia del proyecto necesita literales con llaves —
 * mas corto de escribir en los diccionarios de arriba. */
function interpolate(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, name) => {
    const value = vars[name];
    return value === undefined ? match : String(value);
  });
}

// Chequeo de paridad en dev: `en` esta tipado contra `keyof typeof es`, asi
// que a una llave FALTANTE ya la detiene `tsc` — pero eso no cubre una llave
// de mas en `en` que ya no existe en `es` (borrada de un lado y no del
// otro), que compila sin error y se queda como texto muerto silenciosamente.
// Corre una sola vez al cargar el modulo, nunca en produccion.
if (import.meta.env.DEV) {
  const missingInEn = Object.keys(es).filter((key) => !(key in en));
  const extraInEn = Object.keys(en).filter((key) => !(key in es));
  if (missingInEn.length > 0) {
    console.warn("[i18n] Llaves en 'es' que faltan en 'en':", missingInEn);
  }
  if (extraInEn.length > 0) {
    console.warn("[i18n] Llaves en 'en' que ya no existen en 'es' (texto muerto):", extraInEn);
  }
}

/** Lee el idioma actual del store (persistido junto a `user`) y devuelve un
 * `t()` atado a el. Un componente que llama `useTranslation()` se
 * re-renderiza solo cuando cambia el idioma — es un selector de zustand
 * normal, no un Context aparte. */
export function useTranslation() {
  const language = useAppStore((s) => s.language);

  const t = useCallback(
    (key: TranslationKey, vars?: Record<string, string | number>): string => {
      const dict = translations[language];
      const raw = dict[key] ?? translations.es[key] ?? key;
      return vars ? interpolate(raw, vars) : raw;
    },
    [language],
  );

  return { t, language };
}
