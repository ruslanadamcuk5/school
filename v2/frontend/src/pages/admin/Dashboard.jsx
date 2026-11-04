import { Link } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  BookOpen,
  Bot,
  Building2,
  ClipboardList,
  GraduationCap,
  Library,
  ScrollText,
  ShieldCheck,
  Sparkles,
  Store,
  Target,
  Trophy,
  Users,
  Youtube,
} from "lucide-react";
import {
  Avatar,
  Badge,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  Progress,
  SectionTitle,
  Skeleton,
  StatCard,
} from "../../components/ui";
import { useApi, useSession } from "../../lib/hooks";
import { ROLE_LABEL, formatDateTime, plural, relativeTime, text, todayLabel } from "../../lib/format";
import { RoleBadge } from "./shared";

const QUICK_LINKS = [
  { to: "/app/admin/users", icon: Users, title: "Пользователи", text: "Роли, доступы, пароли и блокировки.", tone: "iris" },
  { to: "/app/admin/topics", icon: BookOpen, title: "Темы и предметы", text: "Каталог обучения и порядок тем.", tone: "cyan" },
  { to: "/app/admin/orgs", icon: Building2, title: "Организация", text: "Города, школы, классы и учителя.", tone: "green" },
  { to: "/app/admin/shop", icon: Store, title: "Магазин", text: "Товары, события, витрина и подарки.", tone: "gold" },
  { to: "/app/admin/youtube", icon: Youtube, title: "YouTube", text: "Видео к темам и кэш подборки.", tone: "rose" },
  { to: "/app/admin/ai", icon: Bot, title: "Искусственный интеллект", text: "Провайдер, модель и лимиты.", tone: "violet" },
];

const TONES = {
  iris: "border-iris-400/20 bg-iris-500/10 text-iris-200",
  cyan: "border-cyan-400/20 bg-cyan-500/10 text-cyan-200",
  green: "border-emerald-400/20 bg-emerald-500/10 text-emerald-200",
  gold: "border-amber-400/20 bg-amber-500/10 text-amber-200",
  rose: "border-rose-400/20 bg-rose-500/10 text-rose-200",
  violet: "border-violet-400/20 bg-violet-500/10 text-violet-200",
};

function AiHealth({ ai }) {
  const total = Number(ai?.total || 0);
  const ok = Number(ai?.ok || 0);
  const percent = total ? Math.round((ok / total) * 100) : 0;
  return (
    <Card className="p-5 sm:p-6">
      <SectionTitle
        eyebrow="ИИ"
        title="Подсказки и объяснения"
        action={<Link to="/app/admin/ai" className="text-[11px] font-bold text-iris-300">Настроить →</Link>}
      />
      <div className="mt-4 grid grid-cols-3 gap-2">
        {[
          ["Всего", total],
          ["Успешно", ok],
          ["Ошибок", ai?.failed || 0],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-white/7 bg-white/[0.025] px-3 py-2.5 text-center">
            <p className="font-display text-base font-semibold text-white">{value}</p>
            <p className="mt-0.5 text-[10px] font-bold uppercase tracking-wider text-mist-600">{label}</p>
          </div>
        ))}
      </div>
      <div className="mt-4">
        <div className="mb-1.5 flex items-center justify-between text-[10px] font-bold text-mist-500">
          <span>Доля успешных ответов</span>
          <span>{total ? `${percent}%` : "нет данных"}</span>
        </div>
        <Progress value={percent} />
      </div>
      {ai?.last_error ? (
        <p className="mt-3 line-clamp-2 rounded-xl border border-rose-400/20 bg-rose-500/[0.06] px-3 py-2 text-[11px] text-rose-200/80">
          {text(ai.last_error)}
        </p>
      ) : (
        <p className="mt-3 text-[11px] leading-relaxed text-mist-500">
          Когда ИИ включён, дети получают объяснения к ошибкам, а учителя — подсказки по темам.
        </p>
      )}
    </Card>
  );
}

