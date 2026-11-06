import { useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Bell,
  BookOpen,
  CalendarDays,
  ChevronRight,
  ClipboardList,
  Compass,
  Gamepad2,
  GraduationCap,
  LayoutDashboard,
  Library,
  LifeBuoy,
  LogOut,
  Map,
  Menu,
  PawPrint,
  ScrollText,
  Settings2,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Users,
  UserRound,
  X,
  Youtube,
  Bot,
  Building2,
} from "lucide-react";
import { Avatar, Badge, Logo, Xp } from "./ui";
import { useApi, useSession } from "../lib/hooks";
import { ROLE_LABEL, formatDate, todayLabel } from "../lib/format";

const ICONS = {
  home: LayoutDashboard,
  learn: Compass,
  quests: Gamepad2,
  assignments: ClipboardList,
  library: Library,
  shop: ShoppingBag,
  pet: PawPrint,
  schedule: CalendarDays,
  map: Map,
  help: LifeBuoy,
  children: Users,
  classes: GraduationCap,
  students: Users,
  notifications: Bell,
  profile: UserRound,
  users: Users,
  topics: BookOpen,
  textbooks: Library,
  orgs: Building2,
  youtube: Youtube,
  ai: Bot,
  audit: ScrollText,
  settings: Settings2,
};

const NAV = {
  student: [
    { to: "/app", label: "Обзор", icon: "home", end: true },
    { to: "/app/learn", label: "Предметы", icon: "learn" },
    { to: "/app/assignments", label: "Задания", icon: "assignments" },
    { to: "/app/library", label: "Библиотека", icon: "library" },
    { to: "/app/shop", label: "Магазин", icon: "shop" },
    { to: "/app/pet", label: "Питомец", icon: "pet" },
    { to: "/app/schedule", label: "Расписание", icon: "schedule" },
  ],
  parent: [
    { to: "/app/parent", label: "Обзор семьи", icon: "home", end: true },
    { to: "/app/parent/map", label: "Карта", icon: "map" },
    { to: "/app/parent/help", label: "Помощь", icon: "help" },
    { to: "/app/parent/library", label: "Библиотека", icon: "library" },
    { to: "/app/parent/assignments", label: "Задания", icon: "assignments" },
    { to: "/app/notifications", label: "Уведомления", icon: "notifications" },
  ],
  teacher: [
    { to: "/app/teacher", label: "Обзор", icon: "home", end: true },
    { to: "/app/teacher/classes", label: "Классы", icon: "classes" },
    { to: "/app/teacher/students", label: "Ученики", icon: "students" },
    { to: "/app/teacher/assignments", label: "Задания", icon: "assignments" },
    { to: "/app/teacher/schedule", label: "Расписание", icon: "schedule" },
    { to: "/app/teacher/library", label: "Библиотека", icon: "library" },
  ],
  admin: [
    { to: "/app/admin", label: "Обзор", icon: "home", end: true },
    { to: "/app/admin/users", label: "Пользователи", icon: "users" },
    { to: "/app/admin/topics", label: "Предметы и темы", icon: "topics" },
    { to: "/app/admin/courses", label: "Курсы", icon: "classes" },
    { to: "/app/admin/textbooks", label: "Пособия и книги", icon: "library" },
    { to: "/app/admin/padruchnik", label: "e-padruchnik", icon: "textbooks" },
    { to: "/app/admin/orgs", label: "Организация", icon: "orgs" },
    { to: "/app/admin/shop", label: "Магазин", icon: "shop" },
    { to: "/app/admin/youtube", label: "YouTube", icon: "youtube" },
    { to: "/app/admin/ai", label: "ИИ-помощник", icon: "ai" },
    { to: "/app/admin/map", label: "Карта", icon: "map" },
    { to: "/app/admin/audit", label: "Журнал", icon: "audit" },
  ],
};

