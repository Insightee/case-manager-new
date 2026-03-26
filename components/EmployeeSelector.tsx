
import React, { useState, useMemo, useRef, useEffect } from 'react';
import { Employee } from '../types';

interface EmployeeSelectorProps {
  employees: Employee[];
  onSelect: (employeeId: string) => void;
}

const EmployeeSelector: React.FC<EmployeeSelectorProps> = ({ employees, onSelect }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedId, setSelectedId] = useState<string>('');
  const dropdownRef = useRef<HTMLDivElement>(null);

  const filteredEmployees = useMemo(() => {
    return employees
      .filter(emp => emp.name.toLowerCase().includes(searchQuery.toLowerCase()))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [employees, searchQuery]);

  const selectedEmployee = useMemo(() => {
    return employees.find(emp => emp.employeeId === selectedId);
  }, [employees, selectedId]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedId) {
      onSelect(selectedId);
    }
  };

  return (
    <div className="space-y-12 animate-fade-in max-w-lg mx-auto relative px-4 sm:px-0">
      <div className="text-center space-y-4">
        <div className="inline-flex items-center space-x-2 px-4 py-2 bg-indigo-50 text-indigo-700 rounded-full border border-indigo-100/50 shadow-sm animate-pulse mb-2">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
            <span className="text-[10px] uppercase tracking-[0.2em] font-black">Internal Portal Access</span>
        </div>
        <h2 className="text-6xl font-black text-slate-900 tracking-tighter font-heading leading-[0.9]">
          insighte <br/>
          <span className="brand-gradient">payout portal</span>
        </h2>
        <p className="text-slate-500 font-bold max-w-sm mx-auto text-sm leading-relaxed">
          select your profile and access your earnings details.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-10">
        <div className="space-y-6 relative" ref={dropdownRef}>
          <div className="flex justify-between items-center ml-2">
             <label className="text-[11px] font-black text-slate-400 uppercase tracking-[0.4em]">
                Select Profile
            </label>
            {selectedEmployee && (
                <span className="text-[10px] font-black text-emerald-600 uppercase tracking-widest bg-emerald-50 px-3 py-1 rounded-full border border-emerald-100">
                    ID Validated
                </span>
            )}
          </div>
          
          <div className="relative group">
            {/* Custom Dropdown Trigger */}
            <div 
              onClick={() => setIsOpen(!isOpen)}
              className={`w-full flex items-center justify-between pl-16 pr-10 py-7 glass-card rounded-[2.5rem] text-slate-900 font-bold cursor-pointer transition-all duration-700 border-2 ${isOpen ? 'border-indigo-400 ring-[12px] ring-indigo-500/5 shadow-[0_30px_70px_rgba(99,102,241,0.2)]' : 'border-slate-100 hover:border-indigo-200 shadow-[0_20px_50px_rgba(0,0,0,0.03)] hover:shadow-indigo-100/40'}`}
            >
              <div className="absolute inset-y-0 left-0 pl-6 flex items-center pointer-events-none">
                <div className={`w-12 h-12 rounded-2xl flex items-center justify-center transition-all duration-700 ${isOpen ? 'bg-indigo-600 text-white rotate-12 scale-110 shadow-lg' : 'bg-slate-100 text-slate-400'}`}>
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                    </svg>
                </div>
              </div>
              
              <div className="flex flex-col items-start leading-none gap-1.5 overflow-hidden pr-4">
                  <span className={`text-[11px] uppercase tracking-[0.3em] font-black transition-colors ${isOpen ? 'text-indigo-600' : 'text-slate-400'}`}>
                    {selectedEmployee ? 'Authenticated Profile' : 'Select Identity'}
                  </span>
                  <span className={`text-xl font-black tracking-tight truncate w-full ${selectedEmployee ? 'text-slate-900' : 'text-slate-300'}`}>
                    {selectedEmployee ? selectedEmployee.name : 'Find your name...'}
                  </span>
              </div>

              <div className={`transition-all duration-700 ${isOpen ? 'rotate-180 scale-125 text-indigo-600' : 'text-slate-300'}`}>
                <svg xmlns="http://www.w3.org/2000/svg" className="h-7 w-7" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M14.707 12.707a1 1 0 01-1.414 0L10 9.414l-3.293 3.293a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 010 1.414z" clipRule="evenodd" />
                </svg>
              </div>
            </div>

            {/* Dropdown Menu */}
            {isOpen && (
              <div className="absolute z-50 mt-6 w-full bg-white/98 backdrop-blur-3xl border border-indigo-100/50 rounded-[3.5rem] shadow-[0_50px_150px_-30px_rgba(99,102,241,0.3)] overflow-hidden animate-fade-in origin-top">
                <div className="p-6 border-b border-slate-100 bg-slate-50/50">
                   <div className="relative">
                      <input 
                        autoFocus
                        type="text"
                        placeholder="Find your name..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="w-full pl-14 pr-8 py-5 bg-white border-2 border-slate-100 rounded-[2rem] text-lg font-bold placeholder:text-slate-300 focus:border-indigo-500 focus:ring-0 transition-all outline-none shadow-sm"
                      />
                      <svg xmlns="http://www.w3.org/2000/svg" className="absolute left-6 top-1/2 -translate-y-1/2 h-6 w-6 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                      </svg>
                   </div>
                </div>
                
                <div className="max-h-[400px] overflow-y-auto overscroll-contain py-4 px-4 space-y-1.5">
                  {filteredEmployees.length > 0 ? (
                    filteredEmployees.map((emp) => (
                      <div
                        key={emp.employeeId}
                        onClick={() => {
                          setSelectedId(emp.employeeId);
                          setIsOpen(false);
                          setSearchQuery('');
                        }}
                        className={`group/item px-8 py-5 flex items-center justify-between cursor-pointer rounded-[2rem] transition-all duration-500 ${selectedId === emp.employeeId ? 'bg-indigo-600 text-white shadow-xl shadow-indigo-200 scale-[0.98]' : 'hover:bg-indigo-50 text-slate-700 hover:pl-10'}`}
                      >
                        <div className="flex flex-col">
                            <span className="font-black text-lg tracking-tight">{emp.name}</span>
                            <span className={`text-[10px] uppercase tracking-[0.3em] font-black ${selectedId === emp.employeeId ? 'text-indigo-200' : 'text-slate-400'}`}>
                                Verified Professional
                            </span>
                        </div>
                        {selectedId === emp.employeeId ? (
                           <div className="w-10 h-10 bg-white/20 rounded-2xl flex items-center justify-center animate-bounce-in">
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" viewBox="0 0 20 20" fill="currentColor">
                                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                </svg>
                           </div>
                        ) : (
                            <div className="w-8 h-8 rounded-xl bg-slate-50 flex items-center justify-center transition-all group-hover/item:bg-indigo-500 group-hover/item:text-white group-hover/item:rotate-90">
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M12 4v16m8-8H4" />
                                </svg>
                            </div>
                        )}
                      </div>
                    ))
                  ) : (
                    <div className="py-20 text-center flex flex-col items-center">
                      <div className="w-20 h-20 bg-slate-50 rounded-[2rem] flex items-center justify-center mb-6">
                         <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-slate-200" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                         </svg>
                      </div>
                      <p className="text-lg font-black text-slate-400 tracking-tight">Identity not found</p>
                      <p className="text-xs font-bold text-slate-300 uppercase tracking-widest mt-2">Check spelling or contact administration</p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        <button
          type="submit"
          disabled={!selectedId}
          className="w-full relative py-7 px-10 rounded-[2.5rem] text-white font-black text-xl overflow-hidden transition-all duration-500 hover:scale-[1.03] active:scale-[0.97] disabled:scale-100 disabled:opacity-40 disabled:grayscale disabled:cursor-not-allowed group shadow-[0_30px_80px_-20px_rgba(99,102,241,0.5)]"
        >
          <div className="absolute inset-0 bg-gradient-to-r from-indigo-700 via-indigo-600 to-purple-700 group-hover:scale-110 transition-transform duration-700"></div>
          <div className="relative flex items-center justify-center space-x-5">
              <span className="uppercase tracking-[0.3em] text-xs">Verify & Enter</span>
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 group-hover:translate-x-3 transition-transform duration-500" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
          </div>
        </button>
      </form>

      <div className="pt-12 text-center">
        <div className="flex flex-col items-center gap-4">
            <div className="flex items-center space-x-4 px-6 py-2.5 bg-slate-900 rounded-full border border-slate-800 shadow-2xl">
                <span className="flex h-2.5 w-2.5 relative">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-indigo-500"></span>
                </span>
                <p className="text-[10px] text-white font-black uppercase tracking-[0.3em]">
                    Pay Portal Status: Active
                </p>
            </div>
            <p className="text-[10px] text-slate-400 font-bold uppercase tracking-widest opacity-60">Verified End-to-End Encryption Environment</p>
        </div>
      </div>
    </div>

  );
};

export default EmployeeSelector;
