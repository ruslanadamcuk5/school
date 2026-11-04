export const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
export const WEEKDAYS_FULL = [
  "Понедельник",
  "Вторник",
  "Среда",
  "Четверг",
  "Пятница",
  "Суббота",
  "Воскресенье",
];

export const ROLE_LABEL = {
  student: "Ученик",
  parent: "Родитель",
  teacher: "Учитель",
  admin: "Администратор",
};

export const ROLE_HOME = {
  student: "/app",
  parent: "/app/parent",
  teacher: "/app/teacher",
  admin: "/app/admin",
};

const SUBJECT_COLORS = {
  indigo: { from: "#8b7bff", to: "#5b5bff", soft: "rgba(139,123,255,.14)" },
  sky: { from: "#38bdf8", to: "#0ea5e9", soft: "rgba(56,189,248,.14)" },
  rose: { from: "#fb7185", to: "#e11d48", soft: "rgba(251,113,133,.14)" },
  violet: { from: "#c084fc", to: "#9333ea", soft: "rgba(192,132,252,.14)" },
  emerald: { from: "#34d399", to: "#059669", soft: "rgba(52,211,153,.14)" },
  teal: { from: "#2dd4bf", to: "#0d9488", soft: "rgba(45,212,191,.14)" },
  amber: { from: "#fbbf24", to: "#d97706", soft: "rgba(251,191,36,.14)" },
};

export function subjectColor(name) {
  return SUBJECT_COLORS[name] || SUBJECT_COLORS.indigo;
}

export function parseDate(value) {
  if (!value) return null;
  if (value instanceof Date) return value;
  const text = String(value);
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return new Date(`${text}T00:00:00`);
  if (/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?$/.test(text)) {
    return new Date(`${text.replace(" ", "T")}Z`);
  }
  const parsed = new Date(text);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatDate(value, opts = {}) {
  const date = parseDate(value);
  if (!date) return "—";
  return date.toLocaleDateString("ru-RU", {
    day: "numeric",
    month: opts.long ? "long" : "short",
    ...(opts.year ? { year: "numeric" } : {}),
  });
}

export function formatDateTime(value) {
  const date = parseDate(value);
  if (!date) return "—";
  return `${formatDate(value)}, ${date.toLocaleTimeString("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

export function relativeTime(value) {
  const date = parseDate(value);
  if (!date) return "";
  const diff = Date.now() - date.getTime();
  const minute = 60_000;
  if (diff < minute) return "только что";
  if (diff < 60 * minute) return `${Math.floor(diff / minute)} мин назад`;
  if (diff < 24 * 60 * minute) return `${Math.floor(diff / (60 * minute))} ч назад`;
  if (diff < 7 * 24 * 60 * minute) return `${Math.floor(diff / (24 * 60 * minute))} дн назад`;
  return formatDate(value);
}

export function plural(n, forms) {
  const value = Math.abs(Number(n)) % 100;
  const last = value % 10;
  if (value > 10 && value < 20) return forms[2];
  if (last > 1 && last < 5) return forms[1];
  if (last === 1) return forms[0];
  return forms[2];
}

export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

export function pct(done, total) {
  if (!total) return 0;
  return clamp(Math.round((Number(done) / Number(total)) * 100), 0, 100);
}

export function todayLabel() {
  return new Date().toLocaleDateString("ru-RU", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

export const LEVEL_THRESHOLDS = [
  0, 60, 150, 280, 450, 650, 900, 1200, 1550, 1950, 2400, 2900,
  3500, 4200, 5000, 6000, 7000, 8200, 9500, 11000, 13000, 15000,
  17500, 20000, 23000, 26000, 30000, 35000, 40000, 46000, 53000,
];

export function levelInfo(xp = 0) {
  const value = Math.max(0, Number(xp) || 0);
  let level = 1;
  LEVEL_THRESHOLDS.forEach((threshold, index) => {
    if (value >= threshold) level = index + 1;
  });
  const current = LEVEL_THRESHOLDS[level - 1] ?? 0;
  const next = LEVEL_THRESHOLDS[level] ?? current + 5000;
  const span = Math.max(1, next - current);
  return {
    level,
    xp: value,
    current,
    next,
    need: Math.max(0, next - value),
    percent: Math.min(100, Math.max(0, Math.round(((value - current) / span) * 100))),
  };
}

export function scoreTone(percent) {
  if (percent >= 85) return "green";
  if (percent >= 65) return "cyan";
  if (percent >= 45) return "gold";
  return "rose";
}

export function taskTypeLabel(type) {
  return (
    {
      test: "Тест",
      read: "Чтение",
      dictation: "Диктант",
      other: "Задание",
    }[type] || "Задание"
  );
}

export const AVATAR_GRADIENTS = [
  "linear-gradient(140deg,#8b7bff,#4ee1f5)",
  "linear-gradient(140deg,#fb7185,#f59e0b)",
  "linear-gradient(140deg,#34d399,#38bdf8)",
  "linear-gradient(140deg,#c084fc,#f472b6)",
];

export function avatarGradient(seed = "") {
  let sum = 0;
  for (let i = 0; i < seed.length; i += 1) sum += seed.charCodeAt(i);
  return AVATAR_GRADIENTS[sum % AVATAR_GRADIENTS.length];
}

export function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

/**
 * Turn any API value into a string safe to render as a React child.
 * Error payloads from the backend are sometimes objects such as
 * ``{created_at, detail}``; rendering them directly crashes React.
 */
export function text(value, fallback = "") {
  if (value === null || value === undefined) return fallback;
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (typeof value === "object") {
    for (const key of ["detail", "message", "error", "text"]) {
      if (typeof value[key] === "string") return value[key];
      if (value[key] && typeof value[key] === "object") {
        const nested = text(value[key], "");
        if (nested) return nested;
      }
    }
    try {
      return JSON.stringify(value);
    } catch {
      return fallback;
    }
  }
  return String(value);
}

export function parseJsonArray(value, fallback = []) {
  if (Array.isArray(value)) return value;
  if (!value) return fallback;
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : fallback;
  } catch {
    return fallback;
  }
}
