import type { Config } from "tailwindcss";
import typography from "@tailwindcss/typography";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#f8f9ff",
        "surface-bright": "#ffffff",
        "surface-container": "#eef4ff",
        "surface-container-low": "#f3f6fb",
        "on-surface": "#0d1c2d",
        "on-surface-variant": "#45464d",
        outline: "#76777d",
        "outline-variant": "#d8dce6",
        primary: "#0d1c2d",
        "on-primary": "#ffffff",
        secondary: "#505f76",
        "secondary-container": "#d0e1fb",
        "on-secondary-container": "#1c3357",
        error: "#ba1a1a",
        "error-container": "#ffedec",
      },
      borderRadius: {
        DEFAULT: "0.25rem",
        lg: "0.375rem",
      },
      fontFamily: {
        mono: ["var(--font-jetbrains-mono)", "monospace"],
      },
    },
  },
  plugins: [typography],
};

export default config;
