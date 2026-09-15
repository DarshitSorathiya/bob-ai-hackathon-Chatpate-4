'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { User, Mail, Lock } from 'lucide-react';
import AuthLayout from '../../components/AuthLayout';
import Input from '../../components/Input';
import Button from '../../components/Button';
import GoogleButton from '../../components/GoogleButton';
import { registerUser, saveSession } from '../../lib/api';

export default function SignupPage() {
  const router = useRouter();

  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    password: '',
    confirmPassword: '',
  });

  const [errors, setErrors] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [authError, setAuthError] = useState('');

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) setErrors((prev) => ({ ...prev, [name]: '' }));
    if (authError) setAuthError('');
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
      newErrors.password = 'Password must be at least 8 characters';
    }

    if (!formData.confirmPassword) {
      newErrors.confirmPassword = 'Please confirm your password';
    } else if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;

    setIsLoading(true);
    setAuthError('');

    try {
      const response = await registerUser(formData);
      saveSession(response);
      router.push('/dashboard');
    } catch (error) {
      setAuthError(error.message || 'Registration failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthLayout title="Create Account" subtitle="Predict the failure. Protect the mission.">
      {authError && (
        <p className="mb-4 rounded-lg border border-red-800/80 bg-red-950/70 p-3 text-xs text-red-200">
          {authError}
        </p>
      )}

      <form onSubmit={handleSubmit} className="space-y-3.5" noValidate>
        <Input
          id="signup-fullname"
          name="fullName"
          label="Full Name"
          type="text"
          placeholder="Jane Smith"
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

      <GoogleButton label="Continue with Google" />

      <div className="mt-5 text-center text-xs text-slate-400 font-sans">
        Already have an account?{' '}
        <Link
          href="/login"
          className="font-semibold text-blue-400 hover:text-blue-300 underline underline-offset-4 transition-colors font-mono"
        >
          Sign in
        </Link>
      </div>
    </AuthLayout>
  );
}
