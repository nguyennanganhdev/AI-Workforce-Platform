import {
	Blocks,
	Calculator,
	Car,
	ConciergeBell,
	Crown,
	Headset,
	type LucideIcon,
	MapPin,
	Wrench,
} from 'lucide-react';

import robotStill from '@/assets/images/stickers/robot-still.webp';
import robot from '@/assets/images/stickers/robot.webp';

/**
 * The agent stickers.
 *
 * Every agent is the same animated robot — Microsoft's Fluent "Robot" emoji
 * (MIT; see `assets/images/stickers/LICENSE-fluentui-emoji.txt`) — because no
 * free set draws a different animated robot per job. What tells agents apart
 * is the tile's colour and a badge in its corner: a crown for the Leader, a
 * wrench for the technician, a bell for the hotel agent, and so on.
 *
 * So the badge is chosen by ROLE, not by a hash. `portraitFor` matches on what
 * the agent is called, in Vietnamese and in English, and falls back to a plain
 * robot with no badge when nothing matches rather than guess a role the agent
 * does not have.
 *
 * It is a robot, not a person, on purpose: these marks stand for agents, and a
 * human face would say a person is on the other end.
 *
 * The drawing is decorative wherever it is used: the name is always rendered
 * beside it, so each sticker is `aria-hidden`.
 */

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

type Role = {
	/** The tile's ground. */
	bg: string;
	/** The badge's fill, a deeper step of the same hue. */
	badge: string;
	icon: LucideIcon;
};

const ROLES: Record<Exclude<PortraitKey, 'generic'>, Role> = {
	// The one that picks who joins.
	leader: { bg: '#c1d2ff', badge: '#536ddf', icon: Crown },
	planner: { bg: '#ffe9b8', badge: '#c98a1c', icon: MapPin },
	hotel: { bg: '#eed5f7', badge: '#9770c5', icon: ConciergeBell },
	car: { bg: '#d3ecff', badge: '#3d8fd1', icon: Car },
	calculator: { bg: '#d8f5d0', badge: '#4f9e5b', icon: Calculator },
	technician: { bg: '#b0e7d9', badge: '#258a85', icon: Wrench },
	// The one that makes other agents.
	builder: { bg: '#ffd9c7', badge: '#e07a4d', icon: Blocks },
	reception: { bg: '#ffd6e4', badge: '#d86a94', icon: Headset },
};

/** Grounds for agents whose name says nothing about their role. */
const GENERIC_GROUNDS = ['#aec4ff', '#9ce3d5', '#ffc0a7'];

/**
 * The words that pick each sticker, Vietnamese first because the product is
 * Vietnamese. Ordered most specific first and matched in order. These are
 * substrings of a lowercased label, not whole words, because agent names are
 * phrases ("Agent Kỹ thuật", "Hotel Agent") rather than tags.
 */
const ROLE_WORDS: [Exclude<PortraitKey, 'generic'>, string[]][] = [
	['leader', ['leader', 'điều phối', 'dieu phoi', 'supervisor', 'trưởng nhóm']],
	[
		'builder',
		['builder', 'factory', 'tạo agent', 'tao agent', 'tạo nhiều agent', 'xây agent'],
	],
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
		['tính chi phí', 'tinh chi phi', 'ngân sách', 'ngan sach', 'calculator', 'budget'],
	],
	[
		'hotel',
		['khách sạn', 'khach san', 'lưu trú', 'luu tru', 'đặt phòng', 'hotel', 'lodging'],
	],
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
	const needle = label.toLowerCase();
	for (const [key, words] of ROLE_WORDS) {
		if (words.some((word) => needle.includes(word))) return key;
	}
	return 'generic';
}

/**
 * One sticker, `size` pixels square: the robot on its role's ground, with the
 * role's badge in the bottom-right corner.
 *
 * The robot blinks and wiggles its antennas on a two-second loop. Anyone who
 * has asked their system for reduced motion gets the still frame instead.
 */
export function ClayPortrait({
	className,
	size,
	which,
	variant = 0,
}: {
	className?: string;
	size: number;
	which: PortraitKey;
	/** Picks the ground of a `generic` robot, so plain agents still differ. */
	variant?: number;
}) {
	const role = which === 'generic' ? null : ROLES[which];
	const badge = Math.round(size * 0.42);
	return (
		<span
			aria-hidden="true"
			className={className}
			style={{
				position: 'relative',
				display: 'block',
				width: size,
				height: size,
				background: role?.bg ?? GENERIC_GROUNDS[variant % GENERIC_GROUNDS.length],
			}}
		>
			<picture>
				<source media="(prefers-reduced-motion: reduce)" srcSet={robotStill} />
				<img
					alt=""
					draggable={false}
					src={robot}
					// Nudged up and left of centre, away from the badge.
					style={{
						position: 'absolute',
						top: '4%',
						left: '6%',
						width: '84%',
						height: '84%',
					}}
				/>
			</picture>
			{role && (
				<span
					style={{
						position: 'absolute',
						right: 1,
						bottom: 1,
						display: 'flex',
						alignItems: 'center',
						justifyContent: 'center',
						width: badge,
						height: badge,
						borderRadius: '50%',
						background: role.badge,
						boxShadow: '0 0 0 1.5px #ffffff',
					}}
				>
					{/* `style`, because `index.css` sets a stroke width on every
					    lucide icon and a rule outranks the attribute. */}
					<role.icon
						color="#ffffff"
						size={Math.round(badge * 0.64)}
						style={{ strokeWidth: 2.6 }}
					/>
				</span>
			)}
		</span>
	);
}
