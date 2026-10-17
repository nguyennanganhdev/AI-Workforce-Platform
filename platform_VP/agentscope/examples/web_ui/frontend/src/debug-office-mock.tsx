// TEMPORARY MOCK (4 agents + 1 Leader) for reviewing the 3D office. Delete with debug-office-mock.html.
import { StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';

import './index.css';
import './i18n';
import { TooltipProvider } from '@/components/ui/tooltip';
import type { SessionOfficeSnapshot } from '@/features/workforce/session-office/model';
import { AgentOffice } from '@/pages/agents/AgentOffice';

type Who = 'leader' | 'reception' | 'technical' | 'plumbing' | 'hotel' | 'customer';
const PEOPLE: { id: Exclude<Who, 'customer'>; name: string; role: string }[] = [
	{ id: 'leader', name: 'Leader', role: 'Điều phối' },
	{ id: 'reception', name: 'Lễ tân', role: 'Tiếp nhận yêu cầu' },
	{ id: 'technical', name: 'Kỹ thuật', role: 'Sửa chữa kỹ thuật' },
	{ id: 'plumbing', name: 'Điện nước', role: 'Điện, nước' },
	{ id: 'hotel', name: 'Khách sạn', role: 'Đặt phòng' },
];
const NAME: Record<Who, string> = {
	customer: 'Cư dân',
	...Object.fromEntries(PEOPLE.map((p) => [p.id, p.name])),
} as Record<Who, string>;

type Step = {
	label: string;
	phase: SessionOfficeSnapshot['phase'];
	status: string;
	active: Who | null;
	called: Who[];
	reported: Who[];
	/** Who walked to whom: [from, to]. */
	exchanges: [Who, Who][];
	line?: [Who, string];
	/** How long auto-play stays on this step. */
	ms: number;
};
const STEPS: Step[] = [
	{ label: 'Chờ', phase: 'idle', status: 'Sẵn sàng', active: null, called: [], reported: [], exchanges: [], ms: 3000 },
	{ label: 'Cư dân gửi', phase: 'work', status: 'Đang xử lý', active: 'leader', called: [], reported: [], exchanges: [], line: ['customer', 'Nhà tôi bị vỡ ống nước, trần căn dưới bị thấm.'], ms: 3000 },
	{ label: 'Gọi Điện nước', phase: 'work', status: 'Đang xử lý', active: 'leader', called: ['plumbing'], reported: [], exchanges: [], line: ['leader', 'Giao việc cho Điện nước: xử lý ống nước vỡ tại A-1203.'], ms: 1500 },
	{ label: 'Gọi Kỹ thuật', phase: 'work', status: 'Đang xử lý', active: 'leader', called: ['plumbing', 'technical'], reported: [], exchanges: [], line: ['leader', 'Giao việc cho Kỹ thuật: kiểm tra trần thấm căn A-1103.'], ms: 18000 },
	{ label: 'Điện nước báo diễn biến', phase: 'work', status: 'Đang xử lý', active: 'leader', called: ['plumbing', 'technical'], reported: [], exchanges: [], line: ['plumbing', 'Đang tìm thợ, cần hỏi Kỹ thuật vị trí van tổng.'], ms: 3000 },
	{ label: 'Điện nước hỏi Kỹ thuật', phase: 'work', status: 'Đang xử lý', active: 'leader', called: ['plumbing', 'technical'], reported: [], exchanges: [['plumbing', 'technical']], line: ['technical', 'Van tổng A-1203 ở hộp kỹ thuật cạnh thang máy.'], ms: 13000 },
	{ label: 'Điện nước báo cáo', phase: 'work', status: 'Đang xử lý', active: 'leader', called: ['plumbing', 'technical'], reported: ['plumbing'], exchanges: [['plumbing', 'technical']], line: ['plumbing', 'Đã xếp thợ, 15 phút nữa có mặt. Cần cư dân khoá van tổng.'], ms: 4000 },
	{ label: 'Kỹ thuật báo cáo', phase: 'work', status: 'Đang xử lý', active: 'leader', called: ['plumbing', 'technical'], reported: ['plumbing', 'technical'], exchanges: [['plumbing', 'technical']], line: ['technical', 'Trần A-1103 thấm nhẹ, sẽ xử lý sau khi sửa ống.'], ms: 4000 },
	{ label: 'Chờ duyệt', phase: 'approval', status: 'Chờ bạn duyệt', active: null, called: ['plumbing', 'technical'], reported: ['plumbing', 'technical'], exchanges: [['plumbing', 'technical']], line: ['leader', 'Gửi cư dân: thợ đến trong 15 phút, vui lòng khoá van tổng.'], ms: 16000 },
	{ label: 'Hoàn tất', phase: 'done', status: 'Hoàn tất', active: null, called: ['plumbing', 'technical'], reported: ['plumbing', 'technical'], exchanges: [['plumbing', 'technical']], ms: 6000 },
];

function snapshot(index: number): SessionOfficeSnapshot {
	const step = STEPS[index];
	const lines = STEPS.slice(0, index + 1).flatMap((s) => (s.line ? [s.line] : []));
	const last = lines.at(-1);
	const working = step.phase === 'work';
	return {
		id: 'mock',
		source: 'mock',
		motion: 'events',
		statusLabel: step.status,
		// As officeFromSession: the active agent and called members still on it work;
		// only the last speaker talks.
		participants: PEOPLE.map((p) => ({
			...p,
			status:
				working && (step.active === p.id || (step.called.includes(p.id) && !step.reported.includes(p.id)))
					? 'working'
					: 'idle',
			message: last && last[0] === p.id && step.phase !== 'done' ? last[1] : undefined,
		})),
		phase: step.phase,
		turn: index === 0 ? '0' : '1',
		called: step.called,
		exchanges: step.exchanges.map(([from, to]) => ({ from, to })),
		hostId: 'leader',
		activity: lines.map(([who, text], i) => ({ id: String(i), text: `${NAME[who]}: ${text}` })).slice(-6),
	};
}

function Mock() {
	const [index, setIndex] = useState(0);
	const [auto, setAuto] = useState(true);
	useEffect(() => {
		// Plays one request once and stops at the end; looping would read as a second meeting.
		if (!auto || index === STEPS.length - 1) return;
		const timer = setTimeout(() => setIndex((i) => i + 1), STEPS[index].ms);
		return () => clearTimeout(timer);
	}, [auto, index]);
	return (
		<div style={{ position: 'absolute', inset: 0 }}>
			<AgentOffice agents={[]} session={snapshot(index)} onChat={() => {}} onEdit={() => {}} />
			<div style={{ position: 'absolute', left: '50%', bottom: 16, transform: 'translateX(-50%)', display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'center', padding: 6, borderRadius: 999, background: 'rgba(255,255,255,0.92)', boxShadow: '0 2px 8px rgba(0,0,0,0.08)', fontSize: 12, zIndex: 10 }}>
				<b style={{ alignSelf: 'center', padding: '0 8px', color: '#8a5a00' }}>MOCK</b>
				{STEPS.map((s, i) => (
					<button key={s.label} type="button" onClick={() => { setAuto(false); setIndex(i); }}
						style={{ padding: '6px 10px', borderRadius: 999, background: i === index ? '#24262d' : 'transparent', color: i === index ? '#fff' : '#333' }}>
						{i + 1}. {s.label}
					</button>
				))}
				<button type="button" onClick={() => setAuto((a) => !a)} style={{ padding: '6px 10px', borderRadius: 999, border: '1px solid #ddd' }}>
					{auto ? '⏸ Tự chạy' : '▶ Tự chạy'}
				</button>
				<button type="button" onClick={() => { setIndex(0); setAuto(true); }} style={{ padding: '6px 10px', borderRadius: 999, border: '1px solid #ddd' }}>
					↺ Chạy lại
				</button>
			</div>
		</div>
	);
}

createRoot(document.getElementById('root')!).render(
	<StrictMode>
		<TooltipProvider>
			<Mock />
		</TooltipProvider>
	</StrictMode>,
);
