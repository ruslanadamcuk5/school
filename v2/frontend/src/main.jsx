import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { SessionProvider } from "./lib/hooks";
import { setToken } from "./lib/api";
import { Toaster } from "./components/ui";
import "./index.css";

// Android открывает квест во встроенном WebView. Токен передаётся во
// фрагменте адреса (он не уходит на сервер) и сразу убирается из строки.
try {
  const fragment = new URLSearchParams((window.location.hash || "").replace(/^#/, ""));
  const incoming = fragment.get("token");
  if (incoming) {
    setToken(incoming);
    window.history.replaceState({}, "", window.location.pathname + window.location.search);
  }
} catch {
  /* адрес без фрагмента — обычный вход через форму */
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <SessionProvider>
        <App />
        <Toaster />
      </SessionProvider>
    </BrowserRouter>
  </StrictMode>,
);
