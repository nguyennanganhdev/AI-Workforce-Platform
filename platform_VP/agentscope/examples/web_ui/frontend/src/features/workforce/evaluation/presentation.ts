import type { TestReport, TestResult } from '@/api';

/** An unavailable environment/model is inconclusive, even in a contradictory legacy report. */
export function isInconclusive(result: TestResult): boolean {
	return Boolean(result.error) || result.status === 'error';
}

export function canPresentPublishable(report: TestReport): boolean {
	return report.publishable && !report.errors && !report.model_error
		&& report.environment?.cleanup?.status !== 'pending' && !(report.results ?? []).some(isInconclusive);
}

export function executionLabel(call: TestResult['tool_calls'][number]): string {
	if (call.mode === 'error' || call.error_code) return 'Lỗi công cụ';
	if (call.mode === 'sandbox') return call.executed ? 'Chạy thật trong sandbox' : 'Chưa thực thi trong sandbox';
	if (call.mode === 'simulated') return 'Mô phỏng, không ghi dữ liệu';
	return call.executed ? 'Đọc thật' : 'Chưa thực thi';
}
