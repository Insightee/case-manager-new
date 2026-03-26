
export const getCurrentMonthYear = (): string => {
  const now = new Date();
  return `${now.toLocaleString('default', { month: 'long' })} ${now.getFullYear()}`;
};

export const getLast12Months = (): { value: string; label: string }[] => {
  const months = [];
  const currentDate = new Date();
  for (let i = 0; i < 12; i++) {
    const date = new Date(currentDate.getFullYear(), currentDate.getMonth() - i, 1);
    const monthName = date.toLocaleString('default', { month: 'long' });
    const year = date.getFullYear();
    const label = `${monthName} ${year}`;
    months.push({ value: label, label: label });
  }
  return months;
};

export const getMonthNumber = (monthName: string): number => {
  const date = new Date(`${monthName} 1, 2000`);
  return date.getMonth();
}
