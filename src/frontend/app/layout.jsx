import './globals.css';
import { ThemeProvider } from '../components/ThemeProvider';

export const metadata = {
  title: 'MissionReady — Predictive Maintenance Copilot',
  description: 'Predict the failure. Protect the mission. Defense & Aerospace Telemetry Operations.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="bg-[#030712] dark:bg-[#030712] light:bg-[#f8fafc] text-slate-100 dark:text-slate-100 light:text-slate-900 antialiased font-sans min-h-screen transition-colors duration-200">
        <ThemeProvider>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
