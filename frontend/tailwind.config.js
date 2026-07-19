/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          900: '#0a0e1a',
          800: '#111827',
          700: '#1a2235',
          600: '#1e2d40',
          500: '#2d4a6b',
        },
        accent: '#3b82f6',
        profit: '#22c55e',
        loss: '#ef4444',
      },
    },
  },
  plugins: [],
}
