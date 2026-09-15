import './globals.css';
import '../public/styles.css';

export const metadata = {
  title: 'MissionReady — Predictive Maintenance Copilot',
  description: 'Predict the failure. Protect the mission. Defense & Aerospace Telemetry Operations.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#070a12] text-slate-100 antialiased font-sans min-h-screen">
        {children}
      </body>
    </html>
  );
}
