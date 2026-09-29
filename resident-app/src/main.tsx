import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource-variable/inter";
import { App } from "./app/App";
import { AuthPage } from "./features/auth/AuthPage";
import "./styles.css";

const authModes = ["login", "register", "forgot-password"] as const;
const authMode = authModes.find(
  (mode) => location.pathname.replace(/\/$/, "") === `/${mode}`,
);
// Preserve old bookmarks while giving account pages their own URLs.
function redirectLegacyAuth() {
  const mode = authModes.find((mode) => location.hash === `#/${mode}`);
  if (mode) location.replace(`/${mode}`);
}
redirectLegacyAuth();
window.addEventListener("hashchange", redirectLegacyAuth);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {authMode ? <AuthPage mode={authMode} /> : <App />}
  </React.StrictMode>,
);
