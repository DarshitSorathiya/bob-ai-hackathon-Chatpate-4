'use client';

import React from 'react';

export default function Button({
  children,
  type = 'button',
  variant = 'primary',
  fullWidth = true,
  isLoading = false,
  disabled = false,
  onClick,
  className = '',
}) {
  const baseStyles = 'inline-flex items-center justify-center font-mono font-semibold rounded-xl text-sm px-4 py-3 transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#f4f6ee] disabled:opacity-50 disabled:cursor-not-allowed';

  const variants = {
    primary: 'bg-[#1e4d35] hover:bg-[#163a26] text-white shadow-lg shadow-[#1e4d35]/20 focus:ring-[#1e4d35] active:bg-[#122018]',
    secondary: 'bg-[#e1eadf] hover:bg-[#c3d6c1] text-[#122018] border border-[#1e4d35]/20 focus:ring-[#1e4d35]',
    outline: 'bg-transparent border border-[#1e4d35]/30 text-[#1e4d35] hover:bg-[#1e4d35] hover:text-white focus:ring-[#1e4d35]',
  };

  return (
    <button
      type={type}
      disabled={disabled || isLoading}
      onClick={onClick}
      className={`
        ${baseStyles}
        ${variants[variant] || variants.primary}
        ${fullWidth ? 'w-full' : ''}
        ${className}
      `}
    >
      {isLoading ? (
        <span className="flex items-center gap-2">
          <svg className="animate-spin h-4 w-4 text-current" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          Authenticating...
        </span>
      ) : (
        children
      )}
    </button>
  );
}
