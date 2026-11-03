import { Badge, Card } from "../../components/ui";
import { ROLE_LABEL } from "../../lib/format";

export function roleTone(role) {
  if (role === "admin") return "rose";
  if (role === "teacher") return "cyan";
  if (role === "parent") return "gold";
  return "iris";
}

export function RoleBadge({ role }) {
  return <Badge tone={roleTone(role)}>{ROLE_LABEL[role] || role}</Badge>;
}

export function Toolbar({ children, className = "" }) {
  return (
    <Card className={`flex flex-col gap-3 p-4 sm:flex-row sm:items-center ${className}`}>
      {children}
    </Card>
  );
}

export function SearchBox({ value, onChange, placeholder = "Поиск…" }) {
  return (
    <div className="relative min-w-0 flex-1">
      <svg
        viewBox="0 0 24 24"
        className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-mist-500"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        aria-hidden="true"
      >
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3.5-3.5" />
      </svg>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="field pl-9"
      />
    </div>
  );
}

export function Detail({ label, value }) {
  return (
    <div className="rounded-xl border border-white/7 bg-white/[0.025] px-3 py-2.5">
      <p className="text-[10px] font-bold uppercase tracking-wider text-mist-600">{label}</p>
      <p className="mt-0.5 truncate text-xs font-semibold text-white">{value ?? "—"}</p>
    </div>
  );
}

export function Toggle({ value, onChange, label, text }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      className="flex w-full items-center gap-3 rounded-xl border border-white/8 bg-white/[0.025] px-3.5 py-3 text-left transition hover:border-white/16"
    >
      <div className="min-w-0 flex-1">
        <p className="text-xs font-bold text-white">{label}</p>
        {text ? <p className="mt-0.5 text-[11px] leading-relaxed text-mist-500">{text}</p> : null}
      </div>
      <span className={`relative h-5 w-9 shrink-0 rounded-full transition ${value ? "bg-emerald-500/80" : "bg-white/10"}`}>
        <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition ${value ? "left-[18px]" : "left-0.5"}`} />
      </span>
    </button>
  );
}

export function MiniStat({ label, value, tone = "text-white" }) {
  return (
    <div className="rounded-xl border border-white/7 bg-white/[0.025] px-3 py-2.5 text-center">
      <p className={`font-display text-sm font-semibold ${tone}`}>{value}</p>
      <p className="mt-0.5 text-[10px] font-bold uppercase tracking-wider text-mist-600">{label}</p>
    </div>
  );
}
