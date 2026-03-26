
import React, { useState } from 'react';
import { getLast12Months } from '../utils/date';

interface AdminPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

const AdminPanel: React.FC<AdminPanelProps> = ({ isOpen, onClose }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [pin, setPin] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [feedback, setFeedback] = useState('');
  const [selectedMonth, setSelectedMonth] = useState(getLast12Months()[0].value);

  const handlePinSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (pin === '2205') {
      setIsAuthenticated(true);
      setFeedback('');
    } else {
      setFeedback('Incorrect PIN.');
      setPin('');
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFile(e.target.files[0]);
      setFeedback('');
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (file) {
      setFeedback(`Successfully uploaded "${file.name}" for ${selectedMonth}. Data processing started.`);
      // Mock processing
      setTimeout(() => {
        setFile(null);
      }, 2000);
    } else {
      setFeedback('Please select a file to submit.');
    }
  };

  const handleClose = () => {
      setIsAuthenticated(false);
      setPin('');
      setFeedback('');
      setFile(null);
      onClose();
  }

  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50 animate-fade-in-fast"
      onClick={handleClose}
    >
      <div 
        className="bg-white rounded-lg shadow-xl p-6 sm:p-8 w-full max-w-md m-4 space-y-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center border-b pb-3">
            <h2 className="text-2xl font-semibold text-slate-800">Admin Settings</h2>
            <button onClick={handleClose} className="text-slate-500 hover:text-slate-800">&times;</button>
        </div>
        
        {!isAuthenticated ? (
            <form onSubmit={handlePinSubmit} className="space-y-4">
                <p className="text-slate-600">Enter Admin PIN to continue.</p>
                <input 
                    type="password" 
                    value={pin}
                    onChange={(e) => setPin(e.target.value)}
                    className="block w-full px-4 py-2 border border-slate-300 rounded-md focus:ring-purple-500 focus:border-purple-500 text-center text-2xl tracking-widest"
                    placeholder="••••"
                    maxLength={4}
                    autoFocus
                />
                {feedback && <p className="text-sm text-red-500 text-center">{feedback}</p>}
                <button type="submit" className="w-full py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700">Login</button>
            </form>
        ) : (
            <>
                <p className="text-slate-600 text-sm">
                Upload monthly payslip data. Supported formats: PDF (auto-OCR) or Excel/CSV.
                </p>

                <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                    <label className="block text-sm font-medium text-slate-600 mb-1">Select Period</label>
                    <select 
                        value={selectedMonth} 
                        onChange={(e) => setSelectedMonth(e.target.value)}
                        className="block w-full px-3 py-2 border border-slate-300 rounded-md shadow-sm focus:ring-purple-500 focus:border-purple-500 sm:text-sm"
                    >
                        {getLast12Months().map(m => (
                            <option key={m.value} value={m.value}>{m.label}</option>
                        ))}
                    </select>
                </div>

                <div>
                    <label htmlFor="file-upload" className="block text-sm font-medium text-slate-600 mb-2">
                    Select File
                    </label>
                    <div className="mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-slate-300 border-dashed rounded-md hover:bg-slate-50 transition-colors">
                    <div className="space-y-1 text-center">
                        <svg className="mx-auto h-12 w-12 text-slate-400" stroke="currentColor" fill="none" viewBox="0 0 48 48" aria-hidden="true">
                        <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                        <div className="flex text-sm text-slate-600">
                        <label htmlFor="file-upload" className="relative cursor-pointer bg-white rounded-md font-medium text-purple-600 hover:text-purple-500 focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-purple-500">
                            <span>Upload a file</span>
                            <input id="file-upload" name="file-upload" type="file" className="sr-only" onChange={handleFileChange} accept=".csv, .xlsx, .xls, .pdf" />
                        </label>
                        <p className="pl-1">or drag and drop</p>
                        </div>
                        <p className="text-xs text-slate-500">
                        PDF, Excel, CSV up to 10MB
                        </p>
                    </div>
                    </div>
                    {file && (
                        <div className="mt-2 p-2 bg-blue-50 text-blue-700 text-sm rounded border border-blue-100 flex items-center gap-2">
                             <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                            </svg>
                            Ready to process: {file.name}
                        </div>
                    )}
                </div>
                
                {feedback && <p className="text-sm text-green-600 text-center">{feedback}</p>}

                <div className="flex justify-end gap-3 pt-4">
                    <button
                        type="button"
                        onClick={handleClose}
                        className="py-2 px-4 border border-slate-300 rounded-md shadow-sm text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 transition-colors"
                    >
                        Cancel
                    </button>
                    <button
                        type="submit"
                        className="py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 disabled:bg-purple-300"
                    >
                        Upload & Process
                    </button>
                </div>
                </form>
            </>
        )}
      </div>
    </div>
  );
};

export default AdminPanel;
