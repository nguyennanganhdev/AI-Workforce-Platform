# OpenBot UI shell

Owner: Frontend. React/Vite OpenBot đã được nhập vào package này.

Shell, router, auth UI và design system giữ theo baseline upstream. Gắn generic UX vào
`src/features/platform`, UX nghiệp vụ vào `src/features/domains/vinhomes`.
`src/routes` là composition layer, chỉ điều phối page/feature.
Chạy từ root: `bun run dev`, `bun run build`. Cấu hình backend/dependency theo README root.
