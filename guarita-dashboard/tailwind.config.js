/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'brand-green': '#3FB897',
        'brand-yellow': '#F4A261',
        'status-red': '#EF4444',
        'status-green': '#22C55E',
      }
    },
  },
  plugins: [],
}