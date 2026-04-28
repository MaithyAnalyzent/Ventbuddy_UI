/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: ["./src/**/*.{js,jsx,ts,tsx}", "./public/index.html"],
  theme: {
    extend: {
      fontFamily: {
        heading: ['Outfit', 'sans-serif'],
        body: ['"DM Sans"', 'sans-serif'],
        sans: ['"DM Sans"', 'sans-serif'],
      },
      colors: {
        sand: {
          50: '#FDFBF7',
          100: '#F9F6F0',
          200: '#F0EBE0',
          300: '#E8A87C',
        },
        sage: {
          50: '#EEF2EC',
          100: '#D8E2D5',
          400: '#8A9A86',
          500: '#748370',
          700: '#586556',
        },
        terracotta: {
          400: '#E27D60',
          500: '#CB674B',
        },
        ink: {
          900: '#2D3A3A',
          600: '#6B7B7B',
        },
        border: '#E5E0D8',
        crisis: '#D9534F',
        sleep: {
          bg: '#0B131E',
          card: '#141F2E',
          text: '#E1E7EE',
        },
        background: '#F9F6F0',
        foreground: '#2D3A3A',
        card: {
          DEFAULT: '#FDFBF7',
          foreground: '#2D3A3A',
        },
        popover: {
          DEFAULT: '#FDFBF7',
          foreground: '#2D3A3A',
        },
        primary: {
          DEFAULT: '#8A9A86',
          foreground: '#FDFBF7',
        },
        secondary: {
          DEFAULT: '#D8E2D5',
          foreground: '#2D3A3A',
        },
        muted: {
          DEFAULT: '#F0EBE0',
          foreground: '#6B7B7B',
        },
        accent: {
          DEFAULT: '#E8A87C',
          foreground: '#2D3A3A',
        },
        destructive: {
          DEFAULT: '#D9534F',
          foreground: '#FDFBF7',
        },
        input: '#E5E0D8',
        ring: '#8A9A86',
      },
      borderRadius: {
        lg: '1rem',
        md: '0.75rem',
        sm: '0.5rem',
        '2xl': '1.5rem',
        '3xl': '2rem',
      },
      keyframes: {
        'accordion-down': { from: { height: '0' }, to: { height: 'var(--radix-accordion-content-height)' } },
        'accordion-up': { from: { height: 'var(--radix-accordion-content-height)' }, to: { height: '0' } },
        'breath': {
          '0%, 100%': { transform: 'scale(1)', opacity: '0.85' },
          '50%': { transform: 'scale(1.18)', opacity: '1' },
        },
        'pulse-ring': {
          '0%': { transform: 'scale(1)', opacity: '0.8' },
          '100%': { transform: 'scale(1.6)', opacity: '0' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
        'breath': 'breath 8s ease-in-out infinite',
        'pulse-ring': 'pulse-ring 1.6s ease-out infinite',
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
