'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Send, Loader2, Bot, User, ChevronDown, ChevronUp, Info } from 'lucide-react';
import { isAuthenticated, queryCopilot } from '../../lib/api';
import NavBar from '../../components/NavBar';

function EvidencePanel({ evidence }) {
  const [open, setOpen] = useState(false);
  if (!evidence?.length) return null;
  return (
    <div className="mt-3 border border-slate-800 rounded-lg overflow-hidden text-[11px] font-mono">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2 bg-slate-900/60 text-slate-400 hover:text-slate-200 transition-colors"
      >
        <span className="flex items-center gap-1.5">
          <Info className="w-3 h-3" />
          Evidence ({evidence.length} source{evidence.length !== 1 ? 's' : ''})
        </span>
        {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      </button>
      {open && (
        <div className="divide-y divide-slate-800">
          {evidence.map((e, i) => (
            <div key={i} className="px-3 py-2 bg-slate-950/50">
              <p className="text-blue-400 mb-1">{e.tool_name}: {e.query}</p>
              {e.error ? (
                <p className="text-red-400">{e.error}</p>
              ) : (
                <pre className="text-slate-400 text-[10px] overflow-x-auto whitespace-pre-wrap max-h-40">
                  {JSON.stringify(e.data, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ModelBadge({ modelUsed }) {
  if (!modelUsed) return null;
  const isWatsonx = modelUsed.startsWith('ibm/');
  const isGroq    = modelUsed.startsWith('groq/');
  const cls = isWatsonx
    ? 'text-blue-400 border-blue-500/30 bg-blue-500/10'
    : isGroq
    ? 'text-violet-400 border-violet-500/30 bg-violet-500/10'
    : 'text-slate-500 border-slate-700 bg-slate-800/40';
  const label = isWatsonx ? `IBM watsonx · ${modelUsed.replace('ibm/', '')}`
              : isGroq    ? `Groq · ${modelUsed.replace('groq/', '')}`
              : modelUsed;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded font-mono text-[10px] border mt-2 ${cls}`}>
      {label}
    </span>
  );
}

function ChatMessage({ msg }) {
  const isUser  = msg.role === 'user';
  const isError = msg.isError;
  return (
    <div className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className={`w-8 h-8 rounded-full border flex items-center justify-center shrink-0 ${
          isError
            ? 'bg-amber-600/20 border-amber-500/40'
            : 'bg-blue-600/20 border-blue-500/40'
        }`}>
          <Bot className={`w-4 h-4 ${isError ? 'text-amber-400' : 'text-blue-400'}`} />
        </div>
      )}
      <div className={`max-w-[80%] ${isUser ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
        <div className={`rounded-xl px-4 py-3 text-sm ${
          isUser
            ? 'bg-blue-600/20 border border-blue-500/30 text-slate-100'
            : isError
            ? 'bg-amber-950/30 border border-amber-800/40 text-amber-200'
            : 'bg-slate-900/60 border border-slate-800 text-slate-200'
        }`}>
          <p className="whitespace-pre-wrap">{msg.content}</p>
          <ModelBadge modelUsed={msg.model_used} />
        </div>
        {msg.evidence && <EvidencePanel evidence={msg.evidence} />}
      </div>
      {isUser && (
        <div className="w-8 h-8 rounded-full bg-slate-700/50 border border-slate-600 flex items-center justify-center shrink-0">
          <User className="w-4 h-4 text-slate-400" />
        </div>
      )}
    </div>
  );
}

const SUGGESTED_QUERIES = [
  "What is the overall fleet readiness status?",
  "Are there any critical maintenance items blocking missions?",
  "How many assets are at risk right now?",
  "What are the most urgent maintenance tasks?",
  "Are there any active alerts I should know about?",
];

export default function CopilotPage() {
  const router = useRouter();
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Hello! I'm the MissionReady Copilot. I can answer questions about fleet readiness, maintenance, missions, and alerts — all backed by real data from the database. No invented values.\n\nAsk me anything, like: \"Why is AH-64-01 at risk?\" or \"What are the most urgent maintenance tasks?\"",
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
  }, [messages]);

  const send = async (question) => {
    if (!question.trim() || loading) return;
    const q = question.trim();
    setInput('');
    setMessages((prev) => [...prev, { role: 'user', content: q }]);
    setLoading(true);
    try {
      const res = await queryCopilot(q, assetCode || null);
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: res.answer,
        evidence: res.evidence,
        model_used: res.model_used,
      }]);
    } catch {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        isError: true,
        content: 'The AI copilot service is unavailable right now. Please try again later or contact your system administrator.',
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#070a12] text-slate-100 font-sans flex flex-col">
      <NavBar title="Copilot" onBack={() => router.push('/dashboard')} />

      {/* Disclaimer banner */}
      <div className="bg-amber-950/30 border-b border-amber-800/30 px-4 py-2 text-center">
        <p className="text-[11px] text-amber-400 font-mono">
          ⚠ Copilot explains retrieved evidence only. It does NOT make readiness decisions. All operational decisions are made by the deterministic ReadinessEngine.
        </p>
      </div>

      {/* Chat area */}
      <main className="flex-1 max-w-4xl w-full mx-auto px-4 sm:px-6 py-6">
        <div className="space-y-4">
          {messages.map((msg, i) => (
            <ChatMessage key={i} msg={msg} />
          ))}
          {loading && (
            <div className="flex gap-3 justify-start">
              <div className="w-8 h-8 rounded-full bg-blue-600/20 border border-blue-500/40 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 text-blue-400" />
              </div>
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl px-4 py-3 flex items-center gap-2">
                <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                <span className="text-sm text-slate-400 font-mono">Retrieving evidence…</span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Suggested queries */}
        {messages.length === 1 && !loading && (
          <div className="mt-6">
            <p className="text-[11px] text-slate-500 font-mono mb-3">SUGGESTED QUERIES</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED_QUERIES.map((q) => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  className="text-xs font-mono bg-slate-900/60 border border-slate-700 hover:border-blue-500/50 text-slate-300 hover:text-blue-300 px-3 py-1.5 rounded-lg transition-colors text-left"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
      </main>

      {/* Input */}
      <div className="sticky bottom-0 bg-[#070a12]/95 backdrop-blur-md border-t border-slate-800/70 px-4 sm:px-6 py-4">
        <div className="max-w-4xl mx-auto space-y-2">
          {/* Asset code context row */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-slate-600 whitespace-nowrap">Asset context:</span>
            <input
              type="text"
              value={assetCode}
              onChange={(e) => setAssetCode(e.target.value.toUpperCase())}
              placeholder="e.g. AH-64-01 (optional)"
              className="px-2.5 py-1 text-xs font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-300 placeholder-slate-600 focus:outline-none focus:border-blue-500 w-48"
            />
            {assetCode && (
              <button onClick={() => setAssetCode('')} className="text-[10px] font-mono text-slate-600 hover:text-slate-400">clear</button>
            )}
          </div>
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send(input)}
              placeholder="Ask about fleet readiness, maintenance, or missions…"
              disabled={loading}
              className="flex-1 px-4 py-3 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-xl text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 disabled:opacity-50"
            />
            <button
              onClick={() => send(input)}
              disabled={!input.trim() || loading}
              className="flex items-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-mono text-sm font-bold disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
