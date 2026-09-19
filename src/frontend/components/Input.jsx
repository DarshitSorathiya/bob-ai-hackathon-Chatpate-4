'use client';

import React, { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

export default function Input({
  id,
  name,
  label,
  type = 'text',
  placeholder = '',
  value = '',
  onChange,
  error = '',
  required = false,
  autoComplete = 'off',
  icon: Icon = null,
}) {
  const [showPassword, setShowPassword] = useState(false);
  const isPasswordType = type === 'password';
  const inputType = isPasswordType ? (showPassword ? 'text' : 'password') : type;

  return (
    <div className="space-y-1">
      {label && (
        <label htmlFor={id} className="block text-[11px] font-mono font-semibold text-[#122018] dark:text-slate-300 uppercase tracking-wider">
          {label} {required && <span className="text-red-400">*</span>}
        </label>
      )}

      <div className="relative rounded-lg shadow-sm">
        {Icon && (
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
            <Icon className="h-4 w-4" />
          </div>
        )}

        <input
          id={id}
          name={name}
          type={inputType}
          placeholder={placeholder}
          value={value}
          onChange={onChange}
          required={required}
          autoComplete={autoComplete}
          aria-invalid={!!error}
          aria-describedby={error ? `${id}-error` : undefined}
          className={`
            block w-full rounded-lg border bg-[#f4f6ee] dark:bg-[#0d1b13] text-[#122018] dark:text-slate-100 placeholder-[#566b5c]/60 dark:placeholder-slate-400 text-sm py-2.5 transition-all font-sans
            focus:outline-none focus:ring-2 focus:ring-[#1e4d35] focus:bg-[#e1eadf] dark:focus:bg-[#122419] focus:border-transparent
            ${Icon ? 'pl-10' : 'pl-3.5'}
            ${isPasswordType ? 'pr-10' : 'pr-3.5'}
            ${error ? 'border-red-500/80 focus:ring-red-500' : 'border-[#1e4d35]/30 hover:border-[#1e4d35]/60'}
          `}
        />

        {isPasswordType && (
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-200 focus:outline-none"
            aria-label={showPassword ? 'Hide password' : 'Show password'}
          >
            {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        )}
      </div>

      {error && (
        <p id={`${id}-error`} className="text-xs text-red-400 font-medium flex items-center gap-1 pt-0.5">
          <span>⚠️</span> {error}
        </p>
      )}
    </div>
  );
}
