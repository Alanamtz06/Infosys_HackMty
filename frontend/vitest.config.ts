/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Config separada de vite.config.ts a proposito: `vitest` no necesita el
// `server.port` fijo que usa el dev server (y fijarlo aqui solo generaria un
// warning inofensivo cada corrida). Comparten el plugin de React porque los
// tests de hooks/componentes si necesitan JSX transformado igual que en dev.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
