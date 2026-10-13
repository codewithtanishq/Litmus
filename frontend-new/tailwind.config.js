/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        theme: {
          page: '#F6F5FF',
          card: '#FFFFFF',
          panel: '#EEEBFF',
          border: '#E1DDFA',
          muted: '#6B6894',
          heading: '#1E1856',
          primary: '#5F4DCB',
          'primary-hover': '#4A39B3',
          'glow-lavender': '#C5C4F2',
          gradient: {
            start: '#221B6D',
            mid: '#3B2A9D',
            end: '#5F4DCB',
          },
          success: {
            DEFAULT: '#2E7D5B',
            bg: '#EDF7F2',
            border: '#BFE7D3',
          },
          error: {
            DEFAULT: '#D13438',
            bg: '#FDF2F2',
            border: '#F9C6C7',
          },
        },
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
      borderRadius: {
        'card': '16px',
        'card-sm': '12px',
      },
      boxShadow: {
        'violet-soft': '0 4px 24px -2px rgba(95, 77, 203, 0.07), 0 2px 6px -1px rgba(95, 77, 203, 0.04)',
        'violet-hover': '0 8px 30px -4px rgba(95, 77, 203, 0.12), 0 4px 10px -2px rgba(95, 77, 203, 0.06)',
        'hero-glow': '0 0 80px 10px rgba(197, 196, 242, 0.25)',
      },
    },
  },
  plugins: [],
};
