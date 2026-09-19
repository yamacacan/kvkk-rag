import forms from '@tailwindcss/forms';

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  darkMode: ['class', '[data-theme="dark"]'],
  // Seviye/renk rozetleri sabit sinif haritalariyla yazilir; yine de dinamik
  // kullanim kalirsa diye renk sinif ailesi guvenli listede.
  safelist: [
    { pattern: /^(bg|text|border)-(rose|amber|yellow|blue|indigo|emerald|violet|sky|fuchsia|cyan)-(300|400|500|600)(\/(5|10|15|20|25|30|40))?$/ },
  ],
  theme: {
    extend: {
      // Tasarim belirtecleri (mockup ile ayni): bg-bg-card, border-line, text-t-2, bg-acc-soft ...
      colors: {
        bg: { 0: 'rgb(var(--bg-0-rgb) / <alpha-value>)', 1: 'rgb(var(--bg-1-rgb) / <alpha-value>)', 2: 'rgb(var(--bg-2-rgb) / <alpha-value>)',
              3: 'rgb(var(--bg-3-rgb) / <alpha-value>)', card: 'rgb(var(--bg-card-rgb) / <alpha-value>)', hover: 'rgb(var(--bg-hover-rgb) / <alpha-value>)',
              inset: 'rgb(var(--bg-inset-rgb) / <alpha-value>)' },
        line: { subtle: 'var(--line-subtle)', DEFAULT: 'var(--line)', bright: 'var(--line-2)', 60: 'var(--line-60)' },
        t: { 1: 'rgb(var(--t0-rgb) / <alpha-value>)', 2: 'rgb(var(--t1-rgb) / <alpha-value>)', 3: 'rgb(var(--t2-rgb) / <alpha-value>)',
             muted: 'var(--t-muted)', soft: 'var(--t-soft)' },
        acc: { DEFAULT: '#6366F1', hover: '#4F46E5', soft: 'rgba(99,102,241,0.12)', glow: 'rgba(99,102,241,0.25)' },
        ok: { DEFAULT: '#10B981', soft: 'rgba(16,185,129,0.12)' },
        warn: { DEFAULT: '#F59E0B', soft: 'rgba(245,158,11,0.12)' },
        bad: { DEFAULT: '#EF4444', soft: 'rgba(239,68,68,0.12)' },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
    },
  },
  plugins: [forms],
};
