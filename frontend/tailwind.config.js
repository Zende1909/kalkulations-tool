/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        sidebar: {
          DEFAULT: "#1e293b",
          hover: "#334155",
          active: "#0f172a",
        },
      },
    },
  },
  plugins: [],
};
