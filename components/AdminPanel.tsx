
import React, { useState, useEffect } from 'react';
import { getLast12Months } from '../utils/date';

interface AdminPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

const AdminPanel: React.FC<AdminPanelProps> = ({ isOpen, onClose }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [pin, setPin] = useState('');
  const [formData, setFormData] = useState({
      employeeId: '',
      name: '',
      month: getLast12Months()[0].month,
      year: getLast12Months()[0].year,
      grossPay: '',
      tds: '',
      netPay: ''
  });
  const [feedback, setFeedback] = useState({ type: '', message: '' });
  const [isProcessing, setIsProcessing] = useState(false);

  const handlePinSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (pin === '2205') {
      setIsAuthenticated(true);
      setFeedback({ type: '', message: '' });
    } else {
      setFeedback({ type: 'error', message: 'Incorrect PIN.' });
      setPin('');
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      const { name, value } = e.target;
      setFormData(prev => ({ ...prev, [name]: value }));
  }

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsProcessing(true);
    setFeedback({ type: '', message: '' });

    try {
        const response = await fetch('/api/admin/payout', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Sync-Secret': 'insighte_payout_portal_secret_2026'
          },
          body: JSON.stringify({
            action: 'upsert',
            employeeId: formData.employeeId,
            name: formData.name,
            month: formData.month,
            year: formData.year,
            grossPay: formData.grossPay,
            tds: formData.tds,
            netPay: formData.netPay
          })
        });

        if (!response.ok) {
          const resErr = await response.json();
          throw new Error(resErr.error || 'Server request failed');
        }

        setFeedback({ type: 'success', message: 'Payout record added successfully.' });
        setFormData(prev => ({ ...prev, grossPay: '', tds: '', netPay: '' }));
    } catch (error: any) {
        setFeedback({ type: 'error', message: error.message || 'Operation failed.' });
    } finally {
        setIsProcessing(false);
    }
  };

  const handleDelete = async () => {
    if (!formData.employeeId || !formData.name) {
        setFeedback({ type: 'error', message: 'Employee ID and Name are required for deletion.' });
        return;
    }
    
    if (!window.confirm(`Delete ${formData.month} record for ${formData.name}?`)) return;

    setIsProcessing(true);
    setFeedback({ type: '', message: '' });

    try {
        const response = await fetch('/api/admin/payout', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Sync-Secret': 'insighte_payout_portal_secret_2026'
          },
          body: JSON.stringify({
            action: 'delete',
            employeeId: formData.employeeId,
            name: formData.name,
            month: formData.month,
            year: formData.year
          })
        });

        if (!response.ok) {
          const resErr = await response.json();
          throw new Error(resErr.error || 'Server request failed');
        }

        setFeedback({ type: 'success', message: 'Record deleted successfully.' });
    } catch (error: any) {
        setFeedback({ type: 'error', message: error.message || 'Delete operation failed.' });
    } finally {
        setIsProcessing(false);
    }
  };


  const handleClose = () => {
      setIsAuthenticated(false);
      setPin('');
      setFeedback({ type: '', message: '' });
      onClose();
  }

  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 bg-black/80 backdrop-blur-sm flex justify-center items-center z-50 animate-fade-in-fast p-4"
      onClick={handleClose}
    >
      <div 
        className="bg-slate-900/60 backdrop-blur-2xl border border-white/10 rounded-[2.5rem] shadow-[0_30px_100px_rgba(0,0,0,0.5)] p-6 sm:p-10 w-full max-w-xl space-y-8 relative overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-indigo-500 to-transparent opacity-50"></div>
        
        <div className="flex justify-between items-center">
            <div className="flex items-center space-x-4">
              <div className="p-2.5 bg-indigo-500/20 rounded-xl border border-indigo-500/30">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </div>
              <div>
                <h2 className="text-2xl font-black text-white font-heading tracking-tight leading-tight uppercase">Admin Override</h2>
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em] mt-1">Institutional Data Control</p>
              </div>
            </div>
            <button 
              onClick={handleClose} 
              className="p-3 bg-white/5 hover:bg-white/10 rounded-2xl text-slate-400 hover:text-white transition-all border border-white/5 active:scale-90"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
        </div>
        
        {!isAuthenticated ? (
            <form onSubmit={handlePinSubmit} className="space-y-8 py-4">
                <div className="text-center space-y-2">
                  <p className="text-indigo-200/60 font-black text-[10px] uppercase tracking-[0.3em]">Access Verification</p>
                  <p className="text-slate-400 text-xs font-bold leading-relaxed uppercase tracking-widest px-8">Confirm secondary encrypted credentials to authorize administrative modifications.</p>
                </div>
                
                <div className="relative group">
                  <input 
                      type="password" 
                      value={pin}
                      onChange={(e) => setPin(e.target.value)}
                      className="block w-full px-6 py-6 bg-white/5 border border-white/10 rounded-3xl focus:ring-4 focus:ring-indigo-500/20 focus:border-indigo-500/50 text-center text-4xl tracking-[1em] outline-none transition-all font-mono text-white placeholder-white/5"
                      placeholder="••••"
                      maxLength={4}
                      autoFocus
                  />
                  <div className="absolute inset-0 bg-indigo-500/10 blur-2xl opacity-0 group-focus-within:opacity-100 transition-opacity rounded-3xl -z-10"></div>
                </div>

                {feedback.message && feedback.type === 'error' && (
                    <div className="flex items-center space-x-3 text-sm text-rose-400 font-bold bg-rose-500/10 p-4 rounded-2xl border border-rose-500/20 animate-shake">
                       <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                         <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                       </svg>
                       <span>{feedback.message}</span>
                    </div>
                )}
                
                <button type="submit" className="w-full py-5 bg-gradient-to-r from-indigo-600 to-indigo-700 text-white rounded-2.5xl font-black hover:from-indigo-500 hover:to-indigo-600 transition-all active:scale-[0.98] shadow-[0_20px_50px_rgba(79,70,229,0.2)] border border-white/10 uppercase tracking-widest text-xs">Establish Session</button>
            </form>
        ) : (
            <div className="space-y-8">
                <div className="bg-white/5 p-5 rounded-2.5xl border border-white/5 flex items-start space-x-4">
                  <div className="p-2 bg-indigo-500/20 rounded-xl text-indigo-400">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                       <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                     </svg>
                  </div>
                  <p className="text-slate-400 text-[10px] font-bold leading-relaxed uppercase tracking-[0.15em]">
                    Synchronized modifications require <span className="text-white font-black">Employee ID</span> and <span className="text-white font-black">Name</span> as primary cryptographic keys for data routing.
                  </p>
                </div>

                <form onSubmit={handleAdd} className="space-y-6">
                    <div className="grid grid-cols-2 gap-6">
                        <div className="space-y-2">
                            <label className="block text-[10px] font-black text-slate-500 uppercase tracking-[0.25em] ml-1">Key Identifier</label>
                            <input name="employeeId" placeholder="Staff ID" value={formData.employeeId} onChange={handleInputChange} className="w-full px-5 py-3.5 bg-white/5 border border-white/10 rounded-2xl focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500/50 outline-none text-sm font-black text-white transition-all" required />
                        </div>
                        <div className="space-y-2">
                            <label className="block text-[10px] font-black text-slate-500 uppercase tracking-[0.25em] ml-1">Legal Name</label>
                            <input name="name" placeholder="Full Name" value={formData.name} onChange={handleInputChange} className="w-full px-5 py-3.5 bg-white/5 border border-white/10 rounded-2xl focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500/50 outline-none text-sm font-black text-white transition-all" required />
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-6">
                        <div className="space-y-2">
                            <label className="block text-[10px] font-black text-slate-500 uppercase tracking-[0.25em] ml-1">Cycle Month</label>
                            <select name="month" value={formData.month} onChange={handleInputChange} className="w-full px-5 py-3.5 bg-white/5 border border-white/10 rounded-2xl outline-none text-sm font-black text-white appearance-none cursor-pointer hover:bg-white/10 transition-all">
                                {['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'].map(m => <option key={m} value={m} className="bg-slate-900">{m}</option>)}
                            </select>
                        </div>
                        <div className="space-y-2">
                            <label className="block text-[10px] font-black text-slate-500 uppercase tracking-[0.25em] ml-1">Cycle Year</label>
                            <select name="year" value={formData.year} onChange={handleInputChange} className="w-full px-5 py-3.5 bg-white/5 border border-white/10 rounded-2xl outline-none text-sm font-black text-white appearance-none cursor-pointer hover:bg-white/10 transition-all">
                                {[2024, 2025, 2026].map(y => <option key={y} value={y} className="bg-slate-900">{y}</option>)}
                            </select>
                        </div>
                    </div>

                    <div className="grid grid-cols-3 gap-4">
                        <div className="space-y-2">
                            <label className="block text-[10px] font-black text-slate-500 uppercase tracking-[0.25em] ml-1">Gross</label>
                            <input name="grossPay" type="number" placeholder="0.00" value={formData.grossPay} onChange={handleInputChange} className="w-full px-4 py-3.5 bg-white/5 border border-white/10 rounded-2xl text-sm font-black text-white outline-none focus:border-indigo-500/50" required />
                        </div>
                        <div className="space-y-2">
                            <label className="block text-[10px] font-black text-slate-500 uppercase tracking-[0.25em] ml-1">TDS</label>
                            <input name="tds" type="number" placeholder="0.00" value={formData.tds} onChange={handleInputChange} className="w-full px-4 py-3.5 bg-white/5 border border-white/10 rounded-2xl text-sm font-black text-white outline-none focus:border-indigo-500/50" required />
                        </div>
                        <div className="space-y-2">
                            <label className="block text-[10px] font-black text-slate-500 uppercase tracking-[0.25em] ml-1">Net</label>
                            <input name="netPay" type="number" placeholder="0.00" value={formData.netPay} onChange={handleInputChange} className="w-full px-4 py-3.5 bg-white/5 border border-white/10 rounded-2xl text-sm font-black text-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.05)] outline-none focus:border-emerald-500/50" required />
                        </div>
                    </div>

                    {feedback.message && (
                        <div className={`flex items-center space-x-3 text-xs font-bold p-5 rounded-2.5xl border animate-fade-in ${feedback.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border-rose-500/20'}`}>
                           <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                             <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d={feedback.type === 'success' ? "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" : "M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"} />
                           </svg>
                           <span>{feedback.message}</span>
                        </div>
                    )}

                    <div className="flex flex-col sm:flex-row gap-4 pt-6 border-t border-white/5">
                        <button
                            type="button"
                            onClick={handleDelete}
                            disabled={isProcessing}
                            className="flex-1 py-4 border border-rose-500/20 text-rose-400 rounded-2.5xl font-black bg-rose-500/5 hover:bg-rose-500/10 disabled:opacity-50 transition-all text-[10px] uppercase tracking-[0.25em] shadow-lg shadow-rose-500/5"
                        >
                            Wipe Entry
                        </button>
                        <button
                            type="submit"
                            disabled={isProcessing}
                            className="flex-1 py-4 bg-gradient-to-r from-indigo-600 to-indigo-700 text-white rounded-2.5xl font-black hover:from-indigo-500 hover:to-indigo-600 disabled:opacity-50 transition-all text-[10px] uppercase tracking-[0.25em] shadow-lg shadow-indigo-600/10 border border-white/5"
                        >
                            {isProcessing ? 'Syncing...' : 'Append Record'}
                        </button>
                    </div>
                </form>
            </div>
        )}
      </div>
    </div>
  );
};

export default AdminPanel;
