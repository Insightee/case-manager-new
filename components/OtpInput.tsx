
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
    <div className="space-y-6 animate-fade-in">
      <h2 className="text-2xl font-semibold text-center text-slate-700">Verify Your Identity</h2>
      <p className="text-center text-slate-500">
        Welcome, <span className="font-medium text-slate-600">{employeeName}</span>. 
        Please enter your Staff / Consultant ID to continue.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="staff-id-input" className="block text-sm font-medium text-slate-600 mb-1">
            Staff / Consultant ID
          </label>
          <input
            id="staff-id-input"
            type="text"
            value={staffId}
            onChange={(e) => setStaffId(e.target.value)}
            className="block w-full px-4 py-3 bg-white text-slate-800 border border-slate-300 rounded-md shadow-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500 sm:text-sm"
            placeholder="Enter your Staff / Consultant ID"
            autoFocus
          />
        </div>
        {error && <p className="text-sm text-red-600 text-center">{error}</p>}
        <div className="flex flex-col sm:flex-row gap-3">
            <button
                type="button"
                onClick={onGoBack}
                className="w-full flex justify-center py-2 px-4 border border-slate-300 rounded-md shadow-sm text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 transition-colors"
            >
                Back
            </button>
            <button
                type="submit"
                disabled={!staffId}
                className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 disabled:bg-purple-300 disabled:cursor-not-allowed transition-colors"
            >
                Verify & View
            </button>
        </div>
      </form>
    </div>
  );
};

export default OtpInput;
