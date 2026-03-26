
export interface Employee {
  employeeId: string;
  name: string;
  email: string;
  role?: 'Consultant' | 'Employee';
}

export interface PayslipRecord {
  id: string; // Unique ID for the payslip record (e.g., empId-month-year)
  employeeId: string;
  month: string;
  year: number;
  grossPay: number;
  tds: number;
  netPay: number;
  baseSalary?: number;
  allowance?: number;
  reference?: string;
}

export enum AppState {
  SELECT_EMPLOYEE,
  VERIFY_STAFF_ID,
  DASHBOARD,
  VIEW_PAYSLIP,
}
