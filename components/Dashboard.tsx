
import React, { useMemo } from 'react';
import { Employee, PayslipRecord } from '../types';
import { getMonthNumber } from '../utils/date';

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
    <div className="space-y-8 animate-fade-in">
      <div className="flex justify-between items-center border-b pb-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-800">Welcome, {employee.name.split(' ')[0]}</h2>
          <p className="text-slate-500 text-sm">Staff / Consultant ID: {employee.employeeId}</p>
        </div>
        <button onClick={onLogout} className="text-sm text-red-500 hover:text-red-700 font-medium">
          Logout
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-purple-50 p-4 rounded-lg border border-purple-100">
          <p className="text-purple-600 text-xs font-semibold uppercase tracking-wide">Total Earnings (YTD)</p>
          <p className="text-2xl font-bold text-slate-800 mt-1">{stats.gross.toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })}</p>
        </div>
        <div className="bg-red-50 p-4 rounded-lg border border-red-100">
          <p className="text-red-600 text-xs font-semibold uppercase tracking-wide">Total TDS (YTD)</p>
          <p className="text-2xl font-bold text-slate-800 mt-1">{stats.tds.toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })}</p>
        </div>
        <div className="bg-green-50 p-4 rounded-lg border border-green-100">
          <p className="text-green-600 text-xs font-semibold uppercase tracking-wide">Net Pay (YTD)</p>
          <p className="text-2xl font-bold text-slate-800 mt-1">{stats.net.toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })}</p>
        </div>
      </div>

      <div>
        <h3 className="text-lg font-semibold text-slate-700 mb-4">Your Earnings Reports</h3>
        {sortedRecords.length === 0 ? (
          <div className="text-center py-8 text-slate-500 bg-slate-50 rounded-lg border border-dashed border-slate-300">
            No earnings reports found for your account.
          </div>
        ) : (
          <div className="space-y-3">
            {sortedRecords.map((record) => (
              <div 
                key={record.id} 
                className="bg-white border border-slate-200 rounded-lg p-4 flex justify-between items-center hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => onViewPayslip(record)}
              >
                <div className="flex items-center gap-4">
                  <div className="bg-slate-100 p-2 rounded-full">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                  <div>
                    <h4 className="font-semibold text-slate-800">{record.month} {record.year}</h4>
                    <p className="text-xs text-slate-500">Gross: {record.grossPay.toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                    <span className="px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full font-medium">Paid</span>
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-slate-400" viewBox="0 0 20 20" fill="currentColor">
                        <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                    </svg>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-slate-50 p-4 rounded-lg border border-dashed border-slate-300 text-center">
         <p className="text-slate-500 text-sm">Tax documents (Form 16) and other financial statements will be available here soon.</p>
      </div>
    </div>
  );
};

export default Dashboard;
