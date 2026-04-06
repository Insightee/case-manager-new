
import React, { useState } from 'react';

interface OtpInputProps {
  employeeName: string;
  onVerify: (staffId: string) => void;
  onGoBack: () => void;
  error: string;
}

const OtpInput: React.FC<OtpInputProps> = ({ employeeName, onVerify, onGoBack, error }) => {
  const [staffId, setStaffId] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (staffId) {
      onVerify(staffId);
    }
  };

  return (
    <div className="space-y-8 animate-fade-in max-w-sm mx-auto">
      <div className="text-center space-y-4">
        <div className="inline-flex items-center justify-center p-5 bg-indigo-500/10 text-indigo-400 rounded-[2rem] mb-2 border border-indigo-500/20 shadow-[0_0_50px_rgba(99,102,241,0.1)]">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04c0 4.833 1.89 9.223 5.035 12.454a.434.434 0 00.612 0a11.955 11.955 0 005.035-12.454z" />
          </svg>
        </div>
        <h2 className="text-3xl font-black text-white font-heading leading-tight uppercase tracking-tighter">Identity Check</h2>
        <div className="px-6 py-3 bg-white/5 rounded-2xl border border-white/10 backdrop-blur-md inline-block shadow-xl">
          <p className="text-indigo-200/50 text-[10px] font-black uppercase tracking-[0.2em] mb-1">Verifying profile for</p>
          <p className="text-white font-black text-xl italic tracking-tight">{employeeName}</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="space-y-3">
          <label htmlFor="staff-id-input" className="block text-[10px] font-black text-slate-500 uppercase tracking-[0.3em] ml-1">
            Access Key (Staff ID)
          </label>
          <div className="relative group">
            <div className="absolute inset-y-0 left-0 pl-5 flex items-center pointer-events-none text-slate-500 group-focus-within:text-indigo-400 transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
              </svg>
            </div>
            <input
              id="staff-id-input"
              type="password"
              value={staffId}
              onChange={(e) => setStaffId(e.target.value)}
              className="block w-full pl-14 pr-6 py-5 bg-white/5 border border-white/10 rounded-2.5xl text-white font-black placeholder-white/5 focus:outline-none focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500/50 transition-all shadow-2xl"
              placeholder="••••••••"
              autoFocus
            />
          </div>
        </div>

        {error && (
          <div className="p-5 bg-rose-500/10 border border-rose-500/20 rounded-2.5xl flex items-center space-x-4 animate-shake">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-rose-400 shrink-0" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            <p className="text-xs text-rose-300 font-bold leading-tight uppercase tracking-widest">{error}</p>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
            <button
                type="button"
                onClick={onGoBack}
                className="py-4.5 px-6 rounded-2.5xl font-black text-slate-400 bg-white/5 border border-white/10 hover:bg-white/10 active:scale-95 transition-all outline-none text-[10px] uppercase tracking-widest"
            >
                Change
            </button>
            <button
                type="submit"
                disabled={!staffId}
                className="py-4.5 px-6 rounded-2.5xl bg-gradient-to-r from-indigo-600 to-indigo-700 text-white font-black shadow-lg shadow-indigo-600/10 disabled:opacity-30 disabled:grayscale transform transition-all active:scale-95 flex items-center justify-center space-x-2 text-[10px] uppercase tracking-widest border border-white/5"
            >
                <span>Authorize</span>
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
                  <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
                </svg>
            </button>
        </div>
      </form>
    </div>
  );
};

export default OtpInput;
