import { useTexture } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import { useEffect, useMemo } from 'react';
import { SRGBColorSpace } from 'three';

import { portraitFor, portraitSheetFor, SHEET } from '@/components/ui/clay-portrait';

/**
 * One agent as a camera-facing character cut from its animation sheet
 * (4 columns × 3 rows). Frames 1–4 blink; frames 5–12 are the role action,
 * played while the agent is working. Each actor clones the texture so two
 * agents sharing artwork animate on their own.
 */
export default function AgentSprite3D({
	name,
	leader,
	working,
	motion,
	opacity,
}: {
	name: string;
	leader: boolean;
	working: boolean;
	motion: boolean;
	opacity: number;
}) {
	const source = useTexture(portraitSheetFor(leader ? 'leader' : portraitFor(name)));
	const texture = useMemo(() => {
		const copy = source.clone();
		copy.colorSpace = SRGBColorSpace;
		copy.anisotropy = 4;
		copy.repeat.set(1 / SHEET.columns, 1 / SHEET.rows);
		copy.offset.set(0, (SHEET.rows - 1) / SHEET.rows);
		return copy;
	}, [source]);
	useEffect(() => () => texture.dispose(), [texture]);
	useFrame(({ clock }) => {
		const time = clock.elapsedTime;
		let frame = 0;
		if (motion && working) {
			frame = 4 + (Math.floor(time * 4) % 8);
		} else if (motion) {
			// A blink every 5.8 s: frames 2–4 over the last 0.4 s.
			const blink = time % 5.8;
			if (blink >= 5.4) frame = Math.min(3, 1 + Math.floor((blink - 5.4) * 7.5));
		}
		texture.offset.set((frame % SHEET.columns) / SHEET.columns, (SHEET.rows - 1 - Math.floor(frame / SHEET.columns)) / SHEET.rows);
	});
	const size = leader ? 3.1 : 2.6;
	return (
		<sprite position={[0, size / 2 + 0.18, 0]} scale={[size, size, 1]}>
			{/* Writes depth (alphaTest cuts the clear pixels) so the floor glow never washes out a far character. */}
			<spriteMaterial map={texture} transparent opacity={opacity} alphaTest={0.08} toneMapped={false} />
		</sprite>
	);
}
