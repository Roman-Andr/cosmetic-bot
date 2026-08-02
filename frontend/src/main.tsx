import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/roboto/cyrillic-400.css";
import "@fontsource/roboto/cyrillic-500.css";
import "@fontsource/roboto/cyrillic-700.css";
import "@fontsource/roboto/cyrillic-900.css";
import "@fontsource/roboto/latin-400.css";
import "@fontsource/roboto/latin-500.css";
import "@fontsource/roboto/latin-700.css";
import "@fontsource/roboto/latin-900.css";

import App from "./App";
import { QueryProvider } from "./app/providers/QueryProvider";
import "./app/styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode><QueryProvider><App /></QueryProvider></StrictMode>,
);
