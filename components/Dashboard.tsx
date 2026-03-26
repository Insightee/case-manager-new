
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
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end border-b border-slate-100 pb-8 gap-6">
        <div className="flex items-center space-x-6">
          <div className="bg-white p-3 rounded-2xl shadow-sm border border-slate-50">
             <img src={insighteLogo} alt="Logo" className="h-10 w-auto object-contain" />
          </div>
          <div>
            <h2 className="text-3xl font-black text-slate-900 font-heading tracking-tight leading-tight">
              Hello, {employee.name.split(' ')[0]}
            </h2>
            <div className="flex items-center space-x-3 mt-1.5">
              <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse"></span>
              <p className="text-slate-400 font-bold text-[10px] tracking-[0.2em] uppercase">Staff ID: {employee.employeeId} • Therapeutic Consultant</p>
            </div>
          </div>
        </div>
        <button 
          onClick={onLogout} 
          className="px-5 py-2.5 rounded-2xl text-xs font-black text-rose-500 hover:bg-rose-50 hover:text-rose-600 transition-all active:scale-95 flex items-center space-x-2 border border-rose-100 uppercase tracking-widest bg-white shadow-sm"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
          </svg>
          <span>Logout Portal</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-gradient-to-br from-indigo-500 to-indigo-600 p-6 rounded-3xl text-white shadow-xl shadow-indigo-100 group hover:-translate-y-1 transition-transform duration-300">
          <div className="flex items-center justify-between mb-4">
            <div className="p-2 bg-white/20 rounded-xl">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <span className="text-xs font-bold bg-white/20 px-2 py-1 rounded-lg uppercase tracking-wider">YTD Earnings</span>
          </div>
          <p className="text-indigo-100 text-sm font-medium opacity-90 uppercase tracking-widest">Gross Total</p>
          <p className="text-3xl font-extrabold mt-1 tracking-tight">{stats.gross.toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })}</p>
        </div>

        <div className="bg-gradient-to-br from-fuchsia-500 to-fuchsia-600 p-6 rounded-3xl text-white shadow-xl shadow-fuchsia-100 group hover:-translate-y-1 transition-transform duration-300">
          <div className="flex items-center justify-between mb-4">
            <div className="p-2 bg-white/20 rounded-xl">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04c0 4.833 1.89 9.223 5.035 12.454a.434.434 0 00.612 0a11.955 11.955 0 005.035-12.454z" />
              </svg>
            </div>
            <span className="text-xs font-bold bg-white/20 px-2 py-1 rounded-lg uppercase tracking-wider">Withholding</span>
          </div>
          <p className="text-fuchsia-100 text-sm font-medium opacity-90 uppercase tracking-widest">Total TDS</p>
          <p className="text-3xl font-extrabold mt-1 tracking-tight">{stats.tds.toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })}</p>
        </div>

        <div className="bg-slate-900 p-6 rounded-3xl text-white shadow-xl shadow-slate-200 group hover:-translate-y-1 transition-transform duration-300">
          <div className="flex items-center justify-between mb-4">
            <div className="p-2 bg-emerald-500/20 rounded-xl">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            </div>
            <span className="text-xs font-bold bg-emerald-500/20 text-emerald-400 px-2 py-1 rounded-lg uppercase tracking-wider">Deposited</span>
          </div>
          <p className="text-slate-400 text-sm font-medium uppercase tracking-widest">Net Payable</p>
          <p className="text-3xl font-extrabold mt-1 tracking-tight text-emerald-400">{stats.net.toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })}</p>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-bold text-slate-800 font-heading">Earnings Reports</h3>
          <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">{sortedRecords.length} Reports</span>
        </div>
        
        {sortedRecords.length === 0 ? (
          <div className="text-center py-16 text-slate-400 bg-slate-50/50 rounded-3xl border-2 border-dashed border-slate-200">
            <div className="inline-flex p-4 bg-white rounded-2xl shadow-sm mb-4">
               <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <p className="font-semibold text-slate-600">No reports generated yet</p>
            <p className="text-sm">Your monthly statements will appear here after payroll processing.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {sortedRecords.map((record) => (
              <div 
                key={record.id} 
                className="group bg-white border border-slate-100 rounded-3xl p-5 flex justify-between items-center hover:shadow-[0_10px_40px_rgba(0,0,0,0.04)] hover:border-indigo-100 transition-all cursor-pointer ring-offset-2 hover:ring-2 hover:ring-indigo-100"
                onClick={() => onViewPayslip(record)}
              >
                <div className="flex items-center gap-4">
                  <div className="bg-indigo-50 p-3 rounded-2xl group-hover:bg-indigo-600 group-hover:text-white transition-colors">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-indigo-500 group-hover:text-white transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-900 text-lg leading-tight">{record.month} {record.year}</h4>
                    <p className="text-sm text-slate-400 font-medium">Earnings: {record.grossPay.toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                    <span className="px-3 py-1 bg-emerald-50 text-emerald-600 text-[10px] sm:text-xs rounded-full font-bold uppercase tracking-wider border border-emerald-100">Paid</span>
                    <div className="p-2 rounded-xl bg-slate-50 text-slate-400 group-hover:bg-indigo-50 group-hover:text-indigo-600 transition-all">
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

      <div className="bg-gradient-to-r from-indigo-50 to-indigo-100/30 p-6 rounded-3xl border border-indigo-100 flex items-start space-x-4">
         <div className="p-2 bg-indigo-500 rounded-xl text-white shrink-0">
           <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
         </div>
         <div>
           <p className="text-indigo-900 text-sm font-bold">Future Documents</p>
           <p className="text-indigo-700/70 text-sm font-medium leading-relaxed">Tax certificates (Form 16) and reimbursement statements will be automatically published here on a quarterly basis.</p>
         </div>
      </div>
    </div>
  );
};

export default Dashboard;
