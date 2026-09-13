'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { Mail, Lock, AlertCircle } from 'lucide-react';
import AuthLayout from '../../components/AuthLayout';
import Input from '../../components/Input';
import Button from '../../components/Button';
import GoogleButton from '../../components/GoogleButton';

export default function LoginPage() {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });

  const [errors, setErrors] = useState({});
  const [authError, setAuthError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showForgotModal, setShowForgotModal] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotSuccess, setForgotSuccess] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: '' }));
    if (authError) setAuthError('');
  };

  const validate = () => {
    const newErrors = {};
    if (!formData.email.trim()) {
      newErrors.email = 'Email address is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Enter a valid operator email address';
    }

    if (!formData.password) {
      newErrors.password = 'Password is required';
    } else if (formData.password.length < 6) {
      newErrors.password = 'Password must be at least 6 characters';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!validate()) return;

    setIsLoading(true);

    setTimeout(() => {
      setIsLoading(false);
      if (formData.email.includes('error')) {
        setAuthError('Unauthorized clearance level or invalid credentials.');
      } else {
        alert(`Authentication Successful. Welcome Operator ${formData.email}!`);
      }
    }, 1200);
  };

  const handleForgotSubmit = (e) => {
    e.preventDefault();
    if (!forgotEmail || !/\S+@\S+\.\S+/.test(forgotEmail)) {
      alert('Please enter a valid operator email address.');
      return;
    }
    setForgotSuccess(true);
  };

  return (
    <AuthLayout
      title="Sign In"
      subtitle="Predict the failure. Protect the mission."
    >
      {authError && (
        <div className="mb-4 p-3 rounded-lg bg-red-950/70 border border-red-800/80 text-red-200 text-xs flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
          <span>{authError}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <Input
          id="login-email"
          name="email"
          label="Email Address"
          type="email"
          placeholder="operator@missionready.io"
          value={formData.email}
          onChange={handleChange}
          error={errors.email}
          required
          autoComplete="email"
          icon={Mail}
        />

        <div className="space-y-1">
          <Input
            id="login-password"
            name="password"
            label="Password"
            type="password"
            placeholder="••••••••••••"
            value={formData.password}
            onChange={handleChange}
            error={errors.password}
            required
            autoComplete="current-password"
            icon={Lock}
          />
          <div className="flex justify-end pt-1">
            <button
              type="button"
              onClick={() => {
                setForgotEmail(formData.email);
                setShowForgotModal(true);
                setForgotSuccess(false);
              }}
              className="text-xs font-mono text-blue-400 hover:text-blue-300 transition-colors focus:outline-none focus:underline"
            >
              Forgot password?
            </button>
          </div>
        </div>

        <div className="pt-2">
          <Button type="submit" isLoading={isLoading}>
            Sign In
          </Button>
        </div>
      </form>

      {/* Divider */}
      <div className="relative my-5">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-slate-800" />
        </div>
        <div className="relative flex justify-center text-[10px] uppercase font-mono">
          <span className="bg-[#0d121f] px-2 text-slate-500">Or continue with</span>
        </div>
      </div>

      {/* Google Sign-in */}
      <GoogleButton label="Continue with Google" />

      {/* Sign up link */}
      <div className="mt-6 text-center text-xs text-slate-400 font-sans">
        Don&apos;t have an account?{' '}
        <Link
          href="/signup"
          className="font-semibold text-blue-400 hover:text-blue-300 underline underline-offset-4 transition-colors font-mono"
        >
          Create account
        </Link>
      </div>

      {/* Forgot Password Modal */}
      {showForgotModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/85 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0d121f] border border-slate-800 p-6 rounded-2xl max-w-sm w-full space-y-4 shadow-2xl relative">
            <h2 className="text-lg font-bold text-slate-100 font-sans">Reset Password</h2>
            {forgotSuccess ? (
              <div className="space-y-3 font-mono text-xs">
                <p className="text-emerald-400 bg-emerald-950/50 border border-emerald-800/50 p-3 rounded-lg">
                  ✅ Reset link dispatched to <strong>{forgotEmail}</strong>.
                </p>
                <Button variant="secondary" onClick={() => setShowForgotModal(false)}>
                  Close
                </Button>
              </div>
            ) : (
              <form onSubmit={handleForgotSubmit} className="space-y-3">
                <p className="text-xs text-slate-400">
                  Enter your registered email address to receive a password reset link.
                </p>
                <Input
                  id="forgot-email-input"
                  name="forgotEmail"
                  label="Email Address"
                  type="email"
                  placeholder="operator@missionready.io"
                  value={forgotEmail}
                  onChange={(e) => setForgotEmail(e.target.value)}
                  required
                  icon={Mail}
                />
                <div className="flex gap-2 pt-2">
                  <Button type="button" variant="secondary" onClick={() => setShowForgotModal(false)}>
                    Cancel
                  </Button>
                  <Button type="submit">
                    Send Reset Link
                  </Button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </AuthLayout>
  );
}
