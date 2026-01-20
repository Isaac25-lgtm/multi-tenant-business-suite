/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          dark: '#0f172a',
          light: '#1e293b',
          DEFAULT: '#1e293b',
        },
        secondary: '#334155',
        accent: {
          DEFAULT: '#14b8a6',
          hover: '#0d9488',
          light: 'rgba(20, 184, 166, 0.1)',
        },
        text: {
          DEFAULT: '#f8fafc',
          muted: '#94a3b8',
        },
        border: '#475569',
        card: '#1e293b',
        danger: '#ef4444',
        warning: '#f59e0b',
        success: '#22c55e',
      },
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
