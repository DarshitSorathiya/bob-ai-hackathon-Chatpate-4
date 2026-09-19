'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { Send, Bot, User, Sparkles, Loader2, HelpCircle, AlertTriangle, ChevronDown, ChevronRight } from 'lucide-react';
import { queryCopilot } from '../../lib/api';
import NavBar from '../../components/NavBar';
import RoleGuard from '../../components/RoleGuard';

// ─── Lightweight markdown renderer ───────────────────────────────────────────
// Handles: headings, bold, italic, inline-code, code blocks, tables,
//          ordered lists, unordered lists, horizontal rules, plain paragraphs.
// Zero dependencies — pure React + Tailwind.

function renderInline(text) {
  // Bold **text** or __text__, italic *text* or _text_, inline `code`
  const parts = [];
  const re = /(\*\*|__)(.+?)\1|(\*|_)(.+?)\3|`([^`]+)`/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    if (m[1]) parts.push(<strong key={m.index} className="font-bold">{m[2]}</strong>);
    else if (m[3]) parts.push(<em key={m.index} className="italic">{m[4]}</em>);
    else parts.push(
      <code key={m.index} className="px-1.5 py-0.5 rounded bg-[#1e4d35]/10 dark:bg-slate-700/60 text-[#1e4d35] dark:text-emerald-300 font-mono text-[11px]">
        {m[5]}
      </code>
    );
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts.length === 1 && typeof parts[0] === 'string' ? parts[0] : parts;
}

function MarkdownTable({ lines }) {
  // lines[0] = header row, lines[1] = separator, lines[2+] = data rows
  const parse = (line) =>
    line.replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
  const headers = parse(lines[0]);
  const rows = lines.slice(2).map(parse);
  return (
    <div className="overflow-x-auto rounded-xl border border-[#1e4d35]/20 dark:border-slate-700 my-2">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="bg-[#e1eadf]/60 dark:bg-[#0d1b13]/60 border-b border-[#1e4d35]/20 dark:border-slate-700">
            {headers.map((h, i) => (
              <th key={i} className="px-3 py-2 text-left font-bold text-[#1e4d35] dark:text-emerald-400 uppercase tracking-wide text-[10px] whitespace-nowrap">
                {renderInline(h)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri} className="border-b border-[#1e4d35]/10 dark:border-slate-800/60 hover:bg-[#e1eadf]/20 dark:hover:bg-slate-900/30">
              {row.map((cell, ci) => (
                <td key={ci} className="px-3 py-2 text-[#122018] dark:text-slate-200 align-top leading-snug">
                  {renderInline(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MarkdownContent({ text }) {
  if (!text) return null;
  const lines = text.split('\n');
  const blocks = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Fenced code block ```
    if (line.startsWith('```')) {
      const lang = line.slice(3).trim();
      const codeLines = [];
      i++;
      while (i < lines.length && !lines[i].startsWith('```')) {
        codeLines.push(lines[i]);
        i++;
      }
      blocks.push(
        <pre key={i} className="my-2 p-3 rounded-xl bg-[#0d1b13]/80 dark:bg-slate-900/80 text-emerald-300 dark:text-emerald-200 text-[11px] font-mono overflow-x-auto leading-relaxed border border-[#1e4d35]/30">
          <code>{codeLines.join('\n')}</code>
        </pre>
      );
      i++;
      continue;
    }

    // Table (line contains | and next line is separator)
    if (line.includes('|') && lines[i + 1]?.match(/^[\s|:-]+$/)) {
      const tableLines = [line];
      i++;
      while (i < lines.length && lines[i].includes('|')) {
        tableLines.push(lines[i]);
        i++;
      }
      blocks.push(<MarkdownTable key={i} lines={tableLines} />);
      continue;
    }

    // Heading # / ## / ###
    const hMatch = line.match(/^(#{1,3})\s+(.+)/);
    if (hMatch) {
      const level = hMatch[1].length;
      const cls = level === 1
        ? 'text-base font-extrabold text-[#122018] dark:text-slate-100 mt-3 mb-1'
        : level === 2
          ? 'text-sm font-bold text-[#122018] dark:text-slate-100 mt-2 mb-0.5'
          : 'text-xs font-bold text-[#1e4d35] dark:text-emerald-400 uppercase tracking-widest mt-2 mb-0.5';
      blocks.push(<p key={i} className={cls}>{renderInline(hMatch[2])}</p>);
      i++;
      continue;
    }

    // Horizontal rule ---
    if (line.match(/^[-*_]{3,}$/)) {
      blocks.push(<hr key={i} className="my-3 border-[#1e4d35]/20 dark:border-slate-700" />);
      i++;
      continue;
    }

    // Unordered list — collect consecutive bullet lines
    if (line.match(/^[-*+]\s/)) {
      const items = [];
      while (i < lines.length && lines[i].match(/^[-*+]\s/)) {
        items.push(lines[i].replace(/^[-*+]\s/, ''));
        i++;
      }
      blocks.push(
        <ul key={i} className="my-1.5 space-y-1 pl-4">
          {items.map((item, idx) => (
            <li key={idx} className="flex items-start gap-2 text-sm text-[#122018] dark:text-slate-200 leading-snug">
              <span className="text-[#1e4d35] dark:text-emerald-400 mt-0.5 shrink-0">›</span>
              <span>{renderInline(item)}</span>
            </li>
          ))}
        </ul>
      );
      continue;
    }

    // Ordered list — collect consecutive numbered lines
    if (line.match(/^\d+\.\s/)) {
      const items = [];
      let num = 1;
      while (i < lines.length && lines[i].match(/^\d+\.\s/)) {
        items.push({ n: num++, text: lines[i].replace(/^\d+\.\s/, '') });
        i++;
      }
      blocks.push(
        <ol key={i} className="my-1.5 space-y-1 pl-4">
          {items.map((item, idx) => (
            <li key={idx} className="flex items-start gap-2 text-sm text-[#122018] dark:text-slate-200 leading-snug">
              <span className="text-[#1e4d35] dark:text-emerald-400 font-mono font-bold shrink-0 min-w-[1.2rem]">{item.n}.</span>
              <span>{renderInline(item.text)}</span>
            </li>
          ))}
        </ol>
      );
      continue;
    }

    // Bold-only heading pattern **Heading** on its own line
    if (line.match(/^\*\*[^*]+\*\*$/) || line.match(/^__[^_]+__$/)) {
      const inner = line.replace(/^\*\*|\*\*$|^__|__$/g, '');
      blocks.push(
        <p key={i} className="text-sm font-bold text-[#122018] dark:text-slate-100 mt-3 mb-0.5">
          {inner}
        </p>
      );
      i++;
      continue;
    }

    // Empty line — spacer
    if (line.trim() === '') {
      i++;
      continue;
    }

    // Plain paragraph
    blocks.push(
      <p key={i} className="text-sm font-sans text-[#122018] dark:text-slate-200 leading-relaxed">
        {renderInline(line)}
      </p>
    );
    i++;
  }

  return <div className="space-y-0.5">{blocks}</div>;
}

