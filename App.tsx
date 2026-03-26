
import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { Employee, AppState, PayslipRecord } from './types';
import { insighteLogo } from './assets/logo';
import { supabase } from './utils/supabase';
import EmployeeSelector from './components/EmployeeSelector';
import OtpInput from './components/OtpInput';
import Payslip from './components/Payslip';
import AdminPanel from './components/AdminPanel';
import Dashboard from './components/Dashboard';

function App() {
  const [appState, setAppState] = useState<AppState>(AppState.SELECT_EMPLOYEE);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [payouts, setPayouts] = useState<PayslipRecord[]>([]);
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<PayslipRecord | null>(null);
  const [error, setError] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isAdminPanelOpen, setIsAdminPanelOpen] = useState<boolean>(false);

  // Fetch employees on mount
  useEffect(() => {
    const fetchEmployees = async () => {
        setIsLoading(true);
        try {
            const { data: empData, error: empError } = await supabase
                .from('employees')
                .select('employee_id, name, email, role')
                .order('name');
            if (empError) throw empError;
            
            setEmployees(empData.map(e => ({
                employeeId: e.employee_id,
                name: e.name,
                email: e.email,
                role: e.role
            })));
        } catch (err: any) {
            setError('Failed to sync with secure vault.');
            console.error(err);
        } finally {
            setIsLoading(false);
        }
    };
    fetchEmployees();
  }, [isAdminPanelOpen]); // Re-fetch if admin panel closed (might have added data)

  // Fetch payouts only for the selected employee (on-demand)
  const fetchPayoutsForEmployee = useCallback(async (employeeId: string) => {
    try {
        const { data: payData, error: payError } = await supabase
            .from('payouts')
            .select('*')
            .eq('employee_id', employeeId)
            .order('year', { ascending: false });
        if (payError) throw payError;

        setPayouts(payData.map(p => ({
            id: p.id,
            employeeId: p.employee_id,
            month: p.month,
            year: p.year,
            grossPay: parseFloat(p.gross_pay),
            tds: parseFloat(p.tds),
            netPay: parseFloat(p.net_pay)
        })));
    } catch (err: any) {
        console.error('Failed to fetch payouts:', err);
        setPayouts([]);
    }
  }, []);

  const handleSelectEmployee = useCallback((employeeId: string) => {
    const employee = employees.find(e => e.employeeId === employeeId);
    if (employee) {
      setSelectedEmployee(employee);
      setError('');
      setAppState(AppState.VERIFY_STAFF_ID);
    } else {
      setError('Identity not verified in records.');
    }
  }, [employees]);

  const handleVerifyStaffId = useCallback(async (staffId: string) => {
    if (selectedEmployee && staffId === selectedEmployee.employeeId) {
      setError('');
      await fetchPayoutsForEmployee(selectedEmployee.employeeId);
      setAppState(AppState.DASHBOARD);
    } else {
      setError('Verification failed. Invalid ID.');
    }
  }, [selectedEmployee, fetchPayoutsForEmployee]);

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

  const employeeRecords = useMemo(() => {
    if (!selectedEmployee) return [];
    return payouts.filter(r => r.employeeId === selectedEmployee.employeeId);
  }, [selectedEmployee, payouts]);

  const renderContent = () => {
    if (isLoading) {
        return (
            <div className="flex flex-col items-center justify-center py-20 space-y-4">
                <div className="w-12 h-12 border-4 border-indigo-100 border-t-indigo-600 rounded-full animate-spin"></div>
                <p className="text-slate-400 font-bold text-[10px] tracking-widest uppercase animate-pulse">Synchronizing Security Keys...</p>
            </div>
        );
    }

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
    <div className="min-h-screen flex flex-col items-center justify-start py-12 px-4 selection:bg-indigo-100">
        <header className="w-full max-w-2xl mb-12 text-center relative animate-fade-in group">
            <div className="inline-block p-4 rounded-3xl bg-white shadow-xl mb-6 border border-slate-50 transition-transform group-hover:scale-110 duration-500">
               <img src={insighteLogo} alt="Insighte Logo" className="h-12 w-auto object-contain" />
            </div>
            <h1 className="text-4xl sm:text-5xl font-black tracking-tight font-heading mb-3">
              <span className="text-slate-900">payout</span>
              <span className="brand-gradient"> portal</span>
            </h1>
            <p className="text-slate-500 font-bold max-w-sm mx-auto leading-relaxed uppercase tracking-[0.3em] text-[10px] opacity-60">
              SECURE EARNINGS ACCESS
            </p>
            
            <button 
              onClick={() => setIsAdminPanelOpen(true)}
              className="absolute -top-4 -right-4 p-3 rounded-full text-slate-400 hover:text-indigo-600 hover:bg-white hover:shadow-md transition-all duration-300 group"
              aria-label="Open admin settings"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 group-hover:rotate-90 transition-transform duration-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </button>
        </header>
        <main className={`w-full animate-fade-in ${appState === AppState.DASHBOARD || appState === AppState.VIEW_PAYSLIP ? 'max-w-5xl' : 'max-w-xl'}`}>
            <div className="glass-card rounded-3xl shadow-[0_8px_30px_rgb(0,0,0,0.04)] overflow-hidden transition-all duration-500">
                <div className="p-6 sm:p-10">
                  {renderContent()}
                </div>
            </div>
        </main>
        <footer className="mt-16 text-center text-slate-400 text-sm font-medium animate-fade-in" style={{ animationDelay: '200ms' }}>
            <p>&copy; {new Date().getFullYear()} Insighte Childcare Private Limited</p>
        </footer>
        <AdminPanel isOpen={isAdminPanelOpen} onClose={() => setIsAdminPanelOpen(false)} />
    </div>
  );
}

export default App;
