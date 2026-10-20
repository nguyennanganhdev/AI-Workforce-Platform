import type { CSSProperties } from 'react';

import coordinator from '@/assets/images/frame/coordinator-sprite.png';
import planner from '@/assets/images/frame/planner-sprite.png';
import technician from '@/assets/images/frame/technician-sprite.png';

import calculator from '@/assets/images/frame/calculator-sprite.png';

import receptionFrames from '@/assets/images/frame/Chibi Robot Waving Animation Sprite Sheet.png';

import './clay-portrait.css';

export type PortraitKey =
	| 'leader'
	| 'planner'
	| 'hotel'
	| 'car'
	| 'calculator'
	| 'technician'
	| 'builder'
	| 'reception'
	| 'generic';

/** Related roles share artwork until a dedicated portrait is supplied. */
const PORTRAITS: Record<PortraitKey, string> = {
	leader: coordinator,
	planner,
	technician,
	reception: receptionFrames,
	calculator,
	hotel: receptionFrames,
	car: planner,
	builder: technician,
	generic: coordinator,
};

/**
 * The words that pick each sticker, Vietnamese first because the product is
 * Vietnamese. Ordered most specific first and matched in order. These are
 * substrings of a lowercased label, not whole words, because agent names are
 * phrases ("Agent Kỹ thuật", "Hotel Agent") rather than tags.
 */
const ROLE_WORDS: [Exclude<PortraitKey, 'generic'>, string[]][] = [
	['leader', ['leader', 'agent group', 'điều phối', 'dieu phoi', 'supervisor', 'trưởng nhóm']],
	['builder', ['builder', 'factory', 'tạo agent', 'tao agent', 'tạo nhiều agent', 'xây agent']],
	[
		'technician',
		[
			'kỹ thuật',
			'ky thuat',
			'bảo trì',
			'bao tri',
			'sửa',
			'sua chua',
			'điện nước',
			'thiết bị',
			'technical',
			'technician',
			'maintenance',
			'repair',
		],
	],
	[
		'calculator',
		[
			'tính toán',
			'tinh toan',
			'tính chi phí',
			'tinh chi phi',
			'ngân sách',
			'ngan sach',
			'calculator',
			'calculation',
			'budget',
		],
	],
	['hotel', ['khách sạn', 'khach san', 'lưu trú', 'luu tru', 'đặt phòng', 'hotel', 'lodging']],
	[
		'car',
		['agent xe', 'thuê xe', 'đặt xe', 'xe đưa đón', 'di chuyển', 'vận chuyển', 'car', 'ride'],
	],
	[
		'planner',
		[
			'kế hoạch',
			'ke hoach',
			'lịch trình',
			'chuyến đi',
			'du lịch',
			'du lich',
			'planner',
			'plan',
			'travel',
		],
	],
	[
		'reception',
		[
			'lễ tân',
			'le tan',
			'tiếp nhận',
			'tiep nhan',
			'cư dân',
			'cu dan',
			'hỗ trợ',
			'ho tro',
			'reception',
			'support',
			'helpdesk',
			'intake',
		],
	],
];

/**
 * Which sticker an agent gets, read from what it is CALLED — the only thing
 * that carries the role. No match is `generic`, never a guessed role.
 */
export function portraitFor(label: string): PortraitKey {
	const needle = label.normalize('NFC').toLowerCase().replace(/[_-]+/g, ' ');
	for (const [key, words] of ROLE_WORDS) {
		if (words.some((word) => needle.includes(word))) return key;
	}
	return 'generic';
}

/** Display the supplied artwork as a head-and-shoulders avatar. */
export function ClayPortrait({
	className,
	size,
	which,
	working = false,
}: {
	className?: string;
	size: number;
	which: PortraitKey;
	working?: boolean;
}) {
	return (
		<span
			aria-hidden="true"
			data-working={working || undefined}
			className={`agent-sprite ${className ?? ''}`}
			style={
				{
					width: size,
					height: size,
					backgroundImage: `url("${PORTRAITS[which]}")`,
					'--blink-delay': `${-(size % 5)}s`,
				} as CSSProperties
			}
		/>
	);
}
