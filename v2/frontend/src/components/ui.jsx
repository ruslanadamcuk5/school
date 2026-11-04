import { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";
import {
  AlertCircle,
  ChevronDown,
  Loader2,
  Sparkles,
  X,
} from "lucide-react";
import { onToast } from "../lib/hooks";
import { avatarGradient, pct } from "../lib/format";

/* ------------------------------------------------------------------ logo */
export function Logo({ size = "md", withWord = true, className = "" }) {
  const dims = size === "sm" ? 30 : size === "lg" ? 44 : 36;
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <span
        className="relative inline-flex items-center justify-center rounded-2xl border border-white/10 bg-ink-900"
        style={{ width: dims, height: dims }}
      >
        <svg viewBox="0 0 64 64" width={dims - 8} height={dims - 8} aria-hidden="true">
          <defs>
            <linearGradient id="logo-g" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
              <stop stopColor="#a78bfa" />
              <stop offset=".55" stopColor="#c084fc" />
              <stop offset="1" stopColor="#4ee1f5" />
            </linearGradient>
          </defs>
          <path d="M32 10 52 21v22L32 54 12 43V21l20-11Z" fill="none" stroke="url(#logo-g)" strokeWidth="3" />
          <path d="M22 26h20M22 33h20M32 26v16" stroke="url(#logo-g)" strokeWidth="3.6" strokeLinecap="round" />
        </svg>
      </span>
      {withWord && (
        <span className="font-display text-[1.05rem] font-semibold tracking-tight text-white">
          школьник<span className="grad-text">.</span>
        </span>
      )}
    </span>
  );
}

/* ------------------------------------------------------------------ buttons */
export function Button({
  variant = "primary",
  size = "md",
  icon: Icon,
  children,
  className = "",
  loading = false,
  ...props
}) {
  const variants = {
    primary: "btn-primary",
    ghost: "btn-ghost",
    gold: "btn-gold",
    danger: "btn-danger",
    plain: "text-mist-300 hover:text-white",
  };
  const sizes = { sm: "btn-sm", md: "", lg: "btn-lg" };
  return (
    <button
      className={`btn ${variants[variant] || ""} ${sizes[size] || ""} ${className}`}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading ? <Loader2 size={16} className="animate-spin" /> : Icon ? <Icon size={16} /> : null}
      {children}
    </button>
  );
}

export function IconButton({ icon: Icon, label, className = "", loading = false, ...props }) {
  return (
    <button
      className={`icon-btn ${className}`}
      aria-label={label}
      title={label}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading ? <Loader2 size={18} className="animate-spin" /> : <Icon size={18} />}
    </button>
  );
}

/* ------------------------------------------------------------------ badges */
export function Badge({ tone = "", children, className = "" }) {
  return <span className={`badge ${tone ? `badge-${tone}` : ""} ${className}`}>{children}</span>;
}

export function Coin({ value, className = "" }) {
  return (
    <span className={`inline-flex items-center gap-1 font-bold ${className}`}>
      <span aria-hidden="true">🪙</span>
      {Number(value || 0).toLocaleString("ru-RU")}
    </span>
  );
}

export function Xp({ value, className = "" }) {
  return (
    <span className={`inline-flex items-center gap-1 font-bold ${className}`}>
      <Sparkles size={14} className="text-iris-400" />
      {Number(value || 0).toLocaleString("ru-RU")} XP
    </span>
  );
}

/* ------------------------------------------------------------------ avatars */
export function Avatar({ emoji = "🦊", size = 44, seed = "", ring = false, className = "" }) {
  return (
    <span
      className={`relative inline-flex shrink-0 items-center justify-center rounded-2xl ${ring ? "ring-2 ring-iris-400/60 ring-offset-2 ring-offset-ink-900" : ""} ${className}`}
      style={{
        width: size,
        height: size,
        background: avatarGradient(seed || emoji),
        fontSize: size * 0.48,
        boxShadow: "inset 0 1px 0 rgba(255,255,255,.35), 0 8px 24px -12px rgba(0,0,0,.8)",
      }}
      aria-hidden="true"
    >
      <span style={{ filter: "drop-shadow(0 1px 2px rgba(0,0,0,.35))" }}>{emoji}</span>
    </span>
  );
}

/* ------------------------------------------------------------------ cards */
export function Card({ as: Tag = "div", className = "", hover = false, children, ...props }) {
  return (
    <Tag className={`card ${hover ? "card-hover" : ""} ${className}`} {...props}>
      {children}
    </Tag>
  );
}

