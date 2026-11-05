import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Keep the details in the console for diagnostics, but never leave the
    // user with a blank screen.
    console.error("Ошибка интерфейса:", error, info?.componentStack || "");
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-ink-900/80 p-6">
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-rose-400">
            Что-то пошло не так
          </p>
          <h1 className="mt-2 font-display text-xl font-semibold text-white">
            Экран не удалось показать
          </h1>
          <p className="mt-2 text-sm text-mist-400">
            Обновите страницу. Если ошибка повторяется — текст ниже поможет её найти.
          </p>
          <pre className="mt-4 max-h-48 overflow-auto rounded-xl border border-white/8 bg-ink-950 p-3 text-[11px] leading-relaxed text-rose-300">
            {String(error?.message || error)}
          </pre>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-4 inline-flex items-center justify-center rounded-xl bg-iris-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-iris-400"
          >
            Обновить страницу
          </button>
        </div>
      </div>
    );
  }
}
