
import React from 'react';
import { Employee, PayslipRecord } from '../types';
import { insighteLogo } from '../assets/logo';
import { getMonthNumber } from '../utils/date';

declare const html2canvas: any;
declare const jspdf: any;

interface PayslipProps {
  employee: Employee;
  record: PayslipRecord;
  onGoBack: () => void;
}

const Payslip: React.FC<PayslipProps> = ({ employee, record, onGoBack }) => {
  const payPeriod = `${record.month} ${record.year}`;
  
  // Generate a professional looking Statement Number
  // Format: INS-YYYYMM-EMPID
  const monthNum = (getMonthNumber(record.month) + 1).toString().padStart(2, '0');
  const statementNo = `INS-${record.year}${monthNum}-${employee.employeeId}`;

  const handleSaveAsPdf = () => {
    const payslipElement = document.getElementById('payslip-content');
    if (!payslipElement) {
        console.error("Payslip element not found!");
        return;
    }
    
    const actionButtons = document.getElementById('payslip-actions');
    if(actionButtons) (actionButtons as HTMLElement).style.display = 'none';

    html2canvas(payslipElement, {
      scale: 2,
      useCORS: true,
      backgroundColor: '#ffffff',
    }).then(canvas => {
      if(actionButtons) (actionButtons as HTMLElement).style.display = 'flex';

      const imgData = canvas.toDataURL('image/png');
      const { jsPDF } = jspdf;
      
      const pdf = new jsPDF({
        orientation: 'portrait',
        unit: 'mm',
        format: 'a4'
      });

      const pdfWidth = pdf.internal.pageSize.getWidth();
      const pdfHeight = pdf.internal.pageSize.getHeight();
      
      const canvasAspectRatio = canvas.width / canvas.height;

      const margin = 10;
      let imgWidth = pdfWidth - (margin * 2);
      let imgHeight = imgWidth / canvasAspectRatio;

      if (imgHeight > pdfHeight - (margin * 2)) {
          imgHeight = pdfHeight - (margin * 2);
          imgWidth = imgHeight * canvasAspectRatio;
      }
      
      const x = (pdfWidth - imgWidth) / 2;

      pdf.addImage(imgData, 'PNG', x, margin, imgWidth, imgHeight);
      pdf.save(`earnings-statement-${employee.employeeId}-${payPeriod.replace(/\s/g, '-')}.pdf`);
    }).catch(err => {
        console.error("Error generating PDF:", err);
        if(actionButtons) (actionButtons as HTMLElement).style.display = 'flex';
    });
  };

  const hasBreakdown = (record.baseSalary || 0) > 0;

  return (
    <div id="payslip-wrapper" className="animate-fade-in w-full">
        <div id="payslip-content" className="bg-white p-8 rounded-lg border border-slate-200 shadow-sm max-w-3xl mx-auto">
            {/* Header Section */}
            <div className="flex flex-col md:flex-row justify-between items-center border-b-2 border-slate-800 pb-6 mb-6">
                <div className="mb-4 md:mb-0">
                    <img src={insighteLogo} alt="Insighte Logo" className="h-16 object-contain" crossOrigin="anonymous" />
                </div>
                <div className="text-center md:text-right">
                    <h2 className="text-xl font-bold text-slate-800 uppercase tracking-wide">insighte childcare private limited</h2>
                    <p className="text-sm text-slate-600 font-medium">CIN: U85100KL2022PTC075910</p>
                    <p className="text-xs text-slate-500 mt-1">Trivandrum, Kerala</p>
                </div>
            </div>

            {/* Title Section */}
            <div className="text-center mb-8">
                <h1 className="text-2xl font-bold text-slate-800 underline decoration-2 underline-offset-4">EARNINGS STATEMENT</h1>
                <p className="text-slate-500 font-medium mt-2">For the month of {payPeriod}</p>
            </div>

            {/* Employee Details Grid */}
            <div className="bg-slate-50 border border-slate-300 rounded p-4 mb-8">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-y-3 gap-x-8 text-sm">
                    <div className="flex justify-between md:justify-start">
                        <span className="text-slate-500 w-48">Staff / Consultant Name:</span>
                        <span className="font-semibold text-slate-800">{employee.name}</span>
                    </div>
                    <div className="flex justify-between md:justify-start">
                        <span className="text-slate-500 w-48">Statement No:</span>
                        <span className="font-semibold text-slate-800 uppercase">{statementNo}</span>
                    </div>
                    <div className="flex justify-between md:justify-start">
                        <span className="text-slate-500 w-48">Staff / Consultant ID:</span>
                        <span className="font-semibold text-slate-800">{employee.employeeId}</span>
                    </div>
                    <div className="flex justify-between md:justify-start">
                        <span className="text-slate-500 w-48">Email:</span>
                        <span className="font-semibold text-slate-800">{employee.email}</span>
                    </div>
                     <div className="flex justify-between md:justify-start">
                        <span className="text-slate-500 w-48">Designation:</span>
                        <span className="font-semibold text-slate-800">Therapist</span>
                    </div>
                     <div className="flex justify-between md:justify-start">
                        <span className="text-slate-500 w-48">Status:</span>
                        <span className="font-semibold text-green-600">Active</span>
                    </div>
                </div>
            </div>

            {/* Financials Table */}
            <div className="mb-8 border border-slate-300 rounded overflow-hidden">
                <table className="w-full text-sm">
                    <thead className="bg-slate-100 text-slate-700 font-bold border-b border-slate-300">
                        <tr>
                            <th className="py-3 px-4 text-left w-1/2 border-r border-slate-300">Earnings</th>
                            <th className="py-3 px-4 text-right">Amount (₹)</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                        {hasBreakdown ? (
                            <>
                                <tr>
                                    <td className="py-2 px-4 border-r border-slate-200 text-slate-600">Base Salary</td>
                                    <td className="py-2 px-4 text-right text-slate-800">{(record.baseSalary || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                                </tr>
                                <tr>
                                    <td className="py-2 px-4 border-r border-slate-200 text-slate-600">Allowance</td>
                                    <td className="py-2 px-4 text-right text-slate-800">{(record.allowance || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                                </tr>
                            </>
                        ) : (
                            <tr>
                                <td className="py-2 px-4 border-r border-slate-200 text-slate-600">Consolidated Pay</td>
                                <td className="py-2 px-4 text-right text-slate-800">{record.grossPay.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                            </tr>
                        )}
                         {/* Spacer rows to maintain height if needed, or just let it collapse */}
                         <tr className="bg-slate-50 font-semibold">
                            <td className="py-2 px-4 border-r border-slate-300 text-slate-800">Total Earnings (A)</td>
                            <td className="py-2 px-4 text-right text-slate-800">{record.grossPay.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                        </tr>
                    </tbody>
                    <thead className="bg-slate-100 text-slate-700 font-bold border-t border-b border-slate-300">
                        <tr>
                            <th className="py-3 px-4 text-left border-r border-slate-300">Deductions</th>
                            <th className="py-3 px-4 text-right">Amount (₹)</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                        <tr>
                            <td className="py-2 px-4 border-r border-slate-200 text-slate-600">TDS (Tax Deducted at Source)</td>
                            <td className="py-2 px-4 text-right text-red-600">{record.tds.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                        </tr>
                        <tr className="bg-slate-50 font-semibold">
                            <td className="py-2 px-4 border-r border-slate-300 text-slate-800">Total Deductions (B)</td>
                            <td className="py-2 px-4 text-right text-red-600">{record.tds.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            {/* Net Pay Section */}
            <div className="flex justify-end mb-12">
                <div className="bg-purple-50 border border-purple-200 rounded p-4 w-full md:w-1/2">
                    <div className="flex justify-between items-center mb-1">
                        <span className="text-purple-800 font-semibold">Net Payable (A - B):</span>
                        <span className="text-2xl font-bold text-purple-700">{record.netPay.toLocaleString('en-IN', { style: 'currency', currency: 'INR' })}</span>
                    </div>
                    <div className="text-right text-xs text-purple-500 uppercase font-medium">
                        {/* Placeholder for words conversion if needed in future */}
                        (Net Pay Transferred to Bank Account)
                    </div>
                </div>
            </div>

            {/* Footer Section */}
            <div className="mt-8 pt-6 border-t border-slate-200 text-center">
                <p className="text-xs text-slate-400 mb-1">This is a system-generated earnings statement and does not require a physical signature.</p>
                <p className="text-xs text-slate-400 mb-1">Insighte Childcare Pvt Ltd | Regd Office: Trivandrum, Kerala</p>
                <p className="text-xs text-slate-400">Contact accounts@insighte.in for any queries</p>
            </div>
        </div>

        {/* Action Buttons */}
        <div id="payslip-actions" className="flex flex-col sm:flex-row justify-center gap-4 pt-8 pb-8">
            <button
                type="button"
                onClick={onGoBack}
                className="w-full sm:w-auto flex justify-center py-2.5 px-6 border border-slate-300 rounded-md shadow-sm text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 transition-colors"
            >
                Back to Dashboard
            </button>
             <button
                type="button"
                onClick={handleSaveAsPdf}
                className="w-full sm:w-auto flex items-center justify-center py-2.5 px-6 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 transition-colors"
            >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Download PDF
            </button>
        </div>
    </div>
  );
};

export default Payslip;