const SUGGESTED_QUERIES = [
  'Give me a fleet readiness summary',
  'What maintenance work orders are open?',
  'Show active critical alerts',
  'What missions are currently planned?',
  'Are there any data quality issues?',
];

// ─── Evidence panel ───────────────────────────────────────────────────────────

function EvidenceItem({ item }) {
  const [open, setOpen] = useState(false);
  const hasError = Boolean(item.error);
  return (
    <div className={`rounded-xl border text-[11px] font-mono overflow-hidden ${
      hasError
        ? 'border-red-500/30 bg-red-500/5'
        : 'border-[#1e4d35]/20 dark:border-slate-700/60 bg-[#f4f6ee]/60 dark:bg-slate-900/40'
    }`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-left"
      >
        <span className="flex items-center gap-2">
          {hasError
            ? <AlertTriangle className="w-3 h-3 text-red-500 shrink-0" />
            : <span className="w-3 h-3 rounded-full bg-[#1e4d35]/30 dark:bg-emerald-500/30 shrink-0" />}
          <span className={`font-bold uppercase tracking-widest ${hasError ? 'text-red-500' : 'text-[#1e4d35] dark:text-emerald-400'}`}>
            {item.tool_name}
          </span>
          <span className="text-[#566b5c] dark:text-slate-500 normal-case font-normal truncate max-w-[280px]">
            — {item.query}
          </span>
        </span>
        {open
          ? <ChevronDown className="w-3.5 h-3.5 text-[#566b5c] shrink-0" />
          : <ChevronRight className="w-3.5 h-3.5 text-[#566b5c] shrink-0" />}
      </button>
      {open && (
        <div className="px-3 pb-3 border-t border-[#1e4d35]/10 dark:border-slate-700/40 pt-2">
          {hasError
            ? <p className="text-red-500">{item.error}</p>
            : <pre className="text-[10px] text-[#122018] dark:text-slate-300 whitespace-pre-wrap break-words leading-relaxed">
                {JSON.stringify(item.data, null, 2)}
              </pre>
          }
        </div>
      )}
    </div>
  );
}

// ─── Chat message ─────────────────────────────────────────────────────────────

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
        {/* Answer — rendered markdown for assistant, plain text for user */}
        {isUser
          ? <p className="text-sm font-sans leading-relaxed">{msg.content}</p>
          : <MarkdownContent text={msg.content} />
        }

        {/* Model badge */}
        {msg.model_used && (
          <p className="text-[10px] font-mono text-[#566b5c] dark:text-slate-500">
            Powered by <span className="font-bold text-[#1e4d35] dark:text-emerald-400">{msg.model_used}</span>
          </p>
        )}

        {/* Evidence items — uses real backend shape: tool_name / query / data / error */}
        {msg.evidence?.length > 0 && (
          <div className="pt-3 border-t border-[#1e4d35]/15 dark:border-slate-800/60 space-y-2">
            <p className="text-[11px] font-mono font-bold text-[#122018] dark:text-slate-300 uppercase tracking-widest">
              Retrieved Evidence ({msg.evidence.length})
            </p>
            {msg.evidence.map((item, i) => (
              <EvidenceItem key={i} item={item} />
            ))}
          </div>
        )}

        {/* Error */}
        {msg.error && (
          <div className="flex items-start gap-2 text-xs font-mono text-red-600 dark:text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl p-3">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{msg.error}</span>
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

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function CopilotPage() {
  const router = useRouter();
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Hello! I am your MissionReady Telemetry Copilot. I retrieve and synthesize real fleet data to explain asset readiness, maintenance status, and mission risks. Select a suggested query on the left or type your question below.',
    },
  ]);
  const [input, setInput] = useState('');
  const [assetCode, setAssetCode] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const send = async (queryText) => {
    const q = (queryText || input).trim();
    if (!q || loading) return;

    setMessages((prev) => [...prev, { role: 'user', content: q }]);
    setInput('');
    setLoading(true);

    try {
      // queryCopilot(question, assetCode) — matches lib/api.js signature exactly
      const response = await queryCopilot(q, assetCode.trim() || null);

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          // Backend returns { answer, model_used, grounded, evidence[] }
          content: response.answer || 'No answer was returned. Review the evidence below.',
          model_used: response.model_used || null,
          evidence: response.evidence || [],
        },
      ]);
    } catch (err) {
      // Show the real error — never fake data
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'The copilot could not retrieve a response.',
          error: err.message || 'An unexpected error occurred. Check that the backend is running and you are authenticated.',
          evidence: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <RoleGuard minRole="operator">
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
                AI-assisted telemetry query engine — powered by real backend data.
              </p>
            </div>
          </div>

          {/* Disclaimer */}
          <p className="text-xs text-amber-600 dark:text-amber-300 font-mono font-bold text-center">
            ⚠ Copilot explains retrieved data only. Operational readiness verdicts are governed by the Readiness Engine.
          </p>

          {/* 2-Column Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">

            {/* LEFT: Suggested queries + asset filter */}
            <div className="lg:col-span-3 space-y-4">

              <div className="dashboard-card-shape rounded-2xl p-4 space-y-3">
                <div className="flex items-center gap-2 border-b border-[#1e4d35]/15 dark:border-slate-800/80 pb-2.5">
                  <Sparkles className="w-4 h-4 text-[#1e4d35] dark:text-emerald-400 shrink-0" />
                  <h3 className="text-[11px] font-mono font-bold uppercase text-[#1e4d35] dark:text-emerald-400 tracking-wider">
                    SUGGESTED QUERIES
                  </h3>
                </div>
                <p className="text-[11px] text-[#566b5c] dark:text-slate-400 font-sans leading-tight">
                  Click any query to run analysis:
                </p>
                <div className="flex flex-col gap-2">
                  {SUGGESTED_QUERIES.map((q) => (
                    <button
                      key={q}
                      onClick={() => send(q)}
                      disabled={loading}
                      className="text-[11px] font-mono font-semibold bg-white dark:bg-slate-950/60 border border-[#1e4d35]/20 hover:border-[#1e4d35] text-[#122018] dark:text-slate-200 hover:text-[#1e4d35] hover:bg-[#e1eadf]/50 p-2.5 rounded-xl transition-all text-left w-full leading-snug shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>

              {/* Asset scope filter */}
              <div className="dashboard-card-shape rounded-2xl p-4 space-y-2.5">
                <div className="flex items-center gap-2 border-b border-[#1e4d35]/15 dark:border-slate-800/80 pb-2">
                  <HelpCircle className="w-4 h-4 text-[#566b5c] dark:text-slate-400 shrink-0" />
                  <h3 className="text-[11px] font-mono font-bold uppercase text-[#122018] dark:text-slate-300 tracking-wider">
                    ASSET SCOPE
                  </h3>
                </div>
                <p className="text-[11px] text-[#566b5c] dark:text-slate-400 font-sans leading-tight">
                  Narrow query to a specific asset code:
                </p>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={assetCode}
                    onChange={(e) => setAssetCode(e.target.value.toUpperCase())}
                    placeholder="e.g. TJS-014 (optional)"
                    className="w-full px-3 py-1.5 text-[11px] font-mono bg-white dark:bg-slate-950/60 border border-[#1e4d35]/20 dark:border-slate-800 rounded-xl text-[#122018] dark:text-slate-200 placeholder-slate-400 focus:outline-none focus:border-[#1e4d35]"
                  />
                  {assetCode && (
                    <button
                      onClick={() => setAssetCode('')}
                      className="text-[11px] font-mono text-[#566b5c] hover:text-[#122018] shrink-0"
                    >
                      Clear
                    </button>
                  )}
                </div>
                {assetCode && (
                  <p className="text-[10px] font-mono text-[#1e4d35] dark:text-emerald-400">
                    Scoped to: <strong>{assetCode}</strong>
                  </p>
                )}
              </div>

            </div>

            {/* RIGHT: Chat log + input */}
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
                      <span className="text-xs text-[#122018] dark:text-slate-300 font-mono font-bold">
                        Retrieving evidence from backend…
                      </span>
                    </div>
                  </div>
                )}
                <div ref={bottomRef} />
              </div>

              {/* Prompt input */}
              <div className="dashboard-card-shape rounded-2xl p-4">
                <div className="flex gap-3">
                  <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send(input)}
                    placeholder="Ask about fleet readiness, maintenance, alerts, or mission parameters…"
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
    </RoleGuard>
  );
}
