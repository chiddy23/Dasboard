/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // JustInsurance brand colors
        'ji-navy': {
          DEFAULT: '#192f4d',
          dark: '#0f2b47',
          light: '#15355f'
        },
        'ji-blue': {
          DEFAULT: '#1a3a52',
          medium: '#2c5282',
          bright: '#3182ce',
          accent: '#5b9bd5',
          light: '#63b3ed'
        }
      },
      fontFamily: {
        sans: ['Segoe UI', 'Tahoma', 'Geneva', 'Verdana', 'sans-serif']
      },
      backgroundImage: {
        'ji-gradient': 'linear-gradient(145deg, #0f2b47 0%, #1a3a52 50%, #2a5575 100%)'
      }
    },
  },
  plugins: [],
}
