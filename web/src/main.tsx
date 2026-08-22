import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import "./index.css";
import App from "./App";
import { SystemActionsProvider } from "./contexts/SystemActions";
import { I18nProvider } from "./i18n";
import { exposePluginSDK } from "./plugins";
import {
  exposeServiceWorkerKillSwitch,
  registerServiceWorker,
} from "./pwa/register";
import { ThemeProvider } from "./themes";
import { HERMES_BASE_PATH } from "./lib/api";

// Expose the plugin SDK before rendering so plugins loaded via <script>
// can access React, components, etc. immediately.
exposePluginSDK();

// PWA. Registers only in production and only in a secure context — see
// src/pwa/register.ts for why. The kill switch goes on `window` regardless,
// so a broken service worker can be removed from the device console even when
// the app itself no longer renders.
exposeServiceWorkerKillSwitch();
void registerServiceWorker();

createRoot(document.getElementById("root")!).render(
  <BrowserRouter basename={HERMES_BASE_PATH || undefined}>
    <I18nProvider>
      <ThemeProvider>
        <SystemActionsProvider>
          <App />
        </SystemActionsProvider>
      </ThemeProvider>
    </I18nProvider>
  </BrowserRouter>,
);
