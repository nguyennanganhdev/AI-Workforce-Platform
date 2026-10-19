import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource-variable/manrope";
import { isResidentPreview } from "./features/auth/demo-access";
import "./styles.css";
import "./brand.css";
import { isLandingRoute } from "./features/landing/routes";

const LandingPage = React.lazy(() => import("./features/landing/LandingPage").then((module) => ({ default: module.LandingPage })));
const App = React.lazy(() => import("./app/App").then((module) => ({ default: module.App })));
const ConnectedApp = React.lazy(() => import("./app/ConnectedApp").then((module) => ({ default: module.ConnectedApp })));
const AuthPage = React.lazy(() => import("./features/auth/AuthPage").then((module) => ({ default: module.AuthPage })));
const ResidentAccountStatus = React.lazy(() => import("./features/auth/ResidentAccountStatus").then((module) => ({ default: module.ResidentAccountStatus })));

const authModes = ["login", "register", "forgot-password"] as const;
const authMode = authModes.find(
  (mode) => location.pathname.replace(/\/$/, "") === `/${mode}`,
);
// Preserve old bookmarks while giving account pages their own URLs.
function redirectLegacyAuth() {
  const mode = authModes.find((mode) => location.hash === `#/${mode}`);
  if (mode) location.replace(`/${mode}`);
  return Boolean(mode);
}
const legacyAuth = redirectLegacyAuth();
window.addEventListener("hashchange", redirectLegacyAuth);
const statusPreview =
  location.pathname === "/account-status" &&
  new URLSearchParams(location.search).get("preview");
const status =
  statusPreview === "verification-required" ||
  statusPreview === "membership-pending"
    ? statusPreview
    : null;
const preview = isResidentPreview();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <React.Suspense fallback={<main aria-busy="true" style={{ padding: "48px" }}>Đang tải…</main>}>
    {authMode ? (
      <AuthPage key={authMode} mode={authMode} onAuthenticated={() => location.assign('/resident')} />
    ) : status ? (
      <ResidentAccountStatus status={status} preview />
    ) : preview ? (
      <App />
    ) : legacyAuth ? null : isLandingRoute(location.pathname, location.hash) ? (
      <LandingPage />
    ) : (
      <ConnectedApp />
    )}
    </React.Suspense>
  </React.StrictMode>,
);
