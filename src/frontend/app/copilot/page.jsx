'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Send, Bot, User, Sparkles, Loader2 } from 'lucide-react';
import { isAuthenticated, copilotQuery } from '../../lib/api';
import NavBar from '../../components/NavBar';

const SUGGESTED_QUERIES = [
  'Why is asset AH-64-01 AT_RISK?',
  'What maintenance is required for AH-64-01?',
  'Show critical telemetry alerts from the last 24 hours',
  'Is CH-47-03 ready for a 4-hour mission?',
];

function ChatMessage({ msg }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className="w-9 h-9 rounded-full bg-blue-600/20 border border-blue-500/40 flex items-center justify-center shrink-0 text-blue-400 shadow-sm">
          <Bot className="w-5 h-5" />
        </div>
      )}
      <div className={`max-w-2xl rounded-2xl p-5 border-[3px] border-white backdrop-blur-xl shadow-xl ${
        isUser
          ? 'bg-blue-600/30 text-slate-100'
          : 'bg-[#0a0f1d]/80 text-slate-100 space-y-3'
      }`}>
        <p className="text-sm font-sans leading-relaxed whitespace-pre-wrap">{msg.content}</p>

        {msg.citations?.length > 0 && (
          <div className="pt-3 border-t border-slate-800/80 font-mono text-xs text-slate-400">
            <p className="font-bold text-slate-300 mb-1">Retrieved Evidence ({msg.citations.length}):</p>
            <ul className="space-y-1">
              {msg.citations.map((c, i) => (
                <li key={i} className="flex items-center gap-2">
                  <span className="text-blue-400">[{c.source_type || 'source'}]</span>
                  <span className="truncate">{c.title || c.id}</span>
                  {c.confidence != null && (
                    <span className="text-emerald-400 ml-auto font-bold">{Math.round(c.confidence * 100)}% match</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {isUser && (
        <div className="w-9 h-9 rounded-full bg-slate-800/80 border border-slate-700 flex items-center justify-center shrink-0 text-slate-300">
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
      content: "Hello! I am your MissionReady Telemetry Copilot. I retrieve and synthesize real-time HUMS sensor telemetry and maintenance records to explain asset readiness. How can I assist you today?",
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
        content: response.answer || response.response || 'No response provided.',
        citations: response.citations || response.evidence || [],
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: `Error retrieving telemetry response: ${err.message}`,
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <NavBar title="AI Copilot" onBack={() => router.push('/dashboard')}>
      <div className="space-y-6">
        {/* Title Header */}
        <div className="flex items-center justify-between flex-wrap gap-4 pt-2">
          <div className="space-y-1">
            <span className="inline-block px-3 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-widest bg-blue-950/80 text-blue-400 border border-blue-800/60 mb-1">
              TELEMETRY ASSISTANT
            </span>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-100 font-sans flex items-center gap-3">
              <Sparkles className="w-8 h-8 text-blue-400" />
              Mission Copilot
            </h1>
          </div>
        </div>

        {/* Disclaimer Card Box */}
        <div className="bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl p-4 backdrop-blur-xl shadow-xl text-center">
          <p className="text-xs text-amber-300 font-mono font-bold">
            ⚠ Copilot explains retrieved evidence only. All operational readiness decisions are made by the deterministic ReadinessEngine.
          </p>
        </div>

        {/* Chat area */}
        <div className="space-y-4">
          {messages.map((msg, i) => (
            <ChatMessage key={i} msg={msg} />
          ))}
          {loading && (
            <div className="flex gap-3 justify-start">
              <div className="w-9 h-9 rounded-full bg-blue-600/20 border border-blue-500/40 flex items-center justify-center shrink-0 text-blue-400">
                <Bot className="w-5 h-5" />
              </div>
              <div className="bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl px-5 py-4 flex items-center gap-3 backdrop-blur-xl shadow-xl">
                <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                <span className="text-xs text-slate-300 font-mono font-bold">Retrieving telemetry evidence…</span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Suggested queries */}
        {messages.length === 1 && !loading && (
          <div className="bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl p-6 backdrop-blur-xl shadow-xl space-y-3">
            <p className="text-xs text-slate-400 font-mono font-bold">RECOMMENDED TELEMETRY QUERIES</p>
            <div className="flex flex-wrap gap-3">
              {SUGGESTED_QUERIES.map((q) => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  className="text-xs font-mono font-bold bg-slate-950/60 border border-slate-800 hover:border-blue-400/60 text-slate-200 hover:text-blue-300 px-4 py-2.5 rounded-xl transition-all text-left"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input Card Box */}
        <div className="bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl p-5 backdrop-blur-xl shadow-xl space-y-3">
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono text-slate-400 font-bold">Asset context:</span>
            <input
              type="text"
              value={assetCode}
              onChange={(e) => setAssetCode(e.target.value.toUpperCase())}
              placeholder="e.g. AH-64-01 (optional)"
              className="px-3 py-1.5 text-xs font-mono bg-slate-950/60 border border-slate-800 rounded-xl text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 w-52"
            />
            {assetCode && (
              <button onClick={() => setAssetCode('')} className="text-xs font-mono text-slate-400 hover:text-slate-200">clear</button>
            )}
          </div>
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send(input)}
              placeholder="Ask about fleet readiness, maintenance, or mission parameters…"
              disabled={loading}
              className="flex-1 px-4 py-3 text-xs font-mono bg-slate-950/60 border border-slate-800 rounded-xl text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 disabled:opacity-50"
            />
            <button
              onClick={() => send(input)}
              disabled={!input.trim() || loading}
              className="flex items-center gap-2 px-5 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-mono text-xs font-bold disabled:opacity-50 transition-all shadow-lg shadow-blue-600/20"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </NavBar>
  );
}
