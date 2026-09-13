import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { useAppStore } from "../state/store";
import { useTranslation } from "./useTranslation";

beforeEach(() => {
  // El idioma vive en el store persistido junto a `user`; se resetea entre
  // tests para que uno no herede el idioma que dejo el anterior.
  useAppStore.setState({ language: "es" });
});

describe("useTranslation", () => {
  it("translates a known key in the current language", () => {
    const { result } = renderHook(() => useTranslation());
    expect(result.current.t("orders.title")).toBe("Ofertas");
  });

  it("re-renders with the new language after the store changes", () => {
    const { result } = renderHook(() => useTranslation());
    expect(result.current.t("orders.title")).toBe("Ofertas");

    act(() => {
      useAppStore.getState().setLanguage("en");
    });

    expect(result.current.language).toBe("en");
    expect(result.current.t("orders.title")).toBe("Offers");
  });

  it("interpolates {placeholder} variables", () => {
    const { result } = renderHook(() => useTranslation());
    expect(result.current.t("profile.greeting", { username: "Ana" })).toBe("Hola, Ana");
  });

  it("leaves an unmatched placeholder untouched instead of throwing", () => {
    const { result } = renderHook(() => useTranslation());
    // "profile.greeting" espera {username}; pasar una variable con otro
    // nombre no debe reventar, solo dejar el placeholder tal cual.
    expect(result.current.t("profile.greeting", { nombre: "Ana" })).toBe("Hola, {username}");
  });

  it("falls back to the key itself for a nonexistent translation key", () => {
    const { result } = renderHook(() => useTranslation());
    // @ts-expect-error -- llave inexistente a proposito, para probar el fallback
    expect(result.current.t("this.key.does.not.exist")).toBe("this.key.does.not.exist");
  });
});