const BOTTOM = {
  student: ["/app", "/app/learn", "/app/assignments", "/app/library", "/app/shop"],
  parent: ["/app/parent", "/app/parent/map", "/app/parent/help", "/app/parent/library", "/app/parent/assignments"],
  teacher: ["/app/teacher", "/app/teacher/classes", "/app/teacher/assignments", "/app/teacher/library"],
  admin: ["/app/admin", "/app/admin/users", "/app/admin/topics", "/app/admin/shop"],
};

function useClickOutside(ref, onClose) {
  useEffect(() => {
    const handler = (event) => {
      if (ref.current && !ref.current.contains(event.target)) onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [ref, onClose]);
}

function SidebarBody({ role, items, onNavigate }) {
  const { session, signOut } = useSession();
  const navigate = useNavigate();
  const learner = session?.learner;
  const user = session?.user;
  const isStudent = role === "student";
  const level = learner ? Math.floor((learner.xp_total || learner.xp || 0) / 250) + 1 : 1;
  const levelProgress = learner ? ((learner.xp_total || learner.xp || 0) % 250) / 250 : 0;

  return (
    <div className="flex h-full flex-col gap-5 px-4 py-5">
      <div className="flex items-center justify-between px-1">
        <Link to={isStudent ? "/app" : role === "parent" ? "/app/parent" : role === "teacher" ? "/app/teacher" : "/app/admin"} onClick={onNavigate}>
          <Logo />
        </Link>
        <button className="icon-btn lg:hidden" onClick={onNavigate} aria-label="Закрыть меню">
          <X size={18} />
        </button>
      </div>

      <div className="rounded-2xl border border-white/8 bg-gradient-to-br from-white/[0.07] to-transparent p-3.5">
        <div className="flex items-center gap-3">
          <Avatar emoji={isStudent ? learner?.avatar || user?.avatar : user?.avatar || "👤"} size={42} seed={user?.login} ring />
          <div className="min-w-0">
            <p className="truncate text-sm font-bold text-white">
              {user?.first_name || learner?.name || "Пользователь"}
            </p>
            <p className="truncate text-[11px] text-mist-500">
              {ROLE_LABEL[role] || role}
              {isStudent && learner?.grade ? ` · ${learner.grade} класс` : ""}
            </p>
          </div>
        </div>
        {isStudent && (
          <div className="mt-3">
            <div className="mb-1.5 flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-mist-500">
              <span>Уровень {level}</span>
              <Xp value={learner?.xp_total ?? learner?.xp ?? 0} className="text-[10px]" />
            </div>
            <div className="progress h-1.5">
              <span style={{ width: `${Math.round(levelProgress * 100)}%` }} />
            </div>
          </div>
        )}
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto no-scrollbar">
        {items.map((item) => {
          const Icon = ICONS[item.icon] || Sparkles;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={onNavigate}
              className={({ isActive }) => `side-link ${isActive ? "active" : ""}`}
            >
              <Icon size={18} strokeWidth={1.9} />
              <span className="flex-1">{item.label}</span>
              <ChevronRight size={14} className="opacity-0 transition group-[.active]:opacity-60" />
            </NavLink>
          );
        })}
      </nav>

      <div className="space-y-0.5 border-t border-white/7 pt-3">
        <NavLink
          to="/app/profile"
          onClick={onNavigate}
          className={({ isActive }) => `side-link ${isActive ? "active" : ""}`}
        >
          <UserRound size={18} strokeWidth={1.9} />
          Профиль
        </NavLink>
        <button
          className="side-link w-full text-left"
          onClick={async () => {
            onNavigate?.();
            await signOut();
            navigate("/login");
          }}
        >
          <LogOut size={18} strokeWidth={1.9} />
          Выйти
        </button>
      </div>

      <div className="rounded-2xl border border-iris-400/20 bg-iris-500/[0.07] p-3.5">
        <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-iris-300">
          <ShieldCheck size={14} /> Безопасно
        </div>
        <p className="mt-1.5 text-[11px] leading-relaxed text-mist-500">
          Данные видны только вам и тем, кому вы разрешили.
        </p>
      </div>
    </div>
  );
}

export default function Shell() {
  const { session } = useSession();
  const location = useLocation();
  const [drawer, setDrawer] = useState(false);
  const [menu, setMenu] = useState(false);
  const menuRef = useRef(null);
  const role = session?.user?.role || "student";
  const items = NAV[role] || NAV.student;
  const learner = session?.learner;
  const user = session?.user;

  const { data: notifications } = useApi("/notifications", { ttl: 30_000 });
  const unread = notifications?.unread || 0;

  useClickOutside(menuRef, () => setMenu(false));

  useEffect(() => {
    setDrawer(false);
    setMenu(false);
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [location.pathname]);

  const current = useMemo(() => {
    const matched = [...items]
      .filter((item) => {
        if (item.end) return location.pathname === item.to;
        return location.pathname.startsWith(item.to);
      })
      .sort((a, b) => b.to.length - a.to.length)[0];
    return matched?.label || "Кабинет";
  }, [items, location.pathname]);

  const bottom = (BOTTOM[role] || []).map((to) => items.find((item) => item.to === to)).filter(Boolean);

  return (
    <div className={`relative z-10 min-h-screen role-${role}`}>
      <div className="aurora" aria-hidden="true">
        <span className="aurora__orb aurora__orb--a" />
        <span className="aurora__orb aurora__orb--b" />
        <span className="aurora__orb aurora__orb--c" />
      </div>

      {/* desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[268px] border-r border-white/7 bg-ink-950/55 backdrop-blur-2xl lg:block">
        <SidebarBody role={role} items={items} />
      </aside>

      {/* mobile drawer */}
      {drawer && (
        <div className="fixed inset-0 z-[70] lg:hidden">
          <div className="absolute inset-0 bg-ink-950/70 backdrop-blur-sm" onClick={() => setDrawer(false)} />
          <div className="glass-strong absolute inset-y-0 left-0 w-[300px] max-w-[86vw] fade-in">
            <SidebarBody role={role} items={items} onNavigate={() => setDrawer(false)} />
          </div>
        </div>
      )}

      <div className="relative z-10 min-w-0 lg:pl-[268px]">
        <header className="sticky top-0 z-30 border-b border-white/6 bg-ink-950/60 backdrop-blur-2xl">
          <div className="flex h-[68px] items-center gap-2 px-3 sm:gap-3 sm:px-6 lg:px-8">
            <button className="icon-btn lg:hidden" onClick={() => setDrawer(true)} aria-label="Меню">
              <Menu size={19} />
            </button>

            <div className="min-w-0 flex-1 overflow-hidden">
              <div className="flex min-w-0 items-center gap-2 text-[10px] font-bold uppercase tracking-[0.16em] text-mist-600">
                <span className="hidden truncate min-[380px]:inline">{todayLabel()}</span>
                <span className="hidden sm:inline">·</span>
                <span className="hidden sm:inline">Школьник</span>
              </div>
              <h1 className="truncate font-display text-[1.02rem] font-semibold text-white">{current}</h1>
            </div>

            <div className="flex items-center gap-2">
              {role === "student" && (
                <div className="hidden items-center gap-2 rounded-xl border border-white/8 bg-white/[0.035] px-3 py-2 sm:flex">
                  <span className="text-sm" aria-hidden="true">🪙</span>
                  <span className="text-sm font-bold text-white">
                    {Number(learner?.coins || 0).toLocaleString("ru-RU")}
                  </span>
                  <span className="h-4 w-px bg-white/10" />
                  <span className="text-sm" aria-hidden="true">✨</span>
                  <span className="text-sm font-bold text-white">
                    {Number(learner?.xp_balance ?? learner?.xp ?? 0).toLocaleString("ru-RU")}
                  </span>
                </div>
              )}

              {role === "student" && Number(learner?.streak_days || 0) > 0 && (
                <Badge tone="gold" className="hidden md:inline-flex">
                  🔥 {learner.streak_days} {learner.streak_days === 1 ? "день" : "дн"}
                </Badge>
              )}

              <Link to="/app/notifications" className="icon-btn relative" aria-label="Уведомления">
                <Bell size={18} />
                {unread > 0 && (
                  <span className="absolute -right-0.5 -top-0.5 inline-flex min-w-[18px] items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white shadow-[0_0_12px_rgba(244,63,94,.6)]">
                    {unread > 9 ? "9+" : unread}
                  </span>
                )}
              </Link>

              <div className="relative" ref={menuRef}>
                <button
                  onClick={() => setMenu((value) => !value)}
                  className="flex items-center gap-2 rounded-xl border border-white/8 bg-white/[0.035] p-1 pr-2 transition hover:border-white/15 hover:bg-white/[0.06]"
                  aria-label="Меню профиля"
                >
                  <Avatar
                    emoji={role === "student" ? learner?.avatar || "🦊" : user?.avatar || "👤"}
                    size={32}
                    seed={user?.login}
                  />
                  <span className="hidden max-w-[110px] truncate text-xs font-bold text-white sm:block">
                    {user?.first_name || learner?.name || "Профиль"}
                  </span>
                </button>
                {menu && (
                  <div className="glass-strong fade-up absolute right-0 top-[calc(100%+8px)] w-60 overflow-hidden rounded-2xl p-1.5">
                    <div className="border-b border-white/7 px-3 py-2.5">
                      <p className="truncate text-sm font-bold text-white">
                        {user?.first_name} {user?.last_name}
                      </p>
                      <p className="truncate text-[11px] text-mist-500">
                        @{user?.login} · {ROLE_LABEL[role]}
                      </p>
                    </div>
                    <Link
                      to="/app/profile"
                      onClick={() => setMenu(false)}
                      className="mt-1 flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-semibold text-mist-300 hover:bg-white/5 hover:text-white"
                    >
                      <UserRound size={16} /> Профиль
                    </Link>
                    <Link
                      to="/app/notifications"
                      onClick={() => setMenu(false)}
                      className="flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-semibold text-mist-300 hover:bg-white/5 hover:text-white"
                    >
                      <Bell size={16} /> Уведомления
                    </Link>
                    <Link
                      to="/"
                      onClick={() => setMenu(false)}
                      className="flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-semibold text-mist-300 hover:bg-white/5 hover:text-white"
                    >
                      <Sparkles size={16} /> О платформе
                    </Link>
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>

        <main className="min-w-0 max-w-full px-4 pb-28 pt-6 sm:px-6 lg:px-8 lg:pb-14 lg:pt-8">
          <div className="mx-auto max-w-[1220px]">
            <Outlet />
          </div>
        </main>
      </div>

      {bottom.length > 0 && (
        <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-white/8 bg-ink-950/85 px-2 pb-safe pt-1.5 backdrop-blur-2xl lg:hidden">
          <div className="mx-auto flex max-w-lg items-stretch justify-around">
            {bottom.map((item) => {
              const Icon = ICONS[item.icon] || Sparkles;
              const active = item.end ? location.pathname === item.to : location.pathname.startsWith(item.to);
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={`flex flex-1 flex-col items-center gap-1 rounded-xl px-1 py-1.5 text-[10px] font-bold transition ${
                    active ? "text-white" : "text-mist-600"
                  }`}
                >
                  <span
                    className={`flex h-8 w-10 items-center justify-center rounded-xl transition ${
                      active ? "bg-iris-500/20 text-iris-300 shadow-[inset_0_0_0_1px_rgba(167,139,250,.25)]" : ""
                    }`}
                  >
                    <Icon size={18} />
                  </span>
                  {item.label}
                </Link>
              );
            })}
          </div>
        </nav>
      )}
    </div>
  );
}
