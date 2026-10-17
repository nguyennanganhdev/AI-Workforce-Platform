# Agent animation sheets

Created with the built-in imagegen tool, using the corresponding supplied image in `../agent/` as the character reference. The original receptionist sheet was supplied by the user.

## Shared prompt

Create a production animation sprite sheet of the EXACT robot character in reference. Preserve its clothing, face, colors, accessories and shaded outlined cartoon illustration style. 12 frames, exactly 4 equal columns x 3 equal rows, row-major. Transparent background, no text, no labels, no grid lines. Fixed camera, identical character scale and center in each square cell; full body, generous consistent padding. Row 1 frames 1–4: open eyes, half closed eyelids, closed eyes, open. Frames 5–12: perform the role action below. Last frame returns to first pose for seamless loop. Only relevant arms/eyes/head move subtly, feet and torso stay registered. No additional limbs, no camera motion.

## Actions and references

- `coordinator-sprite.png` — `Dieu_phoi.jpeg`: gently raise walkie-talkie toward mouth, tilt head slightly listening, lower it back to starting pose; preserve cream head, navy jacket and orange accent.
- `technician-sprite.png` — `Ky_Thuat.png`: raise and turn the wrench gently, then return; preserve orange helmet and clear goggles.
- `planner-sprite.png` — `Ke_hoach.png`: look down slightly and write short strokes with pencil in notebook, then return; preserve round glasses.
- `calculator-sprite.png` — `Tinh_toan.png`: tap calculator buttons with one hand, glance down then return; preserve square head and rectangular glasses.

## Playback

`clay-portrait.css` displays upper-body windows of the sheets. Idle playback uses the first row for blinking; hover plays the action once; `working` repeats the action. Reduced-motion preferences disable playback. Artwork is generated, so small changes in proportions between frames can remain.
