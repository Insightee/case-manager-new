
import React, { useState, useCallback, useMemo } from 'react';
import { Employee, AppState, PayslipRecord } from './types';
import { employees, payslipRecords } from './data/employees';
import EmployeeSelector from './components/EmployeeSelector';
import OtpInput from './components/OtpInput';
import Payslip from './components/Payslip';
import AdminPanel from './components/AdminPanel';
import Dashboard from './components/Dashboard';

function App() {
  const [appState, setAppState] = useState<AppState>(AppState.SELECT_EMPLOYEE);
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<PayslipRecord | null>(null);
  const [error, setError] = useState<string>('');
  const [isAdminPanelOpen, setIsAdminPanelOpen] = useState<boolean>(false);

  const handleSelectEmployee = useCallback((employeeId: string) => {
    const employee = employees.find(e => e.employeeId === employeeId);
    if (employee) {
      setSelectedEmployee(employee);
      setError('');
      setAppState(AppState.VERIFY_STAFF_ID);
    } else {
      setError('Could not find the selected employee.');
    }
  }, []);

  const handleVerifyStaffId = useCallback((staffId: string) => {
    if (selectedEmployee && staffId === selectedEmployee.employeeId) {
      setError('');
      setAppState(AppState.DASHBOARD);
    } else {
      setError('Invalid Staff ID. Please try again.');
    }
  }, [selectedEmployee]);

  const handleViewPayslip = useCallback((record: PayslipRecord) => {
    setSelectedRecord(record);
    setAppState(AppState.VIEW_PAYSLIP);
  }, []);

  const handleBackToDashboard = useCallback(() => {
    setSelectedRecord(null);
    setAppState(AppState.DASHBOARD);
  }, []);

  const handleLogout = useCallback(() => {
    setAppState(AppState.SELECT_EMPLOYEE);
    setSelectedEmployee(null);
    setSelectedRecord(null);
    setError('');
  }, []);

  const handleBackToSelect = useCallback(() => {
    setAppState(AppState.SELECT_EMPLOYEE);
    setSelectedEmployee(null);
    setError('');
  }, []);

  // Filter records for the logged-in employee
  const employeeRecords = useMemo(() => {
    if (!selectedEmployee) return [];
    return payslipRecords.filter(r => r.employeeId === selectedEmployee.employeeId);
  }, [selectedEmployee]);

  const renderContent = () => {
    switch (appState) {
      case AppState.SELECT_EMPLOYEE:
        return (
          <EmployeeSelector 
            employees={employees} 
            onSelect={handleSelectEmployee}
          />
        );
      case AppState.VERIFY_STAFF_ID:
        if (selectedEmployee) {
          return (
            <OtpInput
              employeeName={selectedEmployee.name}
              onVerify={handleVerifyStaffId}
              onGoBack={handleBackToSelect}
              error={error}
            />
          );
        }
        return null;
      case AppState.DASHBOARD:
        if (selectedEmployee) {
            return (
                <Dashboard 
                    employee={selectedEmployee} 
                    records={employeeRecords}
                    onViewPayslip={handleViewPayslip}
                    onLogout={handleLogout}
                />
            );
        }
        return null;
      case AppState.VIEW_PAYSLIP:
        if (selectedEmployee && selectedRecord) {
          return (
            <Payslip 
                employee={selectedEmployee} 
                record={selectedRecord} 
                onGoBack={handleBackToDashboard} 
            />
          );
        }
        return null;
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4 bg-slate-100 font-sans">
        <header className="w-full max-w-2xl mb-8 text-center relative">
            <h1 className="text-4xl font-bold text-slate-800">insighte payout generator</h1>
            <p className="text-slate-600 mt-2">Securely access your monthly earnings report.</p>
            <button 
              onClick={() => setIsAdminPanelOpen(true)}
              className="absolute top-0 right-0 p-2 text-slate-500 hover:text-purple-600 transition-colors"
              aria-label="Open admin settings"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </button>
        </header>
        <main className={`w-full ${appState === AppState.DASHBOARD || appState === AppState.VIEW_PAYSLIP ? 'max-w-4xl' : 'max-w-lg'}`}>
            <div className="bg-white rounded-xl shadow-lg p-6 sm:p-8 transition-all duration-300">
                {renderContent()}
            </div>
        </main>
        <footer className="mt-8 text-center text-slate-500 text-sm">
            <p>&copy; {new Date().getFullYear()} Insighte Childcare Private Limited. All rights reserved.</p>
        </footer>
        <AdminPanel isOpen={isAdminPanelOpen} onClose={() => setIsAdminPanelOpen(false)} />
    </div>
  );
}

export default App;
