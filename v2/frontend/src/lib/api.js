const TOKEN_KEY = "school.v2.token";
const USER_KEY = "school.v2.session";

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage can be unavailable in private mode */
  }
}

export function loadSession() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function saveSession(session) {
  try {
    if (session) localStorage.setItem(USER_KEY, JSON.stringify(session));
    else localStorage.removeItem(USER_KEY);
  } catch {
    /* ignore */
  }
}

export class ApiError extends Error {
  constructor(message, status, code) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function parse(response) {
  const type = response.headers.get("content-type") || "";
  if (type.includes("application/json")) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }
  return await response.text();
}

export async function request(path, options = {}) {
  const { method = "GET", body, form, auth = true, base = "/api/v1" } = options;
  const headers = {};
  const token = getToken();
  if (auth && token) headers.Authorization = `Bearer ${token}`;

  let payload;
  if (form) {
    payload = form;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(base + path, {
      method,
      headers,
      body: payload,
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError("Нет связи с сервером. Проверьте подключение.", 0, "network");
  }

  const data = await parse(response);
  if (!response.ok) {
    const message =
      (data && (data.message || data.detail || data.error)) ||
      `Ошибка ${response.status}`;
    throw new ApiError(
      typeof message === "string" ? message : "Не удалось выполнить запрос",
      response.status,
      data && data.error,
    );
  }
  return data;
}

export const api = {
  get: (path, opts) => request(path, opts),
  post: (path, body, opts) => request(path, { ...opts, method: "POST", body }),
  patch: (path, body, opts) => request(path, { ...opts, method: "PATCH", body }),
  put: (path, body, opts) => request(path, { ...opts, method: "PUT", body }),
  del: (path, opts) => request(path, { ...opts, method: "DELETE" }),
  form: (path, form, opts) =>
    request(path, { ...opts, method: "POST", form }),
};

/* ------------------------------------------------------------------ login */
export async function login(loginName, password) {
  const data = await request("/auth/login", {
    method: "POST",
    body: { login: loginName, password },
    auth: false,
    base: "/api/v2",
  });
  setToken(data.token);
  saveSession({ user: data.user, learner: data.learner, theme: data.theme });
  return data;
}

export async function register(payload) {
  const data = await request("/auth/register", {
    method: "POST",
    body: payload,
    auth: false,
    base: "/api/v2",
  });
  setToken(data.token);
  saveSession({ user: data.user, learner: data.learner, theme: data.theme });
  return data;
}

export async function logout() {
  try {
    await request("/auth/logout", { method: "POST", base: "/api/v2" });
  } catch {
    /* token may already be revoked */
  }
  setToken("");
  saveSession(null);
}

/* --------------------------------------------------------------- tiny cache */
const cache = new Map();
const inflight = new Map();

export function cachedGet(path, { ttl = 20_000, base = "/api/v1" } = {}) {
  const key = `${base}|${path}`;
  const hit = cache.get(key);
  if (hit && Date.now() - hit.at < ttl) {
    return Promise.resolve(hit.data);
  }
  if (inflight.has(key)) return inflight.get(key);
  const promise = request(path, { base })
    .then((data) => {
      cache.set(key, { at: Date.now(), data });
      return data;
    })
    .finally(() => inflight.delete(key));
  inflight.set(key, promise);
  return promise;
}

export function peekCache(path, base = "/api/v1") {
  return cache.get(`${base}|${path}`)?.data;
}

export function invalidate(prefix = "") {
  for (const key of [...cache.keys()]) {
    if (!prefix || key.includes(prefix)) cache.delete(key);
  }
}
