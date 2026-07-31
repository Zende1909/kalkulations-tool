import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import {
  AllCommunityModule,
  ModuleRegistry,
  provideGlobalGridOptions,
} from "ag-grid-community";

import App from "./App";
import "./index.css";

// AG Grid v33+: ohne Modul-Registrierung bleibt die Tabelle leer (kein Row-Model).
ModuleRegistry.registerModules([AllCommunityModule]);
provideGlobalGridOptions({ theme: "legacy" });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
