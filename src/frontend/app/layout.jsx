import './globals.css';
import { ThemeProvider } from '../components/ThemeProvider';

export const metadata = {
  title: 'MissionReady — Predictive Maintenance Copilot',
  description: 'Predict the failure. Protect the mission. Defense & Aerospace Telemetry Operations.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="bg-[#f4f6ee] dark:bg-[#0d1b13] text-[#122018] dark:text-slate-100 antialiased font-sans min-h-screen transition-colors duration-200 relative">
        {/* Global Atmospheric Background Image with Very Low White Transparency */}
        <div className="fixed inset-0 bg-[url('/images/landing-pg.png')] bg-cover bg-center opacity-15 dark:opacity-20 pointer-events-none z-0" />
        <div className="fixed inset-0 bg-gradient-to-b from-[#f4f6ee]/85 via-[#f4f6ee]/75 to-[#f4f6ee]/90 dark:from-[#0d1b13]/85 dark:via-[#0d1b13]/75 dark:to-[#0d1b13]/90 pointer-events-none z-0" />
        <ThemeProvider>
          <div className="relative z-10 min-h-screen flex flex-col">
            {children}
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}
