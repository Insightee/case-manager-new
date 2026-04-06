
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

        <div className="flex flex-col space-y-4">
            <button
                type="submit"
                disabled={!staffId}
                className="w-full py-6 relative px-10 rounded-[2rem] text-white font-black text-lg overflow-hidden transition-all duration-500 hover:scale-[1.02] active:scale-[0.98] disabled:scale-100 disabled:opacity-30 disabled:grayscale group shadow-[0_20px_50px_-10px_rgba(99,102,241,0.5)]"
            >
                <div className="absolute inset-0 bg-gradient-to-r from-indigo-600 via-indigo-500 to-purple-600 group-hover:scale-110 transition-transform duration-700"></div>
                <div className="relative flex items-center justify-center space-x-4">
                    <span className="uppercase tracking-[0.3em] text-xs">Authorize Access</span>
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 group-hover:translate-x-1.5 transition-transform duration-500" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M2.166 4.999A11.954 11.954 0 0010 1.944a11.954 11.954 0 007.834 3.055.75.75 0 01.584.73 11.72 11.72 0 01-5.333 9.776c-.67.44-1.552.44-2.222 0A11.72 11.72 0 012.166 4.999zM10 9.75a2.25 2.25 0 100-4.5 2.25 2.25 0 000 4.5z" clipRule="evenodd" />
                    </svg>
                </div>
            </button>
            <button
                type="button"
                onClick={onGoBack}
                className="w-full py-4 text-[10px] font-black text-slate-500 uppercase tracking-[0.4em] hover:text-indigo-400 transition-colors duration-300"
            >
                ← Use a different profile
            </button>
        </div>
      </form>
    </div>
  );
};

export default OtpInput;
