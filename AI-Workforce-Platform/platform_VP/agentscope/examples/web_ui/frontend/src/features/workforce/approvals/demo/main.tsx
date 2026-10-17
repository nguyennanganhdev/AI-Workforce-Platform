// LOCAL DEMO ONLY: never imported by the application router or production barrel.
/* eslint-disable react-refresh/only-export-components -- Standalone demo entry point. */
import { useState } from 'react';
import { createRoot } from 'react-dom/client';

import { WorkforceApprovalCard } from '../ApprovalCard';
import { WorkforceExecutionStatus } from '../ExecutionStatus';
import { WorkforceExternalOperationStatus } from '../external_operations';
import type { ApprovalView } from '../types';

import '@/index.css';

const approval: ApprovalView = {
	approval_id: 'DEMO-A',
	call_id: 'DEMO-call',
	status: 'pending',
	arguments_hash: 'DEMO-args',
	quote_hash: 'DEMO-quote',
	expires_at: new Date(Date.now() + 600000).toISOString(),
	quote: {
		provider: 'Khách sạn GIẢ LẬP',
		option: 'Phòng view biển (GIẢ LẬP)',
		dates: ['10/10/2026', '11/10/2026'],
		amount: { amount_minor: 5000000, currency: 'VND' },
		fees: { amount_minor: 100000, currency: 'VND' },
		cancellation_terms: 'Không hoàn tiền — dữ liệu demo',
		quote_ref: 'DEMO-quote',
		quote_version: '1',
	},
	decision_history: [],
};

function Demo() {
	const [fail, setFail] = useState(false);
	const [ticket, setTicket] = useState('A');
	const [count, setCount] = useState(0);
	return (
		<main className="mx-auto max-w-xl space-y-4 p-6">
			<h1 className="text-xl font-bold">DEMO kiểm tra ApprovalCard</h1>
			<p>Chỉ dữ liệu giả lập. Không gọi API, thanh toán hoặc nhà cung cấp thật.</p>
			<label className="flex gap-2">
				<input type="checkbox" checked={fail} onChange={(e) => setFail(e.target.checked)} />
				Mô phỏng lỗi gửi
			</label>
			<button
				type="button"
				className="underline"
				onClick={() => setTicket(ticket === 'A' ? 'B' : 'A')}
			>
				Chuyển ticket {ticket === 'A' ? 'B' : 'A'}
			</button>
			<p>Số callback: {count}</p>
			<WorkforceApprovalCard
				approval={{ ...approval, approval_id: `DEMO-${ticket}` }}
				canDecide
				onDecide={async () => {
					setCount((current) => current + 1);
					await new Promise((resolve) => window.setTimeout(resolve, 1500));
					if (fail) throw new Error('DEMO simulated failure');
				}}
			/>
			<WorkforceApprovalCard
				approval={{
					...approval,
					approval_id: 'DEMO-expired',
					expires_at: '2026-01-01T00:00:00Z',
				}}
				canDecide
				onDecide={async () => {
					throw new Error('Expired approval must be disabled');
				}}
			/>
			<WorkforceExecutionStatus status="unknown" />
			<WorkforceExecutionStatus status="partial" />
			<WorkforceExternalOperationStatus
				operation={{
					creation_status: 'succeeded',
					job_status: 'assigned',
					external_job_id: 'DEMO-job',
					pending: true,
				}}
				progressLabel="Đã phân công (GIẢ LẬP)"
			/>
		</main>
	);
}

createRoot(document.getElementById('root')!).render(<Demo />);
