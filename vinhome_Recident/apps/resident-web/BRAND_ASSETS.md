# Landing page assets

- `public/images/vinhomes-official.png`: original Vinhomes logo extracted with its transparency mask from image object 11 on the cover of the company's [1Q2025 earnings presentation](https://gcp-cdn.vinhomes.vn/cms-data/250429_EN_VHM_1Q2025_Earnings%20Presentation_vF_upload_0.pdf). Shape and colours are unchanged. This asset does not include the Vinhomes Market sub-brand.
- `public/images/ocean-park-welcome-{640,960,1600}.webp`: renditions of the existing project asset (quality 78), selected through responsive `srcSet` on the landing page. Account and assistant backgrounds use the 960px rendition. The original JPEG was removed from the public bundle after all consumers switched to WebP; it remains recoverable from Git history.
- Typography: self-hosted Manrope Variable, including the Vietnamese character subset.
- Button: adapted from the [official shadcn/ui new-york registry](https://ui.shadcn.com/r/styles/new-york/button.json), with project colours, sizing and corner radii. Tailwind utilities are used without preflight to preserve existing application styles.
