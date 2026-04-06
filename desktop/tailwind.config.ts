import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        surface: "#181818",
        "surface-under": "#000000",
        elevated: "#282828",
        "elevated-secondary": "rgba(255,255,255,0.03)",
        editor: "#212121",
        accent: "#339cff",
        "accent-bright": "#0285ff",
        "accent-bg": "#00284d",
        "button-primary": "#0d0d0d",
        "text-primary": "#ffffff",
        "text-secondary": "#afafaf",
        "text-tertiary": "#5d5d5d",
        "text-muted": "#414141",
        "border-default": "rgba(255,255,255,0.08)",
        "border-strong": "rgba(255,255,255,0.16)",
        success: "#40c977",
        error: "#ff6764",
        warning: "#ff8549",
      },
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", '"Segoe UI"', "sans-serif"],
        mono: ["ui-monospace", '"SFMono-Regular"', '"SF Mono"', "Menlo", "Consolas", "monospace"],
      },
      fontSize: {
        body: ["13px", "18px"],
        small: ["12px", "16px"],
        code: ["12px", "16px"],
        diff: ["11px", "14px"],
      },
      borderRadius: {
        DEFAULT: "8px",
        lg: "12px",
        xl: "16px",
        "2xl": "20px",
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(255,255,255,0.04), 0 20px 40px rgba(0,0,0,0.35)",
      },
    },
  },
};

export default config;
