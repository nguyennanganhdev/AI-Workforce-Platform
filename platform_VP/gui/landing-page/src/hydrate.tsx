import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { MotionProvider } from "../lib/motion";

const root = document.getElementById('root')!;
const page = (
  <React.StrictMode>
    <MotionProvider>
      <App />
    </MotionProvider>
  </React.StrictMode>
);
if (root.hasChildNodes()) ReactDOM.hydrateRoot(root, page);
else ReactDOM.createRoot(root).render(page);
