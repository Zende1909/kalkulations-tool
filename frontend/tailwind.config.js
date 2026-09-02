/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        app: {
          surface: "#f1f5f9",
          card: "#ffffff",
          border: "#e2e8f0",
          "border-strong": "#cbd5e1",
          muted: "#64748b",
          heading: "#0f172a",
          body: "#334155",
        },
        sidebar: {
          DEFAULT: "#0f172a",
          foreground: "#e2e8f0",
          muted: "#94a3b8",
          hover: "#1e293b",
          active: "#2563eb",
          "active-foreground": "#ffffff",
          border: "#334155",
        },
        brand: {
          DEFAULT: "#2563eb",
          hover: "#1d4ed8",
          light: "#dbeafe",
          foreground: "#ffffff",
        },
        success: {
          DEFAULT: "#16a34a",
          light: "#dcfce7",
          foreground: "#14532d",
        },
        warning: {
          DEFAULT: "#ea580c",
          light: "#ffedd5",
          foreground: "#9a3412",
        },
        danger: {
          DEFAULT: "#dc2626",
          light: "#fee2e2",
          foreground: "#991b1b",
        },
      },
      fontSize: {
        "page-title": ["1.625rem", { lineHeight: "2rem", fontWeight: "700" }],
        "section-title": ["1.0625rem", { lineHeight: "1.5rem", fontWeight: "600" }],
        "body-lg": ["0.9375rem", { lineHeight: "1.375rem" }],
      },
      boxShadow: {
        card: "0 1px 3px 0 rgb(15 23 42 / 0.08), 0 1px 2px -1px rgb(15 23 42 / 0.06)",
        modal: "0 20px 40px -12px rgb(15 23 42 / 0.25)",
      },
      borderRadius: {
        app: "0.5rem",
      },
    },
  },
  plugins: [],
};
