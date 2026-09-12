/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Outfit",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "sans-serif",
        ],
      },
      colors: {
        paper: "#FAF6F3",
        ink: "#18151A",
        blush: "#E5CAD9",
        plum: "#684959",
        charcoal: "#3E3D41",
        dust: "#D8CCCA",
      },
      // Curvas tomadas de la tabla de la skill `animate` (no inventadas):
      // ease-out fuerte para entradas/salidas, ease-in-out fuerte para
      // elementos que se mueven en pantalla, y la curva "drawer" estilo iOS.
      transitionTimingFunction: {
        out: "cubic-bezier(0.23, 1, 0.32, 1)",
        inout: "cubic-bezier(0.77, 0, 0.175, 1)",
        drawer: "cubic-bezier(0.32, 0.72, 0, 1)",
        back: "cubic-bezier(0.34, 1.56, 0.64, 1)",
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(14px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        popIn: {
          "0%": { opacity: "0", transform: "scale(0.85)" },
          "60%": { opacity: "1", transform: "scale(1.06)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        pulseRing: {
          "0%": { transform: "scale(0.8)", opacity: "0.55" },
          "100%": { transform: "scale(2.4)", opacity: "0" },
        },
        bob: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-5px)" },
        },
      },
      animation: {
        "fade-up": "fadeUp 0.45s cubic-bezier(0.23,1,0.32,1) both",
        "fade-in": "fadeIn 0.35s cubic-bezier(0.23,1,0.32,1) both",
        "pop-in": "popIn 0.45s cubic-bezier(0.34,1.56,0.64,1) both",
        "pulse-ring": "pulseRing 2s cubic-bezier(0.23,1,0.32,1) infinite",
        bob: "bob 2.6s cubic-bezier(0.77,0,0.175,1) infinite",
      },
    },
  },
  plugins: [],
};
