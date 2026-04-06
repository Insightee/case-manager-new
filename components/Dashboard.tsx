
import React, { useMemo } from 'react';
import { Employee, PayslipRecord } from '../types';
import { getMonthNumber } from '../utils/date';
import { insighteLogo } from '../assets/logo';

interface DashboardProps {
  employee: Employee;
  records: PayslipRecord[];
  onViewPayslip: (record: PayslipRecord) => void;
  onLogout: () => void;
}

const Dashboard: React.FC<DashboardProps> = ({ employee, records, onViewPayslip, onLogout }) => {
  const stats = useMemo(() => {
    return records.reduce((acc, curr) => ({
      gross: acc.gross + curr.grossPay,
      tds: acc.tds + curr.tds,
      net: acc.net + curr.netPay
    }), { gross: 0, tds: 0, net: 0 });
  }, [records]);

  // Sort records by date descending
  const sortedRecords = [...records].sort((a, b) => {
    const yearDiff = b.year - a.year;
    if (yearDiff !== 0) return yearDiff;
    return getMonthNumber(b.month) - getMonthNumber(a.month);
  });

  return (
    <div className="space-y-10 animate-fade-in">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end border-b border-white/5 pb-8 gap-6">
        <div className="flex items-center space-x-6">
          <div className="bg-white/5 p-3 rounded-2xl shadow-sm border border-white/10 backdrop-blur-xl">
             <img src={insighteLogo} alt="Logo" className="h-10 w-auto object-contain brightness-110" />
          </div>
          <div>
            <h2 className="text-3xl font-black text-white font-heading tracking-tight leading-tight">
              Hello, {employee.name.split(' ')[0]}
            </h2>
            <div className="flex items-center space-x-3 mt-1.5">
              <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse"></span>
              <p className="text-indigo-200/50 font-bold text-[10px] tracking-[0.2em] uppercase">Staff ID: {employee.employeeId} • Therapeutic Consultant</p>
            </div>
          </div>
        </div>
        <button 
          onClick={onLogout} 
          className="px-5 py-2.5 rounded-2xl text-xs font-black text-rose-400 hover:bg-rose-500/10 hover:text-rose-300 transition-all active:scale-95 flex items-center space-x-2 border border-rose-500/20 uppercase tracking-widest bg-white/5 backdrop-blur-md shadow-sm"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          <span>Logout Portal</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-gradient-to-br from-indigo-600 to-indigo-700 p-6 rounded-3xl text-white shadow-[0_20px_50px_rgba(99,102,241,0.2)] group hover:-translate-y-1 transition-transform duration-300 border border-white/10">
          <div className="flex items-center justify-between mb-4">
            <div className="p-2 bg-white/10 rounded-xl">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <span className="text-[10px] font-black bg-white/10 px-2 py-1 rounded-lg uppercase tracking-widest border border-white/5">YTD Earnings</span>
          </div>
          <p className="text-indigo-100/70 text-[10px] font-black uppercase tracking-[0.2em]">Gross Total</p>
          <p className="text-3xl font-black mt-1 tracking-tight">{stats.gross.toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })}</p>
        </div>

        <div className="bg-gradient-to-br from-fuchsia-600 to-fuchsia-700 p-6 rounded-3xl text-white shadow-[0_20px_50px_rgba(192,132,252,0.2)] group hover:-translate-y-1 transition-transform duration-300 border border-white/10">
          <div className="flex items-center justify-between mb-4">
            <div className="p-2 bg-white/10 rounded-xl">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04c0 4.833 1.89 9.223 5.035 12.454a.434.434 0 00.612 0a11.955 11.955 0 005.035-12.454z" />
              </svg>
            </div>
            <span className="text-[10px] font-black bg-white/10 px-2 py-1 rounded-lg uppercase tracking-widest border border-white/5">Withholding</span>
          </div>
          <p className="text-fuchsia-100/70 text-[10px] font-black uppercase tracking-[0.2em]">Total TDS</p>
          <p className="text-3xl font-black mt-1 tracking-tight">{stats.tds.toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })}</p>
        </div>

        <div className="bg-slate-900/50 backdrop-blur-xl p-6 rounded-3xl text-white shadow-2xl group hover:-translate-y-1 transition-transform duration-300 border border-white/10">
          <div className="flex items-center justify-between mb-4">
            <div className="p-2 bg-emerald-500/10 rounded-xl border border-emerald-500/20">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            </div>
            <span className="text-[10px] font-black bg-emerald-500/10 text-emerald-400 px-2 py-1 rounded-lg uppercase tracking-widest border border-emerald-500/20">Deposited</span>
          </div>
          <p className="text-slate-500 text-[10px] font-black uppercase tracking-[0.2em]">Net Payable</p>
          <p className="text-3xl font-black mt-1 tracking-tight text-emerald-400">{stats.net.toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })}</p>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-6 px-2">
          <h3 className="text-xl font-black text-white font-heading uppercase tracking-tighter">Earnings Reports</h3>
          <span className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">{sortedRecords.length} Statements Archived</span>
        </div>
        
        {sortedRecords.length === 0 ? (
          <div className="text-center py-20 text-slate-500 bg-white/5 rounded-[2.5rem] border-2 border-dashed border-white/10 backdrop-blur-sm">
            <div className="inline-flex p-6 bg-white/5 rounded-3xl shadow-sm mb-6 border border-white/5">
               <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10 text-slate-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <p className="font-black text-white text-lg tracking-tight">No reports generated yet</p>
            <p className="text-xs font-bold uppercase tracking-widest opacity-40 mt-2">Statements will appear after processing cycle</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {sortedRecords.map((record) => (
              <div 
                key={record.id} 
                className="group glass-card border border-white/5 rounded-[2rem] p-6 flex justify-between items-center hover:bg-white/5 hover:border-white/10 transition-all cursor-pointer shadow-xl"
                onClick={() => onViewPayslip(record)}
              >
                <div className="flex items-center gap-5">
                  <div className="bg-indigo-500/10 p-4 rounded-2xl group-hover:bg-indigo-600 group-hover:text-white transition-all duration-500 border border-indigo-500/20">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-indigo-400 group-hover:text-white transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <div>
                    <h4 className="font-black text-white text-xl tracking-tight leading-tight">{record.month} {record.year}</h4>
                    <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mt-1">Earnings: {record.grossPay.toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                    <span className="px-3 py-1 bg-emerald-500/10 text-emerald-400 text-[10px] rounded-full font-black uppercase tracking-widest border border-emerald-500/20">Paid</span>
                    <div className="p-2.5 rounded-xl bg-white/5 text-slate-600 group-hover:bg-indigo-500 group-hover:text-white transition-all duration-500">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                      </svg>
                    </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-indigo-500/10 p-8 rounded-[2.5rem] border border-indigo-500/20 flex flex-col sm:flex-row items-center sm:items-start space-y-4 sm:space-y-0 sm:space-x-6 backdrop-blur-xl">
         <div className="p-3 bg-indigo-600 rounded-2xl text-white shadow-lg shadow-indigo-600/30">
           <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
         </div>
         <div className="text-center sm:text-left">
           <p className="text-white text-lg font-black tracking-tight uppercase">Security Advisory</p>
           <p className="text-indigo-200/60 text-xs font-bold leading-relaxed uppercase tracking-widest mt-2">Tax certificates (Form 16) and reimbursement statements will be automatically published here on a quarterly basis.</p>
         </div>
      </div>
    </div>
  );
};

export default Dashboard;
