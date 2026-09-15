'use client';

import React, { useEffect, useRef, useState } from 'react';
import { loginWithGoogle, saveSession } from '../lib/api';

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '';
console.log(GOOGLE_CLIENT_ID);

/**
 * GoogleButton — renders a real Google Sign-In button using the Google Identity
 * Services (GIS) library when NEXT_PUBLIC_GOOGLE_CLIENT_ID is configured.
 *
 * When not configured:
 *   - Shows a disabled button with a clear "not available" tooltip.
 *   - No OAuth flow is attempted.
 *
 * Props:
 *   onSuccess(authResponse) — called after successful login + saveSession
 *   onError(message)        — called on failure (optional)
 *   label                   — button text (default: "Continue with Google")
 */
export default function GoogleButton({
  onSuccess,
  onError,
  label = 'Continue with Google',
}) {
  const buttonRef = useRef(null);
  const [status, setStatus] = useState('idle'); // idle | loading | error | unconfigured
  const [errorMsg, setErrorMsg] = useState('');

  const isConfigured = Boolean(GOOGLE_CLIENT_ID);

  useEffect(() => {
    if (!isConfigured) {
      setStatus('unconfigured');
      return;
    }

    // Load the GIS script once
    const scriptId = 'google-gsi-script';
    if (!document.getElementById(scriptId)) {
      const script = document.createElement('script');
      script.id = scriptId;
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.defer = true;
      document.head.appendChild(script);
    }

    const tryRender = () => {
      if (!window.google?.accounts?.id || !buttonRef.current) return;

      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: handleCredentialResponse,
        auto_select: false,
        cancel_on_tap_outside: true,
      });

      window.google.accounts.id.renderButton(buttonRef.current, {
        type: 'standard',
        shape: 'rectangular',
        theme: 'outline',
        size: 'large',
        text: 'continue_with',
        logo_alignment: 'left',
        width: buttonRef.current.offsetWidth || 360,
      });

      setStatus('idle');
    };

    // Poll until the GIS library is available
    const interval = setInterval(() => {
      if (window.google?.accounts?.id) {
        clearInterval(interval);
        tryRender();
      }
    }, 100);

    return () => clearInterval(interval);
  }, [isConfigured]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleCredentialResponse = async (response) => {
    setStatus('loading');
    setErrorMsg('');
    try {
      const authResponse = await loginWithGoogle(response.credential);
      saveSession(authResponse);
      setStatus('idle');
      if (onSuccess) onSuccess(authResponse);
    } catch (err) {
      const msg = err.message?.includes('not configured')
        ? 'Google Sign-In is not enabled on this server.'
        : (err.message || 'Google authentication failed.');
      setErrorMsg(msg);
      setStatus('error');
      if (onError) onError(msg);
    }
  };

  // ── Not configured ─────────────────────────────────────────────────────────
  if (!isConfigured) {
    return (
      <div className="w-full space-y-1.5">
        <button
          type="button"
          disabled
          title="Google OAuth is not configured on this server"
          className="w-full flex items-center justify-center gap-3 bg-slate-900/40 border border-slate-800 text-slate-600 font-mono text-xs py-2.5 px-4 rounded-lg cursor-not-allowed select-none"
        >
          <GoogleLogo muted />
          <span>{label}</span>
        </button>
        <p className="text-[11px] font-mono text-slate-600 text-center">
          Google Sign-In not available — <code className="text-slate-500">GOOGLE_CLIENT_ID</code> not set
        </p>
      </div>
    );
  }

  // ── Configured — GIS renders its own button into buttonRef ─────────────────
  return (
    <div className="w-full space-y-2">
      {/* GIS renders the real Google button into this div */}
      <div ref={buttonRef} className="w-full flex justify-center min-h-[44px]" />

      {status === 'loading' && (
        <p className="text-[11px] font-mono text-slate-400 text-center animate-pulse">
          Verifying with Google…
        </p>
      )}

      {status === 'error' && errorMsg && (
        <p className="text-[11px] font-mono text-red-400 text-center bg-red-950/30 border border-red-800/30 px-3 py-1.5 rounded-md">
          {errorMsg}
        </p>
      )}
    </div>
  );
}

// Simple inline Google logo SVG
function GoogleLogo({ muted = false }) {
  const fill = muted ? '#4b5563' : undefined;
  return (
    <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
      <path fill={fill || '#4285F4'} d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
      <path fill={fill || '#34A853'} d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
      <path fill={fill || '#FBBC05'} d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
      <path fill={fill || '#EA4335'} d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
    </svg>
  );
}
