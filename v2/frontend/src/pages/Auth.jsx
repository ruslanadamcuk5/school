import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  GraduationCap,
  HeartHandshake,
  KeyRound,
  Loader2,
  Lock,
  Mail,
  ShieldCheck,
  Sparkles,
  User,
  Users,
} from "lucide-react";
import { Badge, Button, Card, Field, Input, Logo, Select } from "../components/ui";
import { useSession } from "../lib/hooks";
import { ROLE_HOME } from "../lib/format";
import { ApiError } from "../lib/api";

function AuthShell({ children, title, subtitle, footer }) {
  return (
    <div className="relative z-10 flex min-h-screen">
      <div className="aurora" aria-hidden="true">
        <span className="aurora__orb aurora__orb--a" />
        <span className="aurora__orb aurora__orb--b" />
        <span className="aurora__orb aurora__orb--c" />
      </div>

      <aside className="relative hidden w-[46%] max-w-[640px] flex-col justify-between overflow-hidden border-r border-white/8 px-12 py-10 lg:flex">
        <div className="grid-lines pointer-events-none absolute inset-0 opacity-50" />
        <Link to="/" className="relative w-fit">
          <Logo size="lg" />
        </Link>

        <div className="relative max-w-lg">
          <div className="eyebrow">
            <span className="inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_10px_#34d399]" />
            Образовательная платформа
          </div>
          <h1 className="mt-7 font-display text-[2.7rem] font-semibold leading-[1.08] text-white">
            Учёба, которая
            <br />
            <span className="grad-text">вдохновляет.</span>
          </h1>
          <p className="mt-5 text-[15px] leading-relaxed text-mist-400">
            Одно пространство для ученика, родителя и учителя. Тренировки,
            задания, библиотека, мотивация и поддержка — без лишнего шума.
          </p>

          <div className="mt-9 space-y-3">
            {[
              [Sparkles, "Персональные тренировки и ИИ-объяснения"],
              [ShieldCheck, "Безопасные данные и родительский контроль"],
              [GraduationCap, "Программа 1–11 классов и библиотека"],
            ].map(([Icon, text]) => (
              <div key={text} className="flex items-center gap-3 text-sm text-mist-300">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-iris-300">
                  <Icon size={16} />
                </span>
                {text}
              </div>
            ))}
          </div>
        </div>

        <div className="relative flex items-center gap-4 text-xs text-mist-600">
          <span>© {new Date().getFullYear()} Школьник</span>
          <span className="h-1 w-1 rounded-full bg-mist-600" />
          <span>Сделано с уважением к детям</span>
        </div>
      </aside>

      <div className="flex flex-1 items-center justify-center px-5 py-10 sm:px-8">
        <div className="w-full max-w-[420px] fade-up">
          <div className="mb-8 flex items-center justify-between lg:hidden">
            <Link to="/"><Logo /></Link>
            <Link to="/" className="text-xs font-semibold text-mist-500 hover:text-white">На сайт</Link>
          </div>
          <div className="mb-7">
            <h2 className="font-display text-2xl font-semibold text-white sm:text-[1.7rem]">{title}</h2>
            {subtitle && <p className="mt-2 text-sm leading-relaxed text-mist-500">{subtitle}</p>}
          </div>
          {children}
          {footer && <div className="mt-6 text-center text-sm text-mist-500">{footer}</div>}
          <div className="mt-8 flex items-center justify-center gap-4 text-[11px] text-mist-600">
            <Link to="/" className="inline-flex items-center gap-1 hover:text-white">
              <ArrowLeft size={12} /> На главную
            </Link>
            <span className="h-1 w-1 rounded-full bg-mist-600" />
            <span>Безопасный вход</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export function LoginPage() {
  const { session, signIn } = useSession();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ login: "", password: "" });
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (session?.user?.role) {
      navigate(ROLE_HOME[session.user.role] || "/app", { replace: true });
    }
  }, [session, navigate]);

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      const data = await signIn(form.login.trim(), form.password);
      const fallback = ROLE_HOME[data.user?.role] || "/app";
      const from = location.state?.from;
      navigate(from && from.startsWith("/app") ? from : fallback, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось войти. Попробуйте ещё раз.");
    } finally {
      setPending(false);
    }
  };

  return (
    <AuthShell
      title="С возвращением"
      subtitle="Войдите, чтобы продолжить учиться, проверять задания и следить за прогрессом."
      footer={
        <>
          Нет аккаунта?{" "}
          <Link to="/register" className="font-bold text-iris-300 hover:text-white">
            Создать бесплатно
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        <Field label="Логин">
          <div className="relative">
            <User size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-mist-500" />
            <Input
              value={form.login}
              onChange={(event) => setForm({ ...form, login: event.target.value })}
              placeholder="a.ivanov"
              autoComplete="username"
              autoCapitalize="none"
              className="pl-10"
              required
            />
          </div>
        </Field>

        <Field label="Пароль">
          <div className="relative">
            <Lock size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-mist-500" />
            <Input
              type="password"
              value={form.password}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
              placeholder="••••••••"
              autoComplete="current-password"
              className="pl-10"
              required
            />
          </div>
        </Field>

        {error && (
          <div className="flex items-start gap-2 rounded-xl border border-rose-400/25 bg-rose-500/10 px-3.5 py-3 text-xs font-semibold text-rose-200">
            <KeyRound size={15} className="mt-0.5 shrink-0" />
            {error}
          </div>
        )}

        <Button type="submit" size="lg" className="w-full" loading={pending} icon={ArrowRight}>
          Войти в кабинет
        </Button>

        <div className="flex items-center gap-3 py-1">
          <span className="h-px flex-1 bg-white/8" />
          <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-mist-600">роли</span>
          <span className="h-px flex-1 bg-white/8" />
        </div>

        <div className="grid grid-cols-3 gap-2">
          {[
            [GraduationCap, "Ученик"],
            [HeartHandshake, "Родитель"],
            [Users, "Учитель"],
          ].map(([Icon, label]) => (
            <div key={label} className="flex flex-col items-center gap-1.5 rounded-xl border border-white/7 bg-white/[0.025] px-2 py-3 text-[11px] font-semibold text-mist-500">
              <Icon size={17} className="text-iris-400/80" />
              {label}
            </div>
          ))}
        </div>

        <p className="pt-1 text-center text-[11px] leading-relaxed text-mist-600">
          Один аккаунт — один профиль. Ученик входит по логину, который выдал
          учитель или указан при регистрации.
        </p>
      </form>
    </AuthShell>
  );
}

