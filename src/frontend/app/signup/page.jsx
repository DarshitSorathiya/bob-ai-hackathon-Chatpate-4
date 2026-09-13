'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { User, Mail, Lock, CheckCircle2 } from 'lucide-react';
import AuthLayout from '../../components/AuthLayout';
import Input from '../../components/Input';
import Button from '../../components/Button';
import GoogleButton from '../../components/GoogleButton';

export default function SignupPage() {
  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    password: '',
    confirmPassword: '',
  });

  const [errors, setErrors] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: '' }));
  };

  const validate = () => {
    const newErrors = {};

    if (!formData.fullName.trim()) {
      newErrors.fullName = 'Full name is required';
    } else if (formData.fullName.trim().length < 2) {
      newErrors.fullName = 'Name must be at least 2 characters';
    }

    if (!formData.email.trim()) {
      newErrors.email = 'Email address is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Enter a valid email address';
    }

    if (!formData.password) {
      newErrors.password = 'Password is required';
    } else if (formData.password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters long';
    }

    if (!formData.confirmPassword) {
      newErrors.confirmPassword = 'Please confirm your password';
    } else if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
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
      setIsSuccess(true);
    }, 1200);
  };

  return (
    <AuthLayout
      title="Create Account"
      subtitle="Predict the failure. Protect the mission."
    >
      {isSuccess ? (
        <div className="space-y-4 text-center py-4">
          <div className="w-12 h-12 bg-emerald-500/20 border border-emerald-500/40 rounded-full flex items-center justify-center text-emerald-400 mx-auto">
            <CheckCircle2 className="w-7 h-7" />
          </div>
          <h2 className="text-lg font-bold text-slate-100 font-sans">Account Provisioned</h2>
          <p className="text-xs text-slate-300 font-mono">
            Account created for <strong>{formData.fullName}</strong> ({formData.email}).
          </p>
          <div className="pt-2">
            <Link href="/login">
              <Button variant="primary">Proceed to Sign In</Button>
            </Link>
          </div>
        </div>
      ) : (
        <>
          <form onSubmit={handleSubmit} className="space-y-3.5" noValidate>
            <Input
              id="signup-fullname"
              name="fullName"
              label="Name"
              type="text"
              placeholder="Tulsi Dhameliya"
              value={formData.fullName}
              onChange={handleChange}
              error={errors.fullName}
              required
              autoComplete="name"
              icon={User}
            />

            <Input
              id="signup-email"
              name="email"
              label="Email"
              type="email"
              placeholder="operator@missionready.io"
              value={formData.email}
              onChange={handleChange}
              error={errors.email}
              required
              autoComplete="email"
              icon={Mail}
            />

            <Input
              id="signup-password"
              name="password"
              label="Password"
              type="password"
              placeholder="Minimum 8 characters"
              value={formData.password}
              onChange={handleChange}
              error={errors.password}
              required
              autoComplete="new-password"
              icon={Lock}
            />

            <Input
              id="signup-confirm-password"
              name="confirmPassword"
              label="Confirm Password"
              type="password"
              placeholder="Re-enter password"
              value={formData.confirmPassword}
              onChange={handleChange}
              error={errors.confirmPassword}
              required
              autoComplete="new-password"
              icon={Lock}
            />

            <div className="pt-2">
              <Button type="submit" isLoading={isLoading}>
                Create Account
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

          {/* Back to Login link */}
          <div className="mt-5 text-center text-xs text-slate-400 font-sans">
            Already have an account?{' '}
            <Link
              href="/login"
              className="font-semibold text-blue-400 hover:text-blue-300 underline underline-offset-4 transition-colors font-mono"
            >
              Sign in
            </Link>
          </div>
        </>
      )}
    </AuthLayout>
  );
}
