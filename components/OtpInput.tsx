
import React, { useState } from 'react';

interface OtpInputProps {
  employeeName: string;
  onVerify: (staffId: string) => void;
  onGoBack: () => void;
  error: string;
}

const OtpInput: React.FC<OtpInputProps> = ({ employeeName, onVerify, onGoBack, error }) => {
  const [staffId, setStaffId] = useState('');
  const [showStaffId, setShowStaffId] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (staffId) {
      onVerify(staffId);
    }
  };

  return (
    <div className="space-y-12 animate-fade-in max-w-sm mx-auto">
      <div className="text-center space-y-6">
        <div className="inline-flex items-center justify-center p-6 bg-indigo-500/10 text-indigo-400 rounded-[2.5rem] mb-2 border border-indigo-500/20 shadow-[0_0_80px_rgba(99,102,241,0.15)] group hover:scale-110 transition-transform duration-700">
          <div className="absolute inset-0 bg-indigo-500/10 blur-2xl rounded-full scale-150 animate-pulse"></div>
          <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 relative z-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>
        <h2 className="text-4xl font-black text-white font-heading leading-tight uppercase tracking-tighter drop-shadow-lg">Identity Check</h2>
        <div className="px-6 py-4 bg-white/5 rounded-3xl border border-white/10 backdrop-blur-xl inline-block shadow-[0_20px_50px_rgba(0,0,0,0.3)] border-t-white/20">
          <p className="text-slate-500 text-[10px] font-black uppercase tracking-[0.3em] mb-1.5 opacity-60">Verifying profile for</p>
          <p className="text-white font-black text-2xl italic tracking-tight brand-gradient bg-clip-text text-transparent">{employeeName}</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-8">
        <div className="space-y-4">
          <div className="flex items-center justify-between ml-1">
             <label htmlFor="staff-id-input" className="block text-[11px] font-black text-slate-500 uppercase tracking-[0.4em]">
                Access Key
             </label>
             <span className="text-[9px] font-black text-indigo-400/60 uppercase tracking-widest bg-indigo-500/5 px-3 py-1 rounded-full border border-indigo-500/10">Staff ID Required</span>
          </div>
          
          <div className="relative group">
            <div className="absolute inset-y-0 left-0 pl-6 flex items-center pointer-events-none text-slate-600 group-focus-within:text-indigo-400 transition-colors duration-500">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
              </svg>
            </div>
            <input
              id="staff-id-input"
              type={showStaffId ? 'text' : 'password'}
              value={staffId}
              onChange={(e) => setStaffId(e.target.value)}
              className="block w-full pl-16 pr-14 py-6 bg-white/5 border-2 border-white/5 rounded-[2rem] text-white font-black text-lg placeholder-white/5 focus:outline-none focus:ring-0 focus:border-indigo-500/30 transition-all shadow-[0_20px_50px_rgba(0,0,0,0.2)] hover:bg-white/[0.08]"
              placeholder="••••••••"
              autoFocus
            />
            <button
              type="button"
              onClick={() => setShowStaffId(!showStaffId)}
              className="absolute inset-y-0 right-0 pr-6 flex items-center text-slate-600 hover:text-indigo-400 transition-colors duration-300"
            >
              {showStaffId ? (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
              )}
            </button>
          </div>
        </div>

        {error && (
          <div className="p-6 bg-rose-500/10 border border-emerald-500/20 rounded-[2rem] flex items-center space-x-4 animate-shake shadow-[0_15px_40px_rgba(244,63,94,0.15)]">
            <div className="w-10 h-10 bg-rose-500/20 rounded-2xl flex items-center justify-center shrink-0">
               <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-rose-400" viewBox="0 0 20 20" fill="currentColor">
                 <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
               </svg>
            </div>
            <p className="text-[11px] text-rose-300 font-black uppercase tracking-widest leading-tight">{error}</p>
          </div>
        )}

        <div className="flex flex-col space-y-5">
            <button
                type="submit"
                disabled={!staffId}
                className="w-full relative py-7 px-10 rounded-[2.5rem] text-white font-black text-xl overflow-hidden transition-all duration-700 hover:scale-[1.03] active:scale-[0.97] hover:shadow-[0_40px_100px_-20px_rgba(79,70,229,0.7)] disabled:scale-100 disabled:opacity-20 disabled:grayscale disabled:cursor-not-allowed group shadow-[0_30px_70px_-10px_rgba(79,70,229,0.5)]"
            >
                <div className="absolute inset-0 bg-gradient-to-r from-indigo-700 via-indigo-600 to-purple-700 group-hover:scale-125 transition-transform duration-1000"></div>
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_transparent_0%,_rgba(0,0,0,0.4)_100%)] opacity-30"></div>
                <div className="relative flex items-center justify-center space-x-5">
                    <span className="uppercase tracking-[0.4em] text-xs">Authorize Access</span>
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-7 w-7 group-hover:rotate-[360deg] transition-transform duration-1000 ease-in-out" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04c0 4.833 1.89 9.223 5.035 12.454a.434.434 0 00.612 0a11.955 11.955 0 005.035-12.454z" />
                    </svg>
                </div>
            </button>
            <button
                type="button"
                onClick={onGoBack}
                className="w-full py-5 rounded-[2rem] text-[10px] font-black text-slate-500 uppercase tracking-[0.5em] border-2 border-white/5 hover:border-white/10 hover:text-indigo-400 hover:bg-white/5 transition-all duration-500 bg-transparent shadow-[0_10px_30px_rgba(0,0,0,0.1)] active:scale-95"
            >
                ← Use a different profile
            </button>
        </div>
      </form>
    </div>
  );
};

export default OtpInput;
