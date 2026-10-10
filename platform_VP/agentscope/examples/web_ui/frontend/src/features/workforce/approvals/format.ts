import type { MoneyView } from './types';

export function formatMoney(money: MoneyView): string {
	const formatter = new Intl.NumberFormat('vi-VN', {
		style: 'currency',
		currency: money.currency,
	});
	const digits = formatter.resolvedOptions().maximumFractionDigits ?? 0;
	if (!Number.isSafeInteger(money.amount_minor)) return 'Số tiền vượt giới hạn hiển thị';
	return formatter.format(money.amount_minor / 10 ** digits);
}
