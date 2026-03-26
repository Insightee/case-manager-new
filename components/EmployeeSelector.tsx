
import React, { useState } from 'react';
import { Employee } from '../types';

interface EmployeeSelectorProps {
  employees: Employee[];
  onSelect: (employeeId: string) => void;
}

const EmployeeSelector: React.FC<EmployeeSelectorProps> = ({ employees, onSelect }) => {
  const [selectedId, setSelectedId] = useState<string>('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedId) {
      onSelect(selectedId);
    }
  };
  
  const sortedEmployees = [...employees].sort((a, b) => a.name.localeCompare(b.name));

  const selectStyles = "appearance-none block w-full px-4 py-3 bg-white text-black border border-slate-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500 text-base";
  const customArrow = `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`;

  return (
    <div className="space-y-6 animate-fade-in">
      <h2 className="text-2xl font-semibold text-center text-slate-700">Therapist Portal</h2>
      <p className="text-center text-slate-500">Please select your name to login.</p>
      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label htmlFor="employee-select" className="block text-sm font-medium text-slate-600 mb-1">
            Staff / Consultant Name
          </label>
           <div className="relative">
            <select
              id="employee-select"
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              className={selectStyles}
              style={{ backgroundImage: customArrow, backgroundRepeat: 'no-repeat', backgroundPosition: 'right 0.75rem center', backgroundSize: '1.5em 1.5em' }}
            >
              <option value="" disabled>-- Select Staff / Consultant --</option>
              {sortedEmployees.map((employee) => (
                <option key={employee.employeeId} value={employee.employeeId}>
                  {employee.name}
                </option>
              ))}
            </select>
          </div>
        </div>
        <button
          type="submit"
          disabled={!selectedId}
          className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-base font-medium text-white bg-purple-600 hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 disabled:bg-purple-300 disabled:cursor-not-allowed transition-colors"
        >
          Continue
        </button>
      </form>
    </div>
  );
};

export default EmployeeSelector;
