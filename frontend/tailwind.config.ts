import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#13211F",
        deep: "#0B3B36",
        teal: { DEFAULT: "#0D7A6B", soft: "#DCEFEA", mint: "#5CC9B4" },
        tint: "#EAF3F1",
        line: "#D5DFDC",
        muted: "#5B6965",
        amber: { DEFAULT: "#B86A00", soft: "#FBECD3", bright: "#E39B2E" },
        danger: { DEFAULT: "#C0443A", soft: "#F7DEDB" },
        info: { DEFAULT: "#2C5D9E", soft: "#DDE7F5" },
      },
      fontFamily: {
        display: ["var(--font-display)", "Arial", "sans-serif"],
        sans: ["var(--font-body)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
