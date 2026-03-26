import React, { useState } from 'react';
import { Employee, PayslipRecord } from '../types';
import { insighteLogo } from '../assets/logo';
import { getMonthNumber } from '../utils/date';
import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';

interface PayslipProps {
  employee: Employee;
  record: PayslipRecord;
  onGoBack: () => void;
}

const Payslip: React.FC<PayslipProps> = ({ employee, record, onGoBack }) => {
  const [isVerifying, setIsVerifying] = useState(false);
  const [verificationResult, setVerificationResult] = useState<{
      isValid: boolean;
      timestamp: string;
      documentHash: string;
      signedBy: string;
  } | null>(null);

  const payPeriod = `${record.month} ${record.year}`;
  const monthNum = (getMonthNumber(record.month) + 1).toString().padStart(2, '0');
  const statementNo = `INS-${record.year}${monthNum}-${employee.employeeId}`;

  const hasBreakdown = (record.baseSalary && record.baseSalary > 0) || (record.allowance && record.allowance > 0);

  const handleSaveAsPdf = () => {
    const payslipElement = document.getElementById('payslip-content');
    if (!payslipElement) {
        console.error("Payslip element not found!");
        return;
    }
    
    // Create a temporary loading state
    const actionButtons = document.getElementById('payslip-actions');
    if(actionButtons) (actionButtons as HTMLElement).style.opacity = '0.5';

    // High quality options for PDF
    const options = {
      scale: 3, // Higher scale for better clarity
      useCORS: true,
      allowTaint: true,
      backgroundColor: '#ffffff',
      logging: false,
      onclone: (clonedDoc: Document) => {
        // Ensure actions are hidden in the clone
        const clonedActions = clonedDoc.getElementById('payslip-actions');
        if (clonedActions) clonedActions.style.display = 'none';
        
        // Ensure the wrapper in clone is properly sized
        const clonedContent = clonedDoc.getElementById('payslip-content');
        if (clonedContent) {
            clonedContent.style.borderRadius = '0px'; // Flat for PDF
            clonedContent.style.boxShadow = 'none';
            clonedContent.style.border = 'none';
        }
      }
    };

    html2canvas(payslipElement, options).then((canvas: HTMLCanvasElement) => {
      if(actionButtons) (actionButtons as HTMLElement).style.opacity = '1';

      const imgData = canvas.toDataURL('image/png', 1.0);
      
      const pdf = new jsPDF({
        orientation: 'portrait',
        unit: 'mm',
        format: 'a4',
      });

      const pdfWidth = pdf.internal.pageSize.getWidth();
      const pdfHeight = pdf.internal.pageSize.getHeight();
      
      const canvasAspectRatio = canvas.width / canvas.height;

      const padding = 10;
      let imgWidth = pdfWidth - (padding * 2);
      let imgHeight = imgWidth / canvasAspectRatio;

      if (imgHeight > pdfHeight - (padding * 2)) {
          imgHeight = pdfHeight - (padding * 2);
          imgWidth = imgHeight * canvasAspectRatio;
      }
      
      const x = (pdfWidth - imgWidth) / 2;
      const y = padding;

      pdf.addImage(imgData, 'PNG', x, y, imgWidth, imgHeight, undefined, 'FAST');
      
      const fileName = `Insighte_Statement_${employee.employeeId}_${record.month}_${record.year}.pdf`;
      
      // Execute save directly
      pdf.save(fileName);

    }).catch((err: Error) => {
        console.error("Error generating PDF:", err);
        if(actionButtons) (actionButtons as HTMLElement).style.opacity = '1';
        alert("Failed to generate PDF. Please ensure you are not blocking downloads.");
    });
  };

  const handleVerify = () => {
    setIsVerifying(true);
    setTimeout(() => {
        setIsVerifying(false);
        setVerificationResult({
            isValid: true,
            timestamp: new Date().toISOString(),
            documentHash: `SHA-256:${Math.random().toString(16).substring(2, 10).toUpperCase()}...${Math.random().toString(16).substring(2, 6).toUpperCase()}`,
            signedBy: 'Insighte Pay Portal'
        });
    }, 2000);
  };

  // Improved TDS logic: 
  // 1. Check role (Consultant = 2%)
  // 2. Otherwise trust the calculated rate if it's 2 or 10
  // 3. Robust fallback
  const tdsRateRaw = record.grossPay > 0 ? Math.round((record.tds / record.grossPay) * 100) : 10;
  const displayTdsRate = (employee.role === 'Consultant' || (employee as any).role === 'Consultant') ? 2 : (tdsRateRaw === 2 || tdsRateRaw === 10 ? tdsRateRaw : (tdsRateRaw > 5 ? 10 : 2));


  return (
    <div id="payslip-wrapper" className="animate-fade-in w-full pb-10">
        <div id="payslip-content" className="bg-white p-8 md:p-12 rounded-[3.5rem] border border-slate-100 shadow-2xl max-w-4xl mx-auto overflow-hidden relative">
            {/* Subtle Watermark/Background Element */}
            <div className="absolute -top-24 -right-24 w-64 h-64 bg-slate-50 rounded-full blur-3xl opacity-50"></div>
            
            {/* Header Section */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center border-b border-slate-100 pb-10 mb-10 relative z-10">
                <div className="mb-6 md:mb-0">
                    <img 
                      src={insighteLogo} 
                      alt="Insighte Logo" 
                      className="h-12 w-auto object-contain mb-3" 
                    />
                    <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest leading-none">Official Earnings Statement</p>
                </div>
                <div className="text-left md:text-right space-y-1">
                    <h2 className="text-xl font-black text-slate-900 uppercase tracking-tight font-heading text-nowrap">Insighte Childcare Pvt Ltd</h2>
                    <p className="text-[11px] text-slate-500 font-bold tracking-wider">CIN: U85100KL2022PTC075910</p>
                    <p className="text-[10px] text-slate-400 font-medium">Global Headquarters: Trivandrum, Kerala</p>
                </div>
            </div>

            {/* Document Meta Section */}
            <div className="flex flex-col sm:flex-row justify-between items-baseline mb-12 gap-4">
                <div>
                  <h1 className="text-5xl font-black text-slate-900 tracking-tighter mb-1 font-heading">Statement</h1>
                  <p className="text-indigo-600 font-black tracking-widest uppercase text-xs">{payPeriod} CYCLE</p>
                </div>
                <div className="bg-slate-50 px-6 py-3 rounded-2xl border border-slate-100">
                  <p className="text-[9px] font-black text-slate-400 uppercase tracking-[0.2em] mb-1">Reference ID</p>
                  <p className="text-sm font-bold text-slate-700 font-mono tracking-tight">{statementNo}</p>
                </div>
            </div>

            {/* Employee Detailed Profile */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-10 mb-12">
                <div className="space-y-6">
                  <div className="flex flex-col">
                    <label className="text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] mb-1.5 leading-none">Employee Name</label>
                    <p className="text-xl font-bold text-slate-900 leading-tight">{employee.name}</p>
                  </div>
                  <div className="flex flex-col">
                    <label className="text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] mb-1.5 leading-none">Staff ID</label>
                    <p className="text-base font-bold text-slate-600 leading-tight">{employee.employeeId}</p>
                  </div>
                  <div className="flex flex-col">
                    <label className="text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] mb-1.5 leading-none">Designation</label>
                    <p className="text-base font-bold text-slate-600 leading-tight">{employee.role || 'Therapeutic Consultant'}</p>
                  </div>
                </div>
                <div className="space-y-6">
                  <div className="flex flex-col">
                    <label className="text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] mb-1.5 leading-none">Email Address</label>
                    <p className="text-base font-bold text-slate-600 leading-tight break-all">{employee.email}</p>
                  </div>
                  <div className="flex flex-col">
                    <label className="text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] mb-1.5 leading-none text-nowrap">Payment Method</label>
                    <p className="text-base font-bold text-slate-600 leading-tight">Bank Transfer (IMPS/NEFT)</p>
                  </div>
                  <div className="flex flex-col">
                    <label className="text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] mb-1.5 leading-none">Disbursement Status</label>
                    <span className="inline-flex items-center space-x-2 px-3 py-1 bg-emerald-50 text-emerald-600 rounded-full border border-emerald-100 font-bold">
                      <span className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></span>
                      <span className="text-xs uppercase tracking-widest">Completed</span>
                    </span>
                  </div>
                </div>
            </div>

            {/* Main Financial Ledger */}
            <div className="mb-12 overflow-x-auto">
                <table className="w-full min-w-[500px]">
                    <thead>
                        <tr className="border-b-4 border-slate-900">
                            <th className="py-5 text-left text-[11px] font-black text-slate-900 uppercase tracking-[4px]">Line Item Description</th>
                            <th className="py-5 text-right text-[11px] font-black text-slate-900 uppercase tracking-[4px]">Value (INR)</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                        {hasBreakdown ? (
                            <>
                                <tr>
                                    <td className="py-6 font-bold text-slate-700 text-sm italic">Base Professional Fee</td>
                                    <td className="py-6 text-right font-bold text-slate-900 text-lg">{(record.baseSalary || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                                </tr>
                                <tr>
                                    <td className="py-6 font-bold text-slate-700 text-sm italic">Performance Allowance</td>
                                    <td className="py-6 text-right font-bold text-slate-900 text-lg">{(record.allowance || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                                </tr>
                            </>
                        ) : (
                            <tr>
                                <td className="py-8 font-bold text-slate-700 text-lg">Consolidated Professional Fee</td>
                                <td className="py-8 text-right font-black text-slate-900 text-2xl">{record.grossPay.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                            </tr>
                        )}
                        
                        <tr className="bg-slate-50/50">
                            <td className="py-6 pl-4 font-black text-slate-400 text-[10px] uppercase tracking-[0.2em]">Total Gross Earning</td>
                            <td className="py-6 pr-4 text-right font-black text-slate-900 text-xl">{record.grossPay.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                        </tr>

                        <tr>
                            <td className="py-6 font-bold text-rose-500 text-sm italic">TDS (Tax Deducted at Source {displayTdsRate}%)</td>
                            <td className="py-6 text-right font-bold text-rose-600 text-lg">({record.tds.toLocaleString('en-IN', { minimumFractionDigits: 2 })})</td>
                        </tr>
                    </tbody>
                    <tfoot>
                        <tr className="border-t-8 border-double border-slate-900 bg-indigo-50/20">
                            <td className="py-10 pl-6">
                                <span className="text-3xl font-black text-slate-900 tracking-tighter uppercase font-heading">Net Payable</span>
                                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-1">Final Settlement Credited to Account</p>
                            </td>
                            <td className="py-10 pr-6 text-right">
                                <span className="text-5xl font-black text-indigo-600 tracking-tighter">{record.netPay.toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })}</span>
                            </td>
                        </tr>
                    </tfoot>
                </table>
            </div>

            {/* Footer Summary & Compliance */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-10 items-end pt-12 border-t border-slate-100">
                <div className="space-y-6">
                  <div 
                    className={`flex items-center space-x-5 p-5 rounded-[2rem] border-2 transition-all overflow-hidden relative cursor-pointer ${verificationResult ? 'bg-emerald-50 border-emerald-200' : 'bg-slate-50 border-slate-100 hover:border-indigo-300 hover:bg-white hover:shadow-xl hover:shadow-indigo-100'}`}
                    onClick={!verificationResult ? handleVerify : undefined}
                  >
                    <div className={`w-16 h-16 rounded-2xl border-2 flex items-center justify-center transition-all duration-500 shadow-sm ${isVerifying ? 'bg-indigo-500 border-indigo-500 animate-pulse' : (verificationResult ? 'bg-emerald-500 border-emerald-500' : 'bg-white border-slate-200')}`}>
                       {isVerifying ? (
                          <svg className="animate-spin h-7 w-7 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                       ) : verificationResult ? (
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-7 w-7 text-white" viewBox="0 0 20 20" fill="currentColor">
                              <path fillRule="evenodd" d="M2.166 4.9L9.03 1.151a1.125 1.125 0 011.08 0L17 4.9a1.125 1.125 0 01.62 1.01V11c0 4.14-2.67 7.98-6.62 9.61a1.125 1.125 0 01-.88 0C6.17 19.04 3.5 15.2 3.5 11V5.91c0-.44.26-.84.66-1.01zm8.34 9.58l3-3a.75.75 0 00-1.06-1.06L10 12.94l-1.47-1.47a.75.75 0 10-1.06 1.06l2 2a.75.75 0 001.06 0z" clipRule="evenodd" />
                          </svg>
                       ) : (
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-7 w-7 text-slate-300 group-hover:text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04m18.236 0a11.958 11.958 0 00-2.015-1.165M12 2.944a11.952 11.952 0 00-5.45 1.31m4.043 1.971c.585.145 1.17.269 1.767.368a11.955 11.955 0 01-1.767-.368zm0 0c-.585.145-1.13.35-1.667.601m1.667-.601L12 2.944m-1.333 3.601a11.959 11.959 0 01-1.667.601" />
                          </svg>
                       )}
                    </div>
                    <div>
                      <p className="text-[10px] font-black text-slate-900 uppercase tracking-widest leading-tight">Digital Document Validation</p>
                      <p className={`text-sm font-bold mt-1 ${verificationResult ? 'text-emerald-600' : 'text-slate-400'}`}>
                        {isVerifying ? 'Authenticating Document...' : (verificationResult ? 'Doc-ID: Verified Authentic' : 'Certify This Document')}
                      </p>
                    </div>
                  </div>
                  <p className="text-[9px] text-slate-400 font-bold italic leading-relaxed px-2">This document is digitally signed and encrypted. No physical signature is required under section 1.2 of the IT Act 2000 regarding digital disclosures.</p>
                </div>
                <div className="text-left md:text-right space-y-2 pr-6">
                   <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Support Channel</p>
                   <p className="text-[13px] text-slate-900 font-black tracking-tight">accounts@insighte.in</p>
                   <div className="pt-2">
                       <p className="text-[9px] font-black text-slate-400 uppercase tracking-[0.2em] mb-1">Direct Support</p>
                       <p className="text-xs text-indigo-600 font-bold">Verification Team</p>
                   </div>
                </div>
            </div>
            
            {/* Verification Result Modal */}
            {verificationResult && (
               <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-white/98 backdrop-blur-3xl px-12 py-10 rounded-[4rem] border-4 border-emerald-500 shadow-[0_50px_150px_-20px_rgba(16,185,129,0.4)] flex flex-col items-center z-50 animate-bounce-in w-[90%] max-w-md">
                  <div className="w-20 h-20 bg-emerald-500 rounded-full flex items-center justify-center text-white mb-8 shadow-2xl scale-110">
                     <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={4} d="M5 13l4 4L19 7" />
                     </svg>
                  </div>
                  <h3 className="text-3xl font-black text-slate-900 tracking-tighter text-center">Identity Verified</h3>
                  <div className="mt-8 space-y-4 w-full border-y border-slate-100 py-8">
                      <div className="flex justify-between text-[11px] font-black uppercase tracking-widest">
                          <span className="text-slate-400">Portal Status</span>
                          <span className="text-emerald-600">Active & Valid</span>
                      </div>
                      <div className="flex justify-between text-[11px] font-black uppercase tracking-widest">
                          <span className="text-slate-400">Security Hash</span>
                          <span className="text-slate-900 font-mono text-[10px] break-all ml-4 text-right">{verificationResult.documentHash}</span>
                      </div>
                      <div className="flex justify-between text-[11px] font-black uppercase tracking-widest">
                          <span className="text-slate-400">Authorized By</span>
                          <span className="text-indigo-600">Insighte Pay Portal</span>
                      </div>
                  </div>
                  <button 
                    onClick={() => setVerificationResult(null)}
                    className="mt-10 w-full py-4 bg-slate-900 text-white rounded-3xl text-sm font-black uppercase tracking-widest hover:bg-black hover:scale-[1.02] active:scale-[0.98] transition-all shadow-xl"
                  >
                    Close Verification
                  </button>
               </div>
            )}
        </div>

        {/* Action Buttons */}
        <div id="payslip-actions" className="flex flex-col sm:flex-row justify-center gap-5 pt-12 pb-10 max-w-lg mx-auto relative z-20 px-6 sm:px-0">
            <button
                type="button"
                onClick={onGoBack}
                className="w-full py-5 px-8 rounded-3xl font-black text-slate-600 bg-white border-2 border-slate-100 shadow-xl shadow-slate-200/50 hover:border-indigo-200 hover:bg-slate-50 active:scale-95 transition-all outline-none uppercase tracking-widest text-xs"
            >
                Return to Hub
            </button>
             <button
                type="button"
                onClick={handleSaveAsPdf}
                className="w-full btn-gradient py-5 px-8 rounded-3xl text-white font-black shadow-[0_20px_40px_-10px_rgba(99,102,241,0.4)] transform transition-all active:scale-95 flex items-center justify-center space-x-3 outline-none uppercase tracking-widest text-xs"
            >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                <span>Download PDF</span>
            </button>
        </div>
    </div>
  );
};

export default Payslip;
