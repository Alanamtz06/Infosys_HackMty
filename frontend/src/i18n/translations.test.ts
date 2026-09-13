import { describe, expect, it } from "vitest";

import { en, es } from "./translations";

describe("es/en dictionary parity", () => {
  it("has exactly the same keys in both languages", () => {
    // Comparado como conjuntos: si difieren, el mensaje de assert lista
    // ambos objetos completos y es dificil ver cual llave sobra/falta. Esta
    // forma senala el diff real.
    const esKeys = new Set(Object.keys(es));
    const enKeys = new Set(Object.keys(en));

    const missingInEn = [...esKeys].filter((key) => !enKeys.has(key));
    const extraInEn = [...enKeys].filter((key) => !esKeys.has(key));

    expect(missingInEn).toEqual([]);
    expect(extraInEn).toEqual([]);
  });

  it("has no empty translation strings in either language", () => {
    for (const [key, value] of Object.entries(es)) {
      expect(value, `es["${key}"] esta vacia`).not.toBe("");
    }
    for (const [key, value] of Object.entries(en)) {
      expect(value, `en["${key}"] esta vacia`).not.toBe("");
    }
  });

  it("uses the same {placeholder} names on both sides of every interpolated string", () => {
    // Si "es" pide {username} pero "en" pide {user} para la MISMA llave,
    // `interpolate()` deja el placeholder sin rellenar en uno de los dos
    // idiomas — un bug silencioso que solo se nota leyendo en ese idioma.
    const placeholderNames = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

    for (const key of Object.keys(es) as (keyof typeof es)[]) {
      expect(placeholderNames(en[key]), `placeholders de "${key}" no coinciden entre es/en`).toEqual(
        placeholderNames(es[key]),
      );
    }
  });
});
