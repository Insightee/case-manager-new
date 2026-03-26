
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
        <div className="inline-flex items-center justify-center p-4 bg-indigo-50 text-indigo-600 rounded-full mb-2">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04c0 4.833 1.89 9.223 5.035 12.454a.434.434 0 00.612 0a11.955 11.955 0 005.035-12.454z" />
          </svg>
        </div>
        <h2 className="text-3xl font-bold text-slate-900 font-heading leading-tight">Identity Check</h2>
        <div className="p-3 bg-white rounded-2xl border border-slate-100 shadow-sm inline-block">
          <p className="text-slate-500 text-sm font-medium">Verifying profile for</p>
          <p className="text-indigo-600 font-bold text-lg">{employeeName}</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="space-y-2">
          <label htmlFor="staff-id-input" className="block text-sm font-semibold text-slate-700 ml-1">
            Access Key (Staff ID)
          </label>
          <div className="relative group">
            <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-slate-400 group-focus-within:text-indigo-500 transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
              </svg>
            </div>
            <input
              id="staff-id-input"
              type="password"
              value={staffId}
              onChange={(e) => setStaffId(e.target.value)}
              className="block w-full pl-12 pr-4 py-4 bg-slate-50 border border-slate-200 rounded-2xl text-slate-900 font-medium placeholder-slate-400 focus:outline-none focus:ring-4 focus:ring-indigo-100 focus:border-indigo-500 transition-all"
              placeholder="••••••••"
              autoFocus
            />
          </div>
        </div>

        {error && (
          <div className="p-4 bg-rose-50 border border-rose-100 rounded-2xl flex items-center space-x-3 animate-fade-in">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-rose-500 shrink-0" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            <p className="text-sm text-rose-700 font-medium leading-tight">{error}</p>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
            <button
                type="button"
                onClick={onGoBack}
                className="py-4 px-6 rounded-2xl font-bold text-slate-600 bg-white border border-slate-200 shadow-sm hover:bg-slate-50 active:scale-95 transition-all outline-none focus:ring-4 focus:ring-slate-100"
            >
                Change
            </button>
            <button
                type="submit"
                disabled={!staffId}
                className="btn-gradient py-4 px-6 rounded-2xl text-white font-bold shadow-lg shadow-indigo-100 disabled:opacity-50 disabled:cursor-not-allowed transform transition-all active:scale-95 flex items-center justify-center space-x-2"
            >
                <span>Authorize</span>
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
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
