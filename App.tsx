
import React, { useState, useCallback, useMemo, useEffect } from 'react';
import { Employee, AppState, PayslipRecord } from './types';
import { insighteLogo } from './assets/logo';
import { supabase } from './utils/supabase';
import EmployeeSelector from './components/EmployeeSelector';
import OtpInput from './components/OtpInput';
import Payslip from './components/Payslip';
import Dashboard from './components/Dashboard';

function App() {
  const [appState, setAppState] = useState<AppState>(AppState.SELECT_EMPLOYEE);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [payouts, setPayouts] = useState<PayslipRecord[]>([]);
  const [selectedEmployee, setSelectedEmployee] = useState<Employee | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<PayslipRecord | null>(null);
  const [error, setError] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);

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
  }, []); // Only on mount

  // Fetch payouts only for the selected employee (on-demand)
  const fetchPayoutsForEmployee = useCallback(async (employeeId: string) => {
    try {
        const { data: payData, error: payError } = await supabase
            .from('payouts')
            .select('*')
            .eq('employee_id', employeeId)
            .order('year', { ascending: false });
        if (payError) throw payError;

        const safeParse = (val: any) => {
          if (typeof val === 'number') return val;
          if (!val) return 0;
          const parsed = parseFloat(String(val).replace(/[^0-9.-]/g, ''));
          return isNaN(parsed) ? 0 : parsed;
        };

        setPayouts(payData.map(p => ({
            id: p.id,
            employeeId: p.employee_id,
            month: p.month,
            year: p.year,
            grossPay: safeParse(p.gross_pay),
            tds: safeParse(p.tds),
            netPay: safeParse(p.net_pay)
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
    <div className="min-h-screen flex flex-col items-center justify-start py-12 px-4 selection:bg-indigo-500/30">
        <header className="w-full max-w-2xl mb-12 text-center relative animate-fade-in group">
            <div className="inline-block p-5 rounded-[2.5rem] bg-white/5 backdrop-blur-xl mb-8 border border-white/10 transition-all duration-500 group-hover:scale-110 group-hover:bg-white/10 group-hover:border-white/20">
               <img src={insighteLogo} alt="Insighte Logo" className="h-10 w-auto object-contain brightness-110" />
            </div>
            <h1 className="text-5xl sm:text-6xl font-black tracking-tight font-heading mb-4">
              <span className="text-white drop-shadow-sm">payout</span>
              <span className="brand-gradient"> portal</span>
            </h1>
            <p className="text-indigo-200/50 font-bold max-w-sm mx-auto leading-relaxed uppercase tracking-[0.4em] text-[10px]">
              SECURE EARNINGS ACCESS
            </p>
            
        </header>
        <main className={`w-full animate-fade-in ${appState === AppState.DASHBOARD || appState === AppState.VIEW_PAYSLIP ? 'max-w-6xl' : 'max-w-xl'}`}>
            <div className="glass-card rounded-[2.5rem] shadow-[0_30px_60px_-15px_rgba(0,0,0,0.6)] transition-all duration-500">
                <div className="p-6 sm:p-10">
                  {renderContent()}
                </div>
            </div>
        </main>
        <footer className="mt-16 mb-20 text-center text-slate-500 text-xs font-semibold uppercase tracking-widest animate-fade-in" style={{ animationDelay: '200ms' }}>
            <p>&copy; {new Date().getFullYear()} Insighte Childcare Private Limited</p>
        </footer>
    </div>
  );
}

export default App;
