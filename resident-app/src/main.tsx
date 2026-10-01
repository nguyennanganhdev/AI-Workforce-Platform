import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource-variable/inter";
import { App } from "./app/App";
import { ConnectedApp } from "./app/ConnectedApp";
import { AuthPage } from "./features/auth/AuthPage";
import { isResidentPreview } from "./features/auth/demo-access";
import { ResidentAccountStatus } from "./features/auth/ResidentAccountStatus";
import "./styles.css";

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
    {authMode ? (
      <AuthPage mode={authMode} onAuthenticated={() => location.assign("/")} />
    ) : status ? (
      <ResidentAccountStatus status={status} preview />
    ) : preview ? (
      <App />
    ) : legacyAuth ? null : <ConnectedApp />}
  </React.StrictMode>,
);
