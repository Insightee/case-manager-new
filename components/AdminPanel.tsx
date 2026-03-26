
import React, { useState, useEffect } from 'react';
import { getLast12Months } from '../utils/date';
import { supabase } from '../utils/supabase';

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
        // 1. Ensure employee exists (Indicators: employeeId, name)
        const { error: empError } = await supabase
            .from('employees')
            .upsert({
                employee_id: formData.employeeId,
                name: formData.name,
                email: `${formData.name.toLowerCase().replace(/\s+/g, '.')}@example.com`
            }, { onConflict: 'employee_id,name' });

        if (empError) throw empError;

        // 2. Add Payout
        const { error: payoutError } = await supabase
            .from('payouts')
            .insert({
                employee_id: formData.employeeId,
                name: formData.name,
                month: formData.month,
                year: parseInt(formData.year.toString()),
                gross_pay: parseFloat(formData.grossPay),
                tds: parseFloat(formData.tds),
                net_pay: parseFloat(formData.netPay),
                status: 'paid'
            });

        if (payoutError) throw payoutError;

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
        const { error } = await supabase
            .from('payouts')
            .delete()
            .match({
                employee_id: formData.employeeId,
                name: formData.name,
                month: formData.month,
                year: parseInt(formData.year.toString())
            });

        if (error) throw error;
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
      className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50 animate-fade-in-fast"
      onClick={handleClose}
    >
      <div 
        className="bg-white rounded-3xl shadow-2xl p-6 sm:p-8 w-full max-w-lg m-4 space-y-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center border-b pb-4">
            <h2 className="text-2xl font-black text-slate-800 font-heading tracking-tight">Data Control</h2>
            <button onClick={handleClose} className="p-2 hover:bg-slate-100 rounded-full text-slate-400 transition-colors">&times;</button>
        </div>
        
        {!isAuthenticated ? (
            <form onSubmit={handlePinSubmit} className="space-y-6">
                <p className="text-slate-500 font-medium">Secondary authentication required.</p>
                <input 
                    type="password" 
                    value={pin}
                    onChange={(e) => setPin(e.target.value)}
                    className="block w-full px-4 py-3 border border-slate-200 rounded-2xl focus:ring-4 focus:ring-indigo-100 focus:border-indigo-400 text-center text-3xl tracking-[1em] outline-none transition-all font-mono"
                    placeholder="••••"
                    maxLength={4}
                    autoFocus
                />
                {feedback.message && feedback.type === 'error' && (
                    <p className="text-sm text-rose-500 font-bold bg-rose-50 p-3 rounded-xl text-center">{feedback.message}</p>
                )}
                <button type="submit" className="w-full py-3.5 bg-slate-900 text-white rounded-2xl font-bold hover:bg-black transition-all active:scale-[0.98]">Confirm Access</button>
            </form>
        ) : (
            <div className="space-y-6">
                <p className="text-slate-500 text-sm font-medium leading-relaxed">
                    Modify payout history using **Employee ID** and **Name** as the secure primary indicators.
                </p>

                <form onSubmit={handleAdd} className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Employee ID</label>
                            <input name="employeeId" value={formData.employeeId} onChange={handleInputChange} className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:ring-4 focus:ring-indigo-100 outline-none text-sm font-bold" required />
                        </div>
                        <div>
                            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Employee Name</label>
                            <input name="name" value={formData.name} onChange={handleInputChange} className="w-full px-3 py-2 border border-slate-200 rounded-xl focus:ring-4 focus:ring-indigo-100 outline-none text-sm font-bold" required />
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Month</label>
                            <select name="month" value={formData.month} onChange={handleInputChange} className="w-full px-3 py-2 border border-slate-200 rounded-xl outline-none text-sm font-bold">
                                {['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'].map(m => <option key={m} value={m}>{m}</option>)}
                            </select>
                        </div>
                        <div>
                            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Year</label>
                            <select name="year" value={formData.year} onChange={handleInputChange} className="w-full px-3 py-2 border border-slate-200 rounded-xl outline-none text-sm font-bold">
                                {[2024, 2025, 2026].map(y => <option key={y} value={y}>{y}</option>)}
                            </select>
                        </div>
                    </div>

                    <div className="grid grid-cols-3 gap-3">
                        <div>
                            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Gross</label>
                            <input name="grossPay" type="number" value={formData.grossPay} onChange={handleInputChange} className="w-full px-3 py-2 border border-slate-200 rounded-xl text-sm font-bold" required />
                        </div>
                        <div>
                            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">TDS</label>
                            <input name="tds" type="number" value={formData.tds} onChange={handleInputChange} className="w-full px-3 py-2 border border-slate-200 rounded-xl text-sm font-bold" required />
                        </div>
                        <div>
                            <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Net</label>
                            <input name="netPay" type="number" value={formData.netPay} onChange={handleInputChange} className="w-full px-3 py-2 border border-slate-200 rounded-xl text-sm font-bold" required />
                        </div>
                    </div>

                    {feedback.message && (
                        <p className={`text-xs font-bold p-3 rounded-xl text-center ${feedback.type === 'success' ? 'bg-emerald-50 text-emerald-600' : 'bg-rose-50 text-rose-500'}`}>
                            {feedback.message}
                        </p>
                    )}

                    <div className="flex gap-3 pt-4 border-t">
                        <button
                            type="button"
                            onClick={handleDelete}
                            disabled={isProcessing}
                            className="flex-1 py-3 border border-rose-100 text-rose-500 rounded-2xl font-bold bg-white hover:bg-rose-50 disabled:opacity-50 transition-all text-xs uppercase tracking-widest"
                        >
                            Delete Record
                        </button>
                        <button
                            type="submit"
                            disabled={isProcessing}
                            className="flex-1 py-3 bg-indigo-600 text-white rounded-2xl font-bold hover:bg-indigo-700 disabled:bg-indigo-300 transition-all text-sm"
                        >
                            {isProcessing ? 'Processing...' : 'Add Record'}
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
