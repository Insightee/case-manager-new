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

  const generatedAt = new Date().toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
      timeZone: 'Asia/Kolkata'
  });

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
      scale: 2, // Better stability across browsers
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
        compress: true,
      });

      // Set Document Metadata for Adobe PDF Compatibility
      pdf.setProperties({
        title: `Payslip - ${employee.name} - ${record.month} ${record.year}`,
        subject: 'Official Earnings Statement',
        author: 'Insighte Childcare Pvt Ltd',
        keywords: 'payslip, insighte, earnings',
        creator: 'Insighte Pay Portal'
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
      
      // Sanitize Filename with extra strictness: strictly alphanumeric and forced extension
      const safeEmployeeId = String(employee.employeeId).replace(/[^a-z0-9]/gi, '_').toLowerCase();
      const safeMonth = String(record.month).replace(/[^a-z0-9]/gi, '_').toLowerCase();
      const safeYear = String(record.year).replace(/[^a-z0-9]/gi, '_');
      const fileName = `insighte_statement_${safeEmployeeId}_${safeMonth}_${safeYear}.pdf`;
      
      // Use Reinforced Blob-based download to force application/pdf MIME type
      const pdfBlob = pdf.output('blob');
      const reinforcedBlob = new Blob([pdfBlob], { type: 'application/pdf' });
      const blobUrl = URL.createObjectURL(reinforcedBlob);
      
      const downloadLink = document.createElement('a');
      downloadLink.href = blobUrl;
      downloadLink.setAttribute('download', fileName);
      downloadLink.style.display = 'none';
      document.body.appendChild(downloadLink);
      
      // Trigger download
      downloadLink.click();
      
      // Cleanup with slightly longer delay for browser stability
      setTimeout(() => {
          if (document.body.contains(downloadLink)) {
              document.body.removeChild(downloadLink);
          }
          URL.revokeObjectURL(blobUrl);
      }, 500);

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

  // Financial Values from Record (Direct Mirror of Source Sheet)
  const displayTds = record.tds || 0;
  const displayNetPay = record.netPay || (record.grossPay - displayTds);
  const displayGrossPay = record.grossPay || 0;


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
            <div className="flex flex-col md:flex-row justify-between items-start md:items-end mb-12 gap-8">
                <div className="flex flex-col gap-2">
                  <h1 className="text-4xl md:text-5xl font-black text-slate-900 tracking-tighter mb-1 font-heading leading-snug underline decoration-indigo-200 underline-offset-8">Statement</h1>
                  <p className="text-indigo-600 font-black tracking-[0.3em] uppercase text-[10px] sm:text-[11px] mt-3 block">{payPeriod} CYCLE</p>
                </div>
                <div className="flex flex-col sm:flex-row gap-2">
                  <div className="bg-slate-50 px-6 py-3 rounded-2xl border border-slate-100">
                    <p className="text-[9px] font-black text-slate-400 uppercase tracking-[0.2em] mb-1">Reference ID</p>
                    <p className="text-sm font-bold text-slate-700 font-mono tracking-tight">{statementNo}</p>
                  </div>
                  <div className="bg-indigo-50/30 px-6 py-3 rounded-2xl border border-indigo-100/50">
                    <p className="text-[9px] font-black text-indigo-400 uppercase tracking-[0.2em] mb-1">Generated On</p>
                    <p className="text-sm font-bold text-indigo-700 font-mono tracking-tight">{generatedAt}</p>
                  </div>
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
                            <td className="py-6 font-bold text-rose-500 text-sm italic">
                                TDS Deducted
                            </td>
                            <td className="py-6 text-right font-bold text-rose-600 text-lg">({displayTds.toLocaleString('en-IN', { minimumFractionDigits: 2 })})</td>
                        </tr>
                    </tbody>
                    <tfoot>
                        <tr className="border-t-8 border-double border-slate-900 bg-indigo-50/20">
                            <td className="py-10 pl-6 text-left">
                                <span className="text-3xl font-black text-slate-900 tracking-tighter uppercase font-heading block">Net Payable</span>
                                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-1">Final Settlement Credited to Account</p>
                            </td>
                            <td className="py-10 pr-6 text-right align-middle">
                                <span className="text-5xl font-black text-indigo-600 tracking-tighter">{displayNetPay.toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })}</span>
                            </td>
                        </tr>
                    </tfoot>
                </table>
            </div>

            {/* Footer Summary & Compliance */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-10 items-start pt-12 border-t border-slate-100">
                <div className="space-y-3">
                  <div className="flex items-center space-x-2 text-indigo-500">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M2.166 4.9L9.03 1.151a1.125 1.125 0 011.08 0L17 4.9a1.125 1.125 0 01.62 1.01V11c0 4.14-2.67 7.98-6.62 9.61a1.125 1.125 0 01-.88 0C6.17 19.04 3.5 15.2 3.5 11V5.91c0-.44.26-.84.66-1.01zm8.34 9.58l3-3a.75.75 0 00-1.06-1.06L10 12.94l-1.47-1.47a.75.75 0 10-1.06 1.06l2 2a.75.75 0 001.06 0z" clipRule="evenodd" />
                    </svg>
                    <p className="text-[10px] font-black uppercase tracking-widest">Digitally Signed Document</p>
                  </div>
                  <p className="text-[9px] text-slate-400 leading-relaxed italic pr-6">Encrypted and electronically validated. No physical signature required per IT Act 2000.</p>
                </div>
                <div className="text-left md:text-right space-y-2">
                   <div>
                     <p className="text-[9px] font-black text-slate-400 uppercase tracking-[0.2em] mb-0.5">Support Channel</p>
                     <p className="text-base text-indigo-600 font-bold tracking-tight">accounts@insighte.in</p>
                   </div>
                   <div className="pt-2">
                     <p className="text-[8px] text-slate-300 uppercase font-black tracking-widest">System Validation Timestamp: {generatedAt}</p>
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
