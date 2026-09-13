import Link from 'next/link';

export default function HomePage() {
  return (
    <main className="min-h-screen flex flex-col justify-center items-center px-4 bg-[#070a12] text-slate-100 font-sans">
      <div className="max-w-xl text-center space-y-6">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-950/80 border border-blue-800/60 text-blue-400 text-xs font-mono font-semibold">
          🛡️ MISSIONREADY COPILOT PLATFORM
        </div>

        <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl">
          Predict the failure.<br />
          <span className="text-blue-400">Protect the mission.</span>
        </h1>

        <p className="text-slate-400 text-sm sm:text-base leading-relaxed">
          AI-powered decision-support copilot ingesting HUMS telemetry and historical service records to forecast asset failure risks and prioritize fleet maintenance.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center pt-4">
          <Link
            href="/login"
            className="px-6 py-3 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm transition-colors shadow-lg shadow-blue-600/20 font-mono"
          >
            Operator Sign In
          </Link>
          <Link
            href="/signup"
            className="px-6 py-3 rounded-lg bg-[#0b0f19] border border-slate-800 hover:bg-slate-800 text-slate-200 font-semibold text-sm transition-colors font-mono"
          >
            Request Access (Sign Up)
          </Link>
        </div>
      </div>
    </main>
  );
}
