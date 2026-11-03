import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  cachedGet,
  getToken,
  invalidate,
  loadSession,
  login as apiLogin,
  logout as apiLogout,
  peekCache,
  register as apiRegister,
  request,
  saveSession,
} from "./api";

/* ------------------------------------------------------------------ session */
const SessionContext = createContext(null);

export function SessionProvider({ children }) {
  const [session, setSession] = useState(() => loadSession());
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let alive = true;
    if (!getToken()) {
      setReady(true);
      return undefined;
    }
    request("/auth/me", { base: "/api/v2" })
      .then((data) => {
        if (!alive) return;
        const next = { user: data.user, learner: data.learner, theme: data.theme };
        setSession(next);
        saveSession(next);
      })
      .catch(() => {
        if (!alive) return;
        setSession(null);
        saveSession(null);
      })
      .finally(() => alive && setReady(true));
    return () => {
      alive = false;
    };
  }, []);

  const signIn = useCallback(async (loginName, password) => {
    const data = await apiLogin(loginName, password);
    const next = { user: data.user, learner: data.learner, theme: data.theme };
    setSession(next);
    return next;
  }, []);

  const signUp = useCallback(async (payload) => {
    const data = await apiRegister(payload);
    const next = { user: data.user, learner: data.learner, theme: data.theme };
    setSession(next);
    return next;
  }, []);

  const signOut = useCallback(async () => {
    await apiLogout();
    invalidate();
    setSession(null);
  }, []);

  const updateLearner = useCallback((patch) => {
    setSession((current) => {
      if (!current) return current;
      const next = { ...current, learner: { ...(current.learner || {}), ...patch } };
      saveSession(next);
      return next;
    });
  }, []);

  const refreshSession = useCallback(async () => {
    const data = await request("/auth/me", { base: "/api/v2" });
    const next = { user: data.user, learner: data.learner, theme: data.theme };
    setSession(next);
    saveSession(next);
    return next;
  }, []);

  return (
    <SessionContext.Provider
      value={{ session, ready, signIn, signUp, signOut, updateLearner, refreshSession }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const context = useContext(SessionContext);
  if (!context) throw new Error("useSession must be used inside SessionProvider");
  return context;
}

/* ------------------------------------------------------------------ fetching */
export function useApi(path, options = {}) {
  const { enabled = true, ttl = 20_000, initial = null, base = "/api/v1" } = options;
  const [data, setData] = useState(() => (path ? peekCache(path, base) ?? initial : initial));
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(Boolean(path && enabled && !peekCache(path, base)));
  const [tick, setTick] = useState(0);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (!path || !enabled) {
      setLoading(false);
      return undefined;
    }
    let alive = true;
    setLoading(!peekCache(path, base));
    cachedGet(path, { ttl, base })
      .then((result) => {
        if (!alive) return;
        setData(result);
        setError(null);
      })
      .catch((err) => {
        if (!alive) return;
        setError(err);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [path, enabled, ttl, base, tick]);

  const refresh = useCallback(() => {
    if (path) {
      invalidate(path);
    }
    setTick((n) => n + 1);
  }, [path]);

  return { data, error, loading, refresh, setData };
}

export function useAction() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(null);
  const run = useCallback(async (fn) => {
    setPending(true);
    setError(null);
    try {
      const result = await fn();
      return result;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setPending(false);
    }
  }, []);
  return { pending, error, run, setError };
}

/* ------------------------------------------------------------------ toasts */
let toastSeq = 0;
const toastListeners = new Set();

export function toast(message, type = "success", ttl = 4200) {
  const item = { id: ++toastSeq, message, type };
  toastListeners.forEach((listener) => listener(item));
  if (ttl) {
    setTimeout(() => {
      toastListeners.forEach((listener) => listener({ ...item, dismiss: true }));
    }, ttl);
  }
}

export function onToast(listener) {
  toastListeners.add(listener);
  return () => toastListeners.delete(listener);
}

/* ------------------------------------------------------------------ media */
export function useMediaQuery(query) {
  const [matches, setMatches] = useState(
    () => typeof window !== "undefined" && window.matchMedia(query).matches,
  );
  useEffect(() => {
    const list = window.matchMedia(query);
    const handler = (event) => setMatches(event.matches);
    list.addEventListener("change", handler);
    return () => list.removeEventListener("change", handler);
  }, [query]);
  return matches;
}
