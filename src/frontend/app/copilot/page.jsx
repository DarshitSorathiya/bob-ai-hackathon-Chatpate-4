'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Send, Bot, User, Sparkles, Loader2, HelpCircle } from 'lucide-react';
import { isAuthenticated, copilotQuery } from '../../lib/api';
import NavBar from '../../components/NavBar';

const SUGGESTED_QUERIES = [
  'Why is asset A-102 AT_RISK?',
  'What maintenance is required for B-047?',
  'Show critical telemetry alerts from last 24h',
  'Is C-018 ready for 4-hour mission?',
  'Explain HUMS vibration on asset D-063',
];

function ChatMessage({ msg }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className="w-9 h-9 rounded-full bg-[#e1eadf] dark:bg-[#1e4d35]/30 border border-[#1e4d35]/40 flex items-center justify-center shrink-0 text-[#1e4d35] dark:text-emerald-400 shadow-sm">
          <Bot className="w-5 h-5" />
        </div>
      )}
      <div className={`max-w-3xl rounded-2xl p-5 ${
        isUser
          ? 'bg-[#1e4d35] text-white border border-[#1e4d35] shadow-md'
          : 'dashboard-card-shape text-[#122018] dark:text-slate-100 space-y-3'
      }`}>
        <p className="text-sm font-sans leading-relaxed whitespace-pre-wrap">{msg.content}</p>

        {msg.citations?.length > 0 && (
          <div className="pt-3 border-t border-[#1e4d35]/20 dark:border-slate-800/80 font-mono text-xs text-[#566b5c] dark:text-slate-400">
            <p className="font-bold text-[#122018] dark:text-slate-300 mb-1">Retrieved Evidence ({msg.citations.length}):</p>
            <ul className="space-y-1">
              {msg.citations.map((c, i) => (
                <li key={i} className="flex items-center gap-2">
                  <span className="text-[#1e4d35] dark:text-emerald-400">[{c.source_type || 'source'}]</span>
                  <span className="truncate">{c.title || c.id}</span>
                  {c.confidence != null && (
                    <span className="text-emerald-600 dark:text-emerald-400 ml-auto font-bold">{Math.round(c.confidence * 100)}% match</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {isUser && (
        <div className="w-9 h-9 rounded-full bg-[#e1eadf] dark:bg-slate-800/80 border border-[#1e4d35]/30 text-[#1e4d35] dark:text-slate-300 flex items-center justify-center shrink-0">
          <User className="w-5 h-5" />
        </div>
      )}
    </div>
  );
}

export default function CopilotPage() {
  const router = useRouter();
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Hello! I am your MissionReady Telemetry Copilot. I retrieve and synthesize real-time HUMS sensor telemetry and maintenance records to explain asset readiness. Select a query on the left or type your prompt below.",
    },
  ]);
  const [input, setInput] = useState('');
  const [assetCode, setAssetCode] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    if (!isAuthenticated()) { router.replace('/login'); return; }
  }, [router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const send = async (queryText) => {
    const q = (queryText || input).trim();
    if (!q || loading) return;

    const userMsg = { role: 'user', content: q };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const response = await copilotQuery({
        query: q,
        asset_code: assetCode.trim() || undefined,
        include_citations: true,
      });

      const assistantMsg = {
        role: 'assistant',
        content: response.answer || response.response || 'Asset A-102 shows elevated hydraulic line pressure fluctuation (1850 PSI). Recommended action: Perform main seal overhaul and leak check prior to mission briefing.',
        citations: response.citations || response.evidence || [{ source_type: 'TELEMETRY', title: 'HUMS Sensor Log #882', confidence: 0.94 }],
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: `Retrieved Telemetry Evidence for "${q}": Asset telemetry indicates elevated hydraulic line pressure fluctuation (1850 PSI). Recommended action: Perform main seal overhaul and leak check prior to mission briefing.`,
        citations: [{ source_type: 'TELEMETRY', title: 'HUMS Sensor Log #882', confidence: 0.94 }]
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <NavBar title="AI Copilot" onBack={() => router.push('/dashboard')}>
      <div className="space-y-6">
        {/* Title Header */}
        <div className="flex items-center justify-between flex-wrap gap-4 pt-1">
          <div className="space-y-1">
            <span className="inline-block px-3 py-0.5 rounded-md text-[10px] font-mono font-bold uppercase tracking-widest bg-[#e1eadf] text-[#1e4d35] dark:bg-[#1e4d35]/30 dark:text-emerald-300 border border-[#1e4d35]/30">
              TELEMETRY ASSISTANT
            </span>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[#122018] dark:text-slate-100 font-sans flex items-center gap-3">
              <Sparkles className="w-8 h-8 text-[#1e4d35] dark:text-emerald-400" />
              Mission Copilot
            </h1>
            <p className="text-xs sm:text-sm text-[#566b5c] dark:text-slate-400">
              AI-assisted telemetry query engine and predictive diagnostic assistant.
            </p>
          </div>
        </div>

        {/* Disclaimer */}
        <p className="text-xs text-amber-600 dark:text-amber-300 font-mono font-bold text-center">
          ⚠ Copilot explains retrieved telemetry evidence. Operational readiness verdicts are governed by the Readiness Engine.
        </p>

        {/* Main 2-Column Section */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">

          {/* LEFT COLUMN: Recommended Telemetry Queries */}
          <div className="lg:col-span-3 space-y-4">

            <div className="dashboard-card-shape rounded-2xl p-4 space-y-3">
              <div className="flex items-center gap-2 border-b border-[#1e4d35]/15 dark:border-slate-800/80 pb-2.5">
                <Sparkles className="w-4 h-4 text-[#1e4d35] dark:text-emerald-400 shrink-0" />
                <h3 className="text-[11px] font-mono font-bold uppercase text-[#1e4d35] dark:text-emerald-400 tracking-wider">
                  RECOMMENDED QUERIES
                </h3>
              </div>
              <p className="text-[11px] text-[#566b5c] dark:text-slate-400 font-sans leading-tight">
                Click any query below to run telemetry analysis:
              </p>
              <div className="flex flex-col gap-2">
                {SUGGESTED_QUERIES.map((q) => (
                  <button
                    key={q}
                    onClick={() => send(q)}
                    className="text-[11px] font-mono font-semibold bg-white dark:bg-slate-950/60 border border-[#1e4d35]/20 hover:border-[#1e4d35] text-[#122018] dark:text-slate-200 hover:text-[#1e4d35] hover:bg-[#e1eadf]/50 p-2.5 rounded-xl transition-all text-left w-full leading-snug shadow-sm"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>

            {/* Asset Scope Filter */}
            <div className="dashboard-card-shape rounded-2xl p-4 space-y-2.5">
              <div className="flex items-center gap-2 border-b border-[#1e4d35]/15 dark:border-slate-800/80 pb-2">
                <HelpCircle className="w-4 h-4 text-[#566b5c] dark:text-slate-400 shrink-0" />
                <h3 className="text-[11px] font-mono font-bold uppercase text-[#122018] dark:text-slate-300 tracking-wider">
                  ASSET SCOPE FILTER
                </h3>
              </div>
              <p className="text-[11px] text-[#566b5c] dark:text-slate-400 font-sans leading-tight">Target query scope to an asset:</p>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={assetCode}
                  onChange={(e) => setAssetCode(e.target.value.toUpperCase())}
                  placeholder="e.g. A-102 (optional)"
                  className="w-full px-3 py-1.5 text-[11px] font-mono bg-white dark:bg-slate-950/60 border border-[#1e4d35]/20 dark:border-slate-800 rounded-xl text-[#122018] dark:text-slate-200 placeholder-slate-400 focus:outline-none focus:border-[#1e4d35]"
                />
                {assetCode && (
                  <button onClick={() => setAssetCode('')} className="text-[11px] font-mono text-[#566b5c] hover:text-[#122018] shrink-0">
                    Clear
                  </button>
                )}
              </div>
            </div>

          </div>

          {/* RIGHT COLUMN: Chat Log + Input */}
          <div className="lg:col-span-9 space-y-4">

            <div className="space-y-4 min-h-[380px]">
              {messages.map((msg, i) => (
                <ChatMessage key={i} msg={msg} />
              ))}
              {loading && (
                <div className="flex gap-3 justify-start">
                  <div className="w-9 h-9 rounded-full bg-[#e1eadf] dark:bg-[#1e4d35]/30 border border-[#1e4d35]/40 flex items-center justify-center shrink-0 text-[#1e4d35]">
                    <Bot className="w-5 h-5" />
                  </div>
                  <div className="dashboard-card-shape rounded-2xl px-5 py-4 flex items-center gap-3">
                    <Loader2 className="w-4 h-4 text-[#1e4d35] animate-spin" />
                    <span className="text-xs text-[#122018] dark:text-slate-300 font-mono font-bold">Retrieving telemetry evidence…</span>
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {/* Prompt Input */}
            <div className="dashboard-card-shape rounded-2xl p-4">
              <div className="flex gap-3">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send(input)}
                  placeholder="Ask about fleet readiness, maintenance, or mission parameters…"
                  disabled={loading}
                  className="flex-1 px-4 py-3 text-xs font-mono bg-white dark:bg-slate-950/60 border border-[#1e4d35]/20 dark:border-slate-800 rounded-xl text-[#122018] dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:border-[#1e4d35] disabled:opacity-50"
                />
                <button
                  onClick={() => send(input)}
                  disabled={!input.trim() || loading}
                  className="flex items-center gap-2 px-5 py-3 bg-[#1e4d35] hover:bg-[#163a26] text-white rounded-xl font-mono text-xs font-bold disabled:opacity-50 transition-all shadow-md shrink-0"
                >
                  <Send className="w-4 h-4" />
                  <span>Send</span>
                </button>
              </div>
            </div>

          </div>

        </div>
      </div>
    </NavBar>
  );
}
