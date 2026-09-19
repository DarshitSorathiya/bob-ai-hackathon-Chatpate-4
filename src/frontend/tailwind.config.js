/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './app/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
    './pages/**/*.{js,ts,jsx,tsx}',
    './src/**/*.{js,ts,jsx,tsx}',
    './src/frontend/app/**/*.{js,ts,jsx,tsx}',
    './src/frontend/components/**/*.{js,ts,jsx,tsx}',
    './src/frontend/pages/**/*.{js,ts,jsx,tsx}',
    './*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f4f6ee',
          100: '#e1eadf',
          200: '#c3d6c1',
          500: '#4e9f76',
          600: '#2d6a4f',
          700: '#1e4d35',
          800: '#163a26',
          900: '#122018',
          950: '#0a140e',
        },
      },
    },
  },
  plugins: [],
};