export function SectionTitle({ eyebrow, title, subtitle, action, className = "" }) {
  return (
    <div className={`flex flex-wrap items-end justify-between gap-3 ${className}`}>
      <div>
        {eyebrow && <div className="eyebrow mb-2.5">{eyebrow}</div>}
        <h2 className="font-display text-xl font-semibold text-white sm:text-2xl">{title}</h2>
        {subtitle && <p className="mt-1.5 max-w-2xl text-sm text-mist-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions, badge }) {
  return (
    <div className="mb-7 flex flex-wrap items-start justify-between gap-4">
      <div>
        {badge}
        <h1 className="font-display text-2xl font-semibold tracking-tight text-white sm:text-[1.9rem]">
          {title}
        </h1>
        {subtitle && <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-mist-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ stats */
export function StatCard({ icon: Icon, label, value, suffix, hint, tone = "iris", children }) {
  const tones = {
    iris: "from-iris-500/20 to-transparent text-iris-400",
    cyan: "from-cyan-400/15 to-transparent text-cyan-300",
    gold: "from-amber-400/15 to-transparent text-amber-300",
    green: "from-emerald-400/15 to-transparent text-emerald-300",
    rose: "from-rose-400/15 to-transparent text-rose-300",
  };
  return (
    <Card className="relative overflow-hidden p-5">
      <div className={`pointer-events-none absolute -right-8 -top-10 h-28 w-28 rounded-full bg-gradient-to-br blur-2xl ${tones[tone] || tones.iris}`} />
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold uppercase tracking-[0.12em] text-mist-500">{label}</span>
        {Icon && (
          <span className={`inline-flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/5 ${(tones[tone] || tones.iris).split(" ").pop()}`}>
            <Icon size={17} />
          </span>
        )}
      </div>
      <div className="mt-3 flex items-end gap-1.5">
        <span className="font-display text-[1.75rem] font-semibold leading-none text-white">{value}</span>
        {suffix && <span className="pb-0.5 text-xs font-semibold text-mist-500">{suffix}</span>}
      </div>
      {hint && <p className="mt-2 text-xs text-mist-500">{hint}</p>}
      {children}
    </Card>
  );
}

export function Progress({ value, className = "" }) {
  return (
    <div className={`progress ${className}`} role="progressbar" aria-valuenow={value || 0} aria-valuemin={0} aria-valuemax={100}>
      <span style={{ width: `${pct(value, 100)}%` }} />
    </div>
  );
}

export function Ring({ value = 0, size = 92, stroke = 8, children, label }) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (pct(value, 100) / 100) * circumference;
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          <linearGradient id={`ring-${size}-${Math.round(value)}`} x1="0" y1="0" x2="1" y2="1">
            <stop stopColor="#8b7bff" />
            <stop offset=".55" stopColor="#c084fc" />
            <stop offset="1" stopColor="#4ee1f5" />
          </linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="rgba(255,255,255,.08)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={`url(#ring-${size}-${Math.round(value)})`}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset .8s cubic-bezier(.22,1,.36,1)" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {children ?? (
          <>
            <span className="font-display text-lg font-semibold text-white">{Math.round(value)}%</span>
            {label && <span className="text-[10px] font-bold uppercase tracking-wider text-mist-500">{label}</span>}
          </>
        )}
      </div>
    </div>
  );
}

export function Sparkline({ points = [], width = 120, height = 36, color = "#a78bfa" }) {
  if (!points.length) return null;
  const max = Math.max(...points, 1);
  const step = width / Math.max(points.length - 1, 1);
  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"}${(index * step).toFixed(1)},${(height - (point / max) * (height - 4) - 2).toFixed(1)}`)
    .join(" ");
  return (
    <svg width={width} height={height} className="overflow-visible">
      <path d={path} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" opacity=".9" />
    </svg>
  );
}

/* ------------------------------------------------------------------ feedback */
export function Spinner({ label = "Загрузка…" }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-sm text-mist-500">
      <Loader2 size={18} className="animate-spin text-iris-400" />
      {label}
    </div>
  );
}

export function Skeleton({ className = "" }) {
  return <div className={`skeleton ${className}`} />;
}

export function EmptyState({ icon = "✨", title, text, action, className = "" }) {
  return (
    <div className={`flex flex-col items-center justify-center px-6 py-14 text-center ${className}`}>
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-2xl">
        {icon}
      </div>
      <h3 className="font-display text-base font-semibold text-white">{title}</h3>
      {text && <p className="mt-1.5 max-w-sm text-sm leading-relaxed text-mist-500">{text}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  return (
    <Card className="border-rose-400/20 bg-rose-500/[0.04] p-5">
      <div className="flex items-start gap-3">
        <AlertCircle size={18} className="mt-0.5 shrink-0 text-rose-300" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-rose-200">Не удалось загрузить данные</p>
          <p className="mt-1 break-words text-xs text-rose-200/70">
            {error?.message || "Попробуйте обновить страницу."}
          </p>
        </div>
        {onRetry && (
          <Button size="sm" variant="ghost" onClick={onRetry}>
            Повторить
          </Button>
        )}
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ forms */
export function Field({ label, hint, error, children, className = "" }) {
  return (
    <div className={className}>
      {label && <label className="label">{label}</label>}
      {children}
      {hint && !error && <p className="mt-1.5 text-xs text-mist-600">{hint}</p>}
      {error && <p className="mt-1.5 text-xs text-rose-300">{error}</p>}
    </div>
  );
}

export function Input({ className = "", ...props }) {
  return <input className={`field ${className}`} {...props} />;
}

export function Textarea({ className = "", ...props }) {
  return <textarea className={`field min-h-[96px] resize-y ${className}`} {...props} />;
}

export function Select({ className = "", children, ...props }) {
  return (
    <span className="relative block">
      <select className={`field appearance-none pr-10 ${className}`} {...props}>
        {children}
      </select>
      <ChevronDown size={16} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-mist-500" />
    </span>
  );
}

/* ------------------------------------------------------------------ tabs */
export function Tabs({ tabs, value, onChange, className = "" }) {
  return (
    <div className={`no-scrollbar flex gap-1 overflow-x-auto rounded-2xl border border-white/8 bg-white/[0.025] p-1 ${className}`}>
      {tabs.map((tab) => {
        const key = tab.key ?? tab;
        const label = tab.label ?? tab;
        const active = key === value;
        return (
          <button
            key={key}
            type="button"
            onClick={() => onChange(key)}
            className={`relative shrink-0 rounded-xl px-3.5 py-2 text-sm font-semibold transition ${
              active
                ? "bg-white/10 text-white shadow-[inset_0_1px_0_rgba(255,255,255,.1)]"
                : "text-mist-500 hover:text-mist-100"
            }`}
          >
            {tab.icon && <span className="mr-1.5">{tab.icon}</span>}
            {label}
            {tab.count != null && (
              <span className={`ml-2 rounded-full px-1.5 py-0.5 text-[10px] ${active ? "bg-iris-500/30 text-white" : "bg-white/5 text-mist-500"}`}>
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ modal */
export function Modal({ open, onClose, title, description, children, footer, size = "md" }) {
  const id = useId();
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => event.key === "Escape" && onClose?.();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;
  const widths = { sm: "max-w-md", md: "max-w-xl", lg: "max-w-3xl" };
  return createPortal(
    <div className="fixed inset-0 z-[80] flex items-end justify-center p-0 sm:items-center sm:p-6">
      <div className="absolute inset-0 bg-ink-950/75 backdrop-blur-sm" onClick={onClose} aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={id}
        className={`glass-strong fade-up relative max-h-[92vh] w-full overflow-y-auto rounded-t-3xl sm:rounded-3xl ${widths[size] || widths.md}`}
      >
        <div className="flex items-start justify-between gap-4 border-b border-white/8 px-6 py-5">
          <div>
            <h3 id={id} className="font-display text-lg font-semibold text-white">{title}</h3>
            {description && <p className="mt-1 text-sm text-mist-500">{description}</p>}
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Закрыть">
            <X size={18} />
          </button>
        </div>
        <div className="px-6 py-5">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-white/8 px-6 py-4">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

/* ------------------------------------------------------------------ toaster */
export function Toaster() {
  const [items, setItems] = useState([]);
  useEffect(
    () =>
      onToast((item) => {
        setItems((current) => {
          if (item.dismiss) return current.filter((entry) => entry.id !== item.id);
          return [...current.filter((entry) => entry.id !== item.id), item].slice(-4);
        });
      }),
    [],
  );
  const tones = {
    success: "border-emerald-400/30 bg-emerald-500/10 text-emerald-100",
    error: "border-rose-400/30 bg-rose-500/10 text-rose-100",
    info: "border-iris-400/30 bg-iris-500/10 text-iris-100",
  };
  return (
    <div className="pointer-events-none fixed bottom-24 right-4 z-[100] flex w-[min(92vw,360px)] flex-col gap-2 sm:bottom-6">
      {items.map((item) => (
        <div
          key={item.id}
          className={`fade-up pointer-events-auto flex items-start gap-2.5 rounded-2xl border px-4 py-3 text-sm font-medium shadow-2xl backdrop-blur-xl ${tones[item.type] || tones.info}`}
        >
          <span className="mt-0.5">{item.type === "error" ? "⚠️" : item.type === "success" ? "✅" : "💡"}</span>
          <span className="flex-1 leading-snug">{item.message}</span>
        </div>
      ))}
    </div>
  );
}