export function AdminDashboard() {
  const { session } = useSession();
  const { data, loading, error, refresh } = useApi("/admin/stats");
  const stats = data?.stats || {};
  const byRole = data?.by_role || {};
  const ai = data?.ai || {};
  const recentUsers = data?.recent_users || [];
  const recentAudit = data?.recent_audit || [];
  const rolesTotal = Object.values(byRole).reduce((sum, value) => sum + Number(value || 0), 0) || 1;

  if (loading && !data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-44 w-full" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, index) => <Skeleton key={index} className="h-28" />)}
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Платформа"
        subtitle={`${todayLabel()} · полный обзор школы, пользователей и сервисов.`}
        actions={
          <>
            <Link to="/app/admin/audit"><span className="btn btn-ghost"><ScrollText size={16} /> Журнал</span></Link>
            <Link to="/app/admin/users"><span className="btn btn-primary"><Users size={16} /> Пользователи</span></Link>
          </>
        }
      />

      {error && <ErrorState error={error} onRetry={refresh} />}

      <Card className="relative overflow-hidden p-6 sm:p-8">
        <div className="pointer-events-none absolute -right-24 -top-28 h-80 w-80 rounded-full bg-iris-500/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 left-1/3 h-72 w-72 rounded-full bg-cyan-400/10 blur-3xl" />
        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center">
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="iris"><ShieldCheck size={12} /> администратор</Badge>
              <Badge tone="green"><Activity size={12} /> все сервисы онлайн</Badge>
              <Badge tone="cyan">{stats.topics || 0} тем в каталоге</Badge>
            </div>
            <h2 className="mt-3 font-display text-xl font-semibold text-white sm:text-2xl">
              Здравствуйте, {session?.user?.first_name || "администратор"}
            </h2>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-mist-400">
              Управляйте пользователями, наполнением, магазином и интеграциями.
              Все изменения сразу видны ученикам, родителям и учителям.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:w-[440px]">
            {[
              [Users, "Люди", stats.users || 0],
              [GraduationCap, "Классы", stats.classes || 0],
              [ClipboardList, "Работы", stats.assignments || 0],
              [Target, "Попытки", stats.attempts || 0],
            ].map(([Icon, label, value]) => (
              <div key={label} className="rounded-2xl border border-white/8 bg-white/[0.035] p-3 text-center">
                <Icon size={16} className="mx-auto text-iris-300" />
                <p className="mt-1.5 font-display text-lg font-semibold text-white">{value}</p>
                <p className="text-[9px] font-bold uppercase tracking-wider text-mist-600">{label}</p>
              </div>
            ))}
          </div>
        </div>
      </Card>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Users} label="Пользователей" value={stats.users || 0} hint={`${stats.students || 0} учеников`} tone="iris" />
        <StatCard icon={GraduationCap} label="Учителей" value={stats.teachers || 0} hint={`${stats.classes || 0} классов`} tone="cyan" />
        <StatCard icon={BookOpen} label="Тем" value={stats.topics || 0} hint={`${stats.library_books || 0} книг в библиотеке`} tone="gold" />
        <StatCard icon={ClipboardList} label="Заданий" value={stats.assignments || 0} hint={`${stats.attempts || 0} попыток`} tone="green" />
      </div>

      <div className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
        <Card className="p-5 sm:p-6">
          <SectionTitle eyebrow="Аудитория" title="Роли в системе" subtitle="Кто пользуется платформой прямо сейчас." />
          <div className="mt-5 space-y-3">
            {["admin", "teacher", "parent", "student"].map((role) => {
              const value = Number(byRole[role] || 0);
              const percent = Math.round((value / rolesTotal) * 100);
              return (
                <div key={role}>
                  <div className="mb-1.5 flex items-center justify-between text-[11px]">
                    <span className="font-semibold text-white">{ROLE_LABEL[role]}</span>
                    <span className="text-mist-500">{value} · {percent}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-white/6">
                    <div
                      className={`h-full rounded-full ${
                        role === "admin"
                          ? "bg-gradient-to-r from-rose-400 to-rose-500"
                          : role === "teacher"
                            ? "bg-gradient-to-r from-cyan-400 to-cyan-500"
                            : role === "parent"
                              ? "bg-gradient-to-r from-amber-300 to-amber-500"
                              : "bg-gradient-to-r from-iris-400 to-iris-600"
                      }`}
                      style={{ width: `${Math.max(3, percent)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-5 grid grid-cols-2 gap-2">
            <div className="rounded-xl border border-white/7 bg-white/[0.025] px-3 py-2.5">
              <p className="font-display text-base font-semibold text-white">{stats.learners || 0}</p>
              <p className="text-[10px] text-mist-600">профилей детей</p>
            </div>
            <div className="rounded-xl border border-white/7 bg-white/[0.025] px-3 py-2.5">
              <p className="font-display text-base font-semibold text-white">{stats.schools || 0}</p>
              <p className="text-[10px] text-mist-600">школ · {stats.cities || 0} городов</p>
            </div>
          </div>
        </Card>

        <AiHealth ai={ai} />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <div>
          <SectionTitle
            eyebrow="Люди"
            title="Недавние пользователи"
            action={<Link to="/app/admin/users" className="text-[11px] font-bold text-iris-300">Все →</Link>}
          />
          <Card className="mt-4 p-2">
            {recentUsers.length === 0 && <EmptyState icon="👥" title="Пользователей пока нет" text="Создайте первый аккаунт." />}
            {recentUsers.slice(0, 7).map((user) => (
              <Link key={user.id} to="/app/admin/users" className="flex items-center gap-3 rounded-xl px-3 py-2.5 transition hover:bg-white/5">
                <Avatar emoji={user.avatar || "🦊"} size={36} seed={user.login} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-bold text-white">{user.first_name} {user.last_name}</p>
                  <p className="truncate text-[10px] text-mist-600">@{user.login} · {relativeTime(user.created_at)}</p>
                </div>
                <RoleBadge role={user.role} />
              </Link>
            ))}
          </Card>
        </div>

        <div>
          <SectionTitle
            eyebrow="События"
            title="Журнал действий"
            action={<Link to="/app/admin/audit" className="text-[11px] font-bold text-iris-300">Весь журнал →</Link>}
          />
          <Card className="mt-4 p-2">
            {recentAudit.length === 0 && <EmptyState icon="📜" title="Записей пока нет" text="Здесь появятся действия администраторов и учителей." />}
            {recentAudit.slice(0, 7).map((entry) => (
              <div key={entry.id} className="flex items-center gap-3 rounded-xl px-3 py-2.5">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/5 text-[11px] font-bold uppercase text-iris-200">
                  {(entry.action || "?").slice(0, 2)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[11px] font-semibold text-white">
                    {entry.action} · {entry.entity || "система"}
                  </p>
                  <p className="truncate text-[10px] text-mist-600">
                    {entry.login ? `@${entry.login} · ` : ""}{text(entry.detail) || formatDateTime(entry.created_at)}
                  </p>
                </div>
                <span className="shrink-0 text-[10px] text-mist-600">{relativeTime(entry.created_at)}</span>
              </div>
            ))}
          </Card>
        </div>
      </div>

      <div>
        <SectionTitle eyebrow="Навигация" title="Быстрый доступ" subtitle="Всё, что нужно для управления платформой." />
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {QUICK_LINKS.map(({ to, icon: Icon, title, text, tone }) => (
            <Link key={to} to={to}>
              <Card hover className="group h-full p-5">
                <span className={`inline-flex h-11 w-11 items-center justify-center rounded-2xl border ${TONES[tone]}`}>
                  <Icon size={19} />
                </span>
                <h3 className="mt-3 font-display text-sm font-semibold text-white">{title}</h3>
                <p className="mt-1 text-[11px] leading-relaxed text-mist-500">{text}</p>
                <span className="mt-3 inline-flex items-center gap-1 text-[11px] font-bold text-iris-300">
                  Открыть <ArrowRight size={12} />
                </span>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
