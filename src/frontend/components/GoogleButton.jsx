'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight } from 'lucide-react';
import { loginWithGoogle, saveSession, getUserRole } from '../lib/api';

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '';

function getRoleRedirect(role) {
  if (role === 'admin') return '/admin';
  return '/dashboard';
}

/**
 * GoogleButton — triggers Google Identity Services (GIS) when NEXT_PUBLIC_GOOGLE_CLIENT_ID
 * is set.  When the env var is absent the button is rendered disabled with a tooltip so the
 * UI never crashes and the user gets a clear message instead of a fake session.
 */
export default function GoogleButton({
  onSuccess,
  onError,
  label = 'Continue with Google',
}) {
  const router = useRouter();
  const [status, setStatus] = useState('idle'); // idle | loading | error
  const [errorMsg, setErrorMsg] = useState('');

  const isConfigured = Boolean(GOOGLE_CLIENT_ID);

  useEffect(() => {
    if (!isConfigured) return;
    const scriptId = 'google-gsi-script';
    if (!document.getElementById(scriptId)) {
      const script = document.createElement('script');
      script.id = scriptId;
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }
  }, [isConfigured]);

  const handleCredentialResponse = async (response) => {
    setStatus('loading');
    setErrorMsg('');
    try {
      const authResponse = await loginWithGoogle(response.credential);
      saveSession(authResponse);
      setStatus('idle');
      const dest = getRoleRedirect(getUserRole());
      if (onSuccess) onSuccess(authResponse);
      router.push(dest);
    } catch (err) {
      const msg = err.message || 'Google authentication failed.';
      setErrorMsg(msg);
      setStatus('error');
      if (onError) onError(msg);
    }
  };

  const handleGoogleClick = () => {
    if (!isConfigured) return; // button is disabled — do nothing

    if (!window.google?.accounts?.id) {
      const msg = 'Google Sign-In is not available yet. Please try again in a moment.';
      setErrorMsg(msg);
      setStatus('error');
      if (onError) onError(msg);
      return;
    }

    setStatus('loading');
    setErrorMsg('');

    try {
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: handleCredentialResponse,
        auto_select: false,
      });
      window.google.accounts.id.prompt((notification) => {
        // GIS calls this when the One Tap prompt is suppressed or closed
        if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
          const reason = notification.getNotDisplayedReason?.() || notification.getSkippedReason?.() || 'unknown';
          const msg = `Google sign-in was not shown (${reason}). Try signing in via your browser's Google account.`;
          setErrorMsg(msg);
          setStatus('error');
          if (onError) onError(msg);
        }
      });
    } catch (err) {
      const msg = err.message || 'Failed to start Google sign-in.';
      setErrorMsg(msg);
      setStatus('error');
      if (onError) onError(msg);
    }
  };

  return (
    <div className="w-full space-y-2">
      <button
        type="button"
        onClick={handleGoogleClick}
        disabled={!isConfigured || status === 'loading'}
        title={!isConfigured ? 'Google OAuth is not configured on this server (NEXT_PUBLIC_GOOGLE_CLIENT_ID is not set).' : undefined}
        className={`w-full flex items-center justify-between px-5 py-3 rounded-xl border shadow-md transition-all duration-200 group select-none
          ${!isConfigured
            ? 'bg-slate-100 dark:bg-slate-900/60 border-slate-300 dark:border-slate-700 text-slate-400 dark:text-slate-500 cursor-not-allowed opacity-60'
            : 'bg-white dark:bg-[#122419] hover:bg-[#e1eadf]/50 dark:hover:bg-[#163a26]/70 border-[#1e4d35]/25 hover:border-[#1e4d35]/60 text-[#122018] dark:text-slate-100 cursor-pointer'
          }`}
      >
        {/* Left: Google G Logo + Vertical Divider */}
        <div className="flex items-center gap-4 shrink-0">
          <GoogleLogo muted={!isConfigured} />
          <div className="h-5 w-px bg-[#1e4d35]/20 dark:bg-slate-800" />
        </div>

        {/* Center: label */}
        <span className="text-sm font-medium font-sans tracking-wide group-hover:text-[#1e4d35] dark:group-hover:text-emerald-400 transition-colors">
          {!isConfigured ? 'Google Sign-In Not Configured' : label}
        </span>

        {/* Right: Arrow */}
        <ArrowRight className="w-4 h-4 text-[#1e4d35] dark:text-emerald-400 group-hover:translate-x-1 transition-transform shrink-0" />
      </button>

      {status === 'loading' && (
        <p className="text-[11px] font-mono text-slate-400 text-center animate-pulse">
          Verifying with Google…
        </p>
      )}

      {status === 'error' && errorMsg && (
        <p className="text-[11px] font-mono text-amber-700 dark:text-amber-400 text-center bg-amber-500/10 border border-amber-500/30 px-3 py-1.5 rounded-md">
          {errorMsg}
        </p>
      )}

      {!isConfigured && (
        <p className="text-[11px] font-mono text-slate-400 dark:text-slate-500 text-center">
          Set <code className="bg-slate-100 dark:bg-slate-800 px-1 rounded">NEXT_PUBLIC_GOOGLE_CLIENT_ID</code> to enable Google sign-in.
        </p>
      )}
    </div>
  );
}

// Multi-color Google SVG logo
function GoogleLogo({ muted = false }) {
  if (muted) {
    return (
      <svg className="w-5 h-5 shrink-0 opacity-40" viewBox="0 0 24 24">
        <path fill="#888" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
        <path fill="#888" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
        <path fill="#888" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
        <path fill="#888" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
      </svg>
    );
  }
  return (
    <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
    </svg>
  );
}
