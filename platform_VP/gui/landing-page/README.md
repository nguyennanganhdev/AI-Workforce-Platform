# VAgents landing page

Vietnamese landing page inside `platform_VP/gui/landing-page`, built with
React, Vite, TypeScript, Tailwind CSS, Framer Motion, GSAP ScrollTrigger and Lenis.
White Platform surfaces, orange accents and the supplied transparent mascots.
Be Vietnam Pro and JetBrains Mono are self-hosted through Fontsource.
Lucide icons use a consistent 1.8 stroke width. There is no Next.js dependency.

## Local development

```powershell
npm install
npm run dev
```

Development: `http://127.0.0.1:5186/landing-assets/`.
Production preview: `npm run build`, then `npm run preview` and open
`http://127.0.0.1:5186/landing-assets/`. Signup buttons open `/register`, which is served by
the existing Platform frontend on the deployed domain.

## Verification

```powershell
npm run build
npx playwright install chromium
$env:LANDING_IMAGE = 'vagents-landing:20261017-react-white'
docker build -t $env:LANDING_IMAGE .
docker compose -p vagents-landing up -d --no-build
npm test
```

Tests default to the production container at `http://127.0.0.1:5180`. To verify
the live release, set `LANDING_BASE_URL=https://vagen-platform.duckdns.org`.
The suite checks 360–1440px layouts, all images and placeholders, synchronized
demo steps, pause/replay/offscreen behavior, FAQ, mobile menu,
reduced motion, 44px touch targets and serious/critical axe findings.
It does not sign in or modify Platform data. Evidence and screenshots are
saved under Git-ignored `.artifacts/`.

The live demo is explicitly labeled as a simulation and never calls a business
API. All requested bracketed placeholders remain visible: customer count, integration list, FAQ answers,
contact details and legal text. Newsletter submission validates the email
locally and states that no service is connected; no email is sent or stored.
Model/partner/ticket acceptance is outside frontend verification.

## Visual direction

White/light-gray, orange and 3D workforce characters. Design variance 7/10,
motion 8/10, density 4/10. OS reduced motion and the global pause button stop
continuous animation; offscreen sections pause loops. Touch devices retain
native scrolling and disable parallax, tilt and magnetic hover.

Four supplied PNGs are preserved byte-for-byte. The fifth mascot was generated
from the references because the coordinator was attached twice. The page uses
optimized AVIF/WebP derivatives; original transparent PNGs remain in `public/images`.
Sources, SHA256 and full prompts: [art-direction-white.txt](art-direction-white.txt).

Source layout: `src/` (entry, App, styles, fonts), `components/sections/`
(12 sections), `components/ui/` (motion primitives), `lib/content.ts` (copy),
`lib/motion.ts` + `lib/motion-provider.tsx` (shared motion preferences).

Vite builds to `dist/` with `/landing-assets/` as its asset namespace. nginx
serves the landing at `/` while preserving the existing Platform app and API routes.
Pricing is intentionally omitted from the page, navigation and footer.
The build prerenders React to HTML and hydrates it in the browser. Headings,
content and the hero image remain available before JavaScript loads; no
application server or Next.js runtime is involved.

VPS packaging and rollback: [deploy/README.md](deploy/README.md).