const ROLES = [
  {
    key: "student",
    label: "Ученик",
    icon: GraduationCap,
    text: "Тренировки, задания и награды",
    tone: "from-iris-500/20",
  },
  {
    key: "parent",
    label: "Родитель",
    icon: HeartHandshake,
    text: "Прогресс, карта и помощь",
    tone: "from-cyan-400/15",
  },
  {
    key: "teacher",
    label: "Учитель",
    icon: Users,
    text: "Классы, задания и библиотека",
    tone: "from-emerald-400/15",
  },
];

const GRADES = Array.from({ length: 11 }, (_, index) => index + 1);

export function RegisterPage() {
  const { session, signUp } = useSession();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const initialRole = useMemo(() => {
    const value = params.get("role");
    return ["student", "parent", "teacher"].includes(value) ? value : "student";
  }, [params]);

  const [role, setRole] = useState(initialRole);
  const [form, setForm] = useState({
    login: "",
    password: "",
    confirm: "",
    first_name: "",
    last_name: "",
    email: "",
    grade: "3",
    child_code: "",
  });
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    if (session?.user?.role) {
      navigate(ROLE_HOME[session.user.role] || "/app", { replace: true });
    }
  }, [session, navigate]);

  const set = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    if (form.password.length < 6) {
      setError("Пароль должен быть не короче 6 символов.");
      return;
    }
    if (form.password !== form.confirm) {
      setError("Пароли не совпадают.");
      return;
    }
    setPending(true);
    try {
      const data = await signUp({
        login: form.login.trim().toLowerCase(),
        password: form.password,
        role,
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        email: form.email.trim() || null,
        grade: role === "student" ? Number(form.grade) : undefined,
        child_code: role === "parent" ? form.child_code.trim().toUpperCase() : undefined,
      });
      navigate(ROLE_HOME[data.user?.role] || "/app", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Не удалось создать аккаунт. Попробуйте ещё раз.");
    } finally {
      setPending(false);
    }
  };

  return (
    <AuthShell
      title="Создать аккаунт"
      subtitle="Выберите роль — интерфейс и возможности настроятся автоматически."
      footer={
        <>
          Уже есть аккаунт?{" "}
          <Link to="/login" className="font-bold text-iris-300 hover:text-white">
            Войти
          </Link>
        </>
      }
    >
      <div className="mb-5 grid grid-cols-3 gap-2">
        {ROLES.map((item) => {
          const active = item.key === role;
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => setRole(item.key)}
              className={`relative overflow-hidden rounded-2xl border p-3 text-left transition ${
                active
                  ? "border-iris-400/40 bg-iris-500/12 shadow-[0_10px_30px_-16px_rgba(139,123,255,.8)]"
                  : "border-white/8 bg-white/[0.025] hover:border-white/16"
              }`}
            >
              <div className={`pointer-events-none absolute -right-6 -top-6 h-16 w-16 rounded-full bg-gradient-to-br ${item.tone} to-transparent blur-xl`} />
              <item.icon size={18} className={active ? "text-iris-300" : "text-mist-500"} />
              <p className={`mt-2 text-xs font-bold ${active ? "text-white" : "text-mist-300"}`}>{item.label}</p>
              <p className="mt-0.5 hidden text-[10px] leading-tight text-mist-600 sm:block">{item.text}</p>
            </button>
          );
        })}
      </div>

      <form onSubmit={submit} className="space-y-3.5">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Имя">
            <Input value={form.first_name} onChange={set("first_name")} placeholder="Иван" required maxLength={40} />
          </Field>
          <Field label="Фамилия">
            <Input value={form.last_name} onChange={set("last_name")} placeholder="Иванов" maxLength={40} />
          </Field>
        </div>

        <Field label="Логин" hint="3–24 символа: латиница, цифры, точка, дефис, подчёркивание">
          <div className="relative">
            <User size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-mist-500" />
            <Input
              value={form.login}
              onChange={set("login")}
              placeholder="ivan.2026"
              autoCapitalize="none"
              autoComplete="username"
              className="pl-10"
              required
              minLength={3}
              maxLength={24}
            />
          </div>
        </Field>

        {role === "student" && (
          <Field label="Класс">
            <Select value={form.grade} onChange={set("grade")}>
              {GRADES.map((grade) => (
                <option key={grade} value={grade}>{grade} класс</option>
              ))}
            </Select>
          </Field>
        )}

        {role === "parent" && (
          <Field label="Код ребёнка" hint="Необязательно. Можно привязать ребёнка позже по коду из его профиля.">
            <Input
              value={form.child_code}
              onChange={set("child_code")}
              placeholder="например, 844F64"
              maxLength={16}
              className="uppercase tracking-widest"
            />
          </Field>
        )}

        <Field label="Email" hint="Необязательно, для восстановления доступа">
          <div className="relative">
            <Mail size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-mist-500" />
            <Input
              type="email"
              value={form.email}
              onChange={set("email")}
              placeholder="you@example.com"
              autoComplete="email"
              className="pl-10"
            />
          </div>
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Пароль">
            <div className="relative">
              <Lock size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-mist-500" />
              <Input
                type={showPassword ? "text" : "password"}
                value={form.password}
                onChange={set("password")}
                placeholder="минимум 6"
                autoComplete="new-password"
                className="pl-10"
                required
                minLength={6}
              />
            </div>
          </Field>
          <Field label="Повторите">
            <Input
              type={showPassword ? "text" : "password"}
              value={form.confirm}
              onChange={set("confirm")}
              placeholder="ещё раз"
              autoComplete="new-password"
              required
            />
          </Field>
        </div>

        <label className="flex items-center gap-2 text-[11px] font-semibold text-mist-500">
          <input
            type="checkbox"
            checked={showPassword}
            onChange={(event) => setShowPassword(event.target.checked)}
            className="h-3.5 w-3.5 rounded border-white/20 bg-white/5 accent-violet-500"
          />
          Показать пароль
        </label>

        {error && (
          <div className="rounded-xl border border-rose-400/25 bg-rose-500/10 px-3.5 py-3 text-xs font-semibold text-rose-200">
            {error}
          </div>
        )}

        <Button type="submit" size="lg" className="w-full" loading={pending} icon={Sparkles}>
          Создать аккаунт
        </Button>

        <p className="text-center text-[10px] leading-relaxed text-mist-600">
          Создавая аккаунт, вы соглашаетесь с правилами платформы и обработкой
          данных для обучения. Мы не передаём данные третьим лицам.
        </p>
      </form>
    </AuthShell>
  );
}
