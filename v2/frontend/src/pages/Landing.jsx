import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  BookOpen,
  Brain,
  CheckCircle2,
  Gamepad2,
  GraduationCap,
  HeartHandshake,
  MapPin,
  Menu,
  ShieldCheck,
  Sparkles,
  Star,
  Trophy,
  Users,
  Wand2,
  X,
  Zap,
} from "lucide-react";
import { Badge, Button, Card, Logo, Ring } from "../components/ui";
import { useApi, useSession } from "../lib/hooks";
import { ROLE_HOME, subjectColor } from "../lib/format";

function Nav() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const { session } = useSession();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const links = [
    ["#features", "Возможности"],
    ["#subjects", "Предметы"],
    ["#roles", "Роли"],
    ["#how", "Как это работает"],
  ];

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-all duration-300 ${
        scrolled ? "border-b border-white/8 bg-ink-950/70 backdrop-blur-2xl" : "bg-transparent"
      }`}
    >
      <div className="mx-auto flex h-[74px] max-w-7xl items-center justify-between px-5 lg:px-8">
        <Link to="/" aria-label="Школьник — на главную">
          <Logo />
        </Link>

        <nav className="hidden items-center gap-7 lg:flex">
          {links.map(([href, label]) => (
            <a key={href} href={href} className="text-sm font-semibold text-mist-500 transition hover:text-white">
              {label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-2.5 lg:flex">
          {session ? (
            <Link to={ROLE_HOME[session.user?.role] || "/app"}>
              <Button icon={ArrowRight}>В кабинет</Button>
            </Link>
          ) : (
            <>
              <Link to="/login">
                <Button variant="ghost">Войти</Button>
              </Link>
              <Link to="/register">
                <Button icon={Sparkles}>Начать бесплатно</Button>
              </Link>
            </>
          )}
        </div>

        <button className="icon-btn lg:hidden" onClick={() => setOpen((v) => !v)} aria-label="Меню">
          {open ? <X size={18} /> : <Menu size={18} />}
        </button>
      </div>

      {open && (
        <div className="fade-in border-t border-white/8 bg-ink-950/95 px-5 py-4 backdrop-blur-2xl lg:hidden">
          <div className="flex flex-col gap-1">
            {links.map(([href, label]) => (
              <a
                key={href}
                href={href}
                onClick={() => setOpen(false)}
                className="rounded-xl px-3 py-2.5 text-sm font-semibold text-mist-300 hover:bg-white/5 hover:text-white"
              >
                {label}
              </a>
            ))}
          </div>
          <div className="mt-3 flex gap-2">
            <Link to="/login" className="flex-1">
              <Button variant="ghost" className="w-full">Войти</Button>
            </Link>
            <Link to={session ? ROLE_HOME[session.user?.role] || "/app" : "/register"} className="flex-1">
              <Button className="w-full">{session ? "В кабинет" : "Начать"}</Button>
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}

const FEATURES = [
  {
    icon: Brain,
    title: "Персональная траектория",
    text: "Алгоритм подбирает задания по уровню, а не по среднему классу. Ребёнок всегда решает то, что ему по силам — и чуть сложнее.",
    tone: "iris",
  },
  {
    icon: Wand2,
    title: "ИИ-помощник",
    text: "Объясняет тему человеческим языком, разбирает ошибку и подсказывает следующий шаг. Без готовых ответов — с пониманием.",
    tone: "cyan",
  },
  {
    icon: BookOpen,
    title: "Библиотека и учебники",
    text: "Пособия, темы и рекомендации учителя в одном месте. Чтение, тренировки и проверочные работы связаны между собой.",
    tone: "gold",
  },
  {
    icon: Trophy,
    title: "Мотивация без принуждения",
    text: "Монеты, уровни, питомцы и магазин наград. Прогресс виден, усилия вознаграждаются, а серия дней держит ритм.",
    tone: "green",
  },
  {
    icon: ShieldCheck,
    title: "Родительский контроль",
    text: "Успеваемость, задания, местоположение и удалённая помощь. Спокойствие родителя — без тотального контроля.",
    tone: "rose",
  },
  {
    icon: BarChart3,
    title: "Аналитика для учителя",
    text: "Классы, ученики, сданные работы и рекомендации. Видно, кому нужна поддержка, ещё до контрольной.",
    tone: "iris",
  },
];

const ROLES = [
  {
    icon: GraduationCap,
    title: "Ученику",
    text: "Учиться в своём темпе, получать награды и видеть, как растёт уровень.",
    points: ["Ежедневные задания", "Тренировки и боссы", "Питомец и магазин"],
    accent: "from-iris-500/25",
    href: "/register?role=student",
  },
  {
    icon: HeartHandshake,
    title: "Родителю",
    text: "Понимать, как дела у ребёнка, и помогать одним нажатием.",
    points: ["Дети и успеваемость", "Карта и геолокация", "Удалённая помощь"],
    accent: "from-cyan-400/20",
    href: "/register?role=parent",
  },
  {
    icon: Users,
    title: "Учителю",
    text: "Создавать задания, рекомендовать материалы и видеть прогресс класса.",
    points: ["Классы и ученики", "Задания за минуту", "Библиотека рекомендаций"],
    accent: "from-emerald-400/20",
    href: "/register?role=teacher",
  },
];

function HeroPreview({ stats }) {
  return (
    <div className="relative mx-auto w-full max-w-[520px]">
      <div className="pointer-events-none absolute -inset-10 -z-10 rounded-full bg-iris-500/20 blur-3xl" />

      <div className="glass-strong float-slow relative rounded-[28px] p-5 sm:p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-iris-400 to-cyan-300 text-sm text-ink-950">
              🦊
            </span>
            <div>
              <p className="text-sm font-bold text-white">Иван, 3 класс</p>
              <p className="text-[11px] text-mist-500">Уровень 12 · Новичок+</p>
            </div>
          </div>
          <Badge tone="gold">🔥 7 дней</Badge>
        </div>

        <div className="mt-5 grid grid-cols-[1fr_auto] items-center gap-4 rounded-2xl border border-white/8 bg-white/[0.03] p-4">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-mist-500">Прогресс недели</p>
            <p className="mt-1 font-display text-2xl font-semibold text-white">12 из 15 целей</p>
            <div className="mt-3 flex items-end gap-1.5">
              {[42, 66, 38, 82, 58, 92, 74].map((h, i) => (
                <span
                  key={i}
                  className="w-3 rounded-full bg-gradient-to-t from-iris-500/40 to-cyan-300/90"
                  style={{ height: `${Math.max(10, h * 0.42)}px`, opacity: i === 5 ? 1 : 0.62 }}
                />
              ))}
            </div>
          </div>
          <Ring value={80} size={84} stroke={7}>
            <span className="font-display text-base font-semibold text-white">80%</span>
            <span className="text-[9px] font-bold uppercase tracking-wider text-mist-500">цель</span>
          </Ring>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-3">
          <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-3.5">
            <div className="flex items-center gap-2 text-[11px] font-bold text-mist-500">
              <Zap size={13} className="text-amber-300" /> Сегодня
            </div>
            <p className="mt-2 text-sm font-semibold text-white">Таблица умножения</p>
            <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-white/8">
              <span className="block h-full w-[64%] rounded-full bg-gradient-to-r from-iris-400 to-cyan-300" />
            </div>
          </div>
          <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-3.5">
            <div className="flex items-center gap-2 text-[11px] font-bold text-mist-500">
              <Star size={13} className="text-iris-400" /> Награда
            </div>
            <p className="mt-2 font-display text-lg font-semibold text-white">+120 XP</p>
            <p className="text-[11px] text-emerald-300">Задание сдано ✓</p>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap gap-1.5">
          {["Математика", "Русский язык", "Человек и мир"].map((name) => (
            <span key={name} className="rounded-full border border-white/8 bg-white/[0.04] px-2.5 py-1 text-[11px] font-semibold text-mist-300">
              {name}
            </span>
          ))}
        </div>
      </div>

      <div className="glass absolute -right-3 top-16 hidden rounded-2xl px-3.5 py-2.5 text-xs font-semibold text-white sm:block">
        <span className="mr-1.5">🤖</span> ИИ объясняет шаг
      </div>
      <div className="glass absolute -left-4 bottom-14 hidden rounded-2xl px-3.5 py-2.5 text-xs font-semibold text-white sm:block">
        <span className="mr-1.5">🪙</span> +25 монет
      </div>
      <div className="glass absolute -bottom-4 right-10 hidden rounded-2xl px-3.5 py-2.5 text-xs font-semibold text-white sm:block">
        <span className="mr-1.5 text-emerald-300">●</span> Родитель рядом
      </div>

      <p className="mt-8 text-center text-[11px] font-semibold uppercase tracking-[0.18em] text-mist-600">
        {stats.users ? `${stats.users} аккаунтов уже учатся` : "Живой интерфейс платформы"}
      </p>
    </div>
  );
}

export default function Landing() {
  const { data } = useApi("/public/landing", { base: "/api/v2", ttl: 60_000 });
  const stats = data?.stats || {};
  const subjects = data?.subjects || [];

  return (
    <div className="relative z-10">
      <Nav />

      <main>
        {/* hero */}
        <section className="relative overflow-hidden px-5 pb-20 pt-32 lg:px-8 lg:pt-40">
          <div className="grid-lines pointer-events-none absolute inset-0 -z-10 opacity-60" />
          <div className="mx-auto grid max-w-7xl items-center gap-14 lg:grid-cols-[1.05fr_0.95fr]">
            <div className="fade-up">
              <div className="eyebrow">
                <span className="inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_10px_#34d399]" />
                Образовательная платформа нового поколения
              </div>
              <h1 className="mt-6 font-display text-[2.6rem] font-semibold leading-[1.06] tracking-tight text-white sm:text-6xl lg:text-[4.15rem]">
                Учёба, которая
                <br />
                <span className="grad-text">вдохновляет.</span>
              </h1>
              <p className="mt-6 max-w-xl text-[1.02rem] leading-relaxed text-mist-300 sm:text-lg">
                Школьник объединяет тренировки, домашние задания, библиотеку и
                поддержку близких в одном спокойном и красивом пространстве.
                Для учеников 1–11 классов, их родителей и учителей.
              </p>

              <div className="mt-8 flex flex-wrap items-center gap-3">
                <Link to="/register">
                  <Button size="lg" icon={Sparkles}>Создать аккаунт</Button>
                </Link>
                <Link to="/login">
                  <Button size="lg" variant="ghost" icon={ArrowRight}>У меня есть аккаунт</Button>
                </Link>
              </div>

              <div className="mt-9 flex flex-wrap gap-x-7 gap-y-3 text-sm text-mist-500">
                {[
                  [CheckCircle2, "Бесплатный старт"],
                  [ShieldCheck, "Безопасно для детей"],
                  [Zap, "Мгновенный отклик"],
                ].map(([Icon, text]) => (
                  <span key={text} className="inline-flex items-center gap-2">
                    <Icon size={16} className="text-iris-400" />
                    {text}
                  </span>
                ))}
              </div>
            </div>

            <div className="fade-up [animation-delay:120ms]">
              <HeroPreview stats={stats} />
            </div>
          </div>

          <div className="mx-auto mt-16 grid max-w-5xl grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              [stats.topics || 36, "тем в программе"],
              [stats.subjects || 8, "предметов"],
              ["1–11", "классы"],
              ["24/7", "доступ с любого устройства"],
            ].map(([value, label]) => (
              <div key={label} className="glass rounded-2xl px-4 py-4 text-center">
                <p className="font-display text-2xl font-semibold text-white">{value}</p>
                <p className="mt-1 text-[11px] font-semibold uppercase tracking-wider text-mist-500">{label}</p>
              </div>
            ))}
          </div>
        </section>

        {/* subjects marquee */}
        <section id="subjects" className="border-y border-white/6 bg-white/[0.015] py-10">
          <div className="mx-auto max-w-7xl px-5 lg:px-8">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-mist-500">
                Вся школьная программа — в одном месте
              </p>
              <Badge tone="iris">{subjects.length || 8} предметов</Badge>
            </div>
            <div className="mt-6 flex flex-wrap gap-2.5">
              {(subjects.length ? subjects : [{ slug: "math", name: "Математика", icon: "📐", color: "indigo" }]).map((subject) => {
                const tone = subjectColor(subject.color);
                return (
                  <div
                    key={subject.slug}
                    className="card card-hover flex items-center gap-3 px-4 py-3"
                    style={{ background: `linear-gradient(140deg, ${tone.soft}, rgba(255,255,255,.015))` }}
                  >
                    <span className="text-xl">{subject.icon}</span>
                    <div>
                      <p className="text-sm font-bold text-white">{subject.name}</p>
                      <p className="text-[11px] text-mist-500">{subject.topics_count || 0} тем</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* features */}
        <section id="features" className="px-5 py-24 lg:px-8">
          <div className="mx-auto max-w-7xl">
            <div className="max-w-2xl">
              <div className="eyebrow">Возможности</div>
              <h2 className="mt-5 font-display text-3xl font-semibold leading-tight text-white sm:text-[2.6rem]">
                Продумано до мелочей.
                <br />
                <span className="text-mist-500">Сделано с уважением к детям.</span>
              </h2>
              <p className="mt-5 text-mist-400">
                Мы не превращаем учёбу в гонку. Каждый элемент платформы помогает
                понять тему, почувствовать прогресс и вернуться завтра.
              </p>
            </div>

            <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map((feature, index) => (
                <Card key={feature.title} hover className={`p-6 ${index === 0 ? "sm:col-span-2 lg:col-span-1" : ""}`}>
                  <span
                    className={`inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 ${
                      feature.tone === "cyan"
                        ? "bg-cyan-400/10 text-cyan-300"
                        : feature.tone === "gold"
                          ? "bg-amber-400/10 text-amber-300"
                          : feature.tone === "green"
                            ? "bg-emerald-400/10 text-emerald-300"
                            : feature.tone === "rose"
                              ? "bg-rose-400/10 text-rose-300"
                              : "bg-iris-500/12 text-iris-400"
                    }`}
                  >
                    <feature.icon size={22} />
                  </span>
                  <h3 className="mt-5 font-display text-lg font-semibold text-white">{feature.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-mist-500">{feature.text}</p>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* roles */}
        <section id="roles" className="px-5 pb-24 lg:px-8">
          <div className="mx-auto max-w-7xl">
            <div className="flex flex-wrap items-end justify-between gap-5">
              <div>
                <div className="eyebrow">Одна платформа</div>
                <h2 className="mt-5 font-display text-3xl font-semibold text-white sm:text-[2.6rem]">
                  Три роли. <span className="grad-text">Одна цель.</span>
                </h2>
              </div>
              <p className="max-w-md text-sm leading-relaxed text-mist-500">
                У каждого — своё пространство и свои инструменты. Данные связаны,
                но никто не видит лишнего.
              </p>
            </div>

            <div className="mt-10 grid gap-4 lg:grid-cols-3">
              {ROLES.map((role) => (
                <Card key={role.title} hover className="relative overflow-hidden p-7">
                  <div className={`pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-gradient-to-br ${role.accent} to-transparent blur-2xl`} />
                  <span className="inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-iris-300">
                    <role.icon size={22} />
                  </span>
                  <h3 className="mt-5 font-display text-xl font-semibold text-white">{role.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-mist-500">{role.text}</p>
                  <ul className="mt-5 space-y-2.5">
                    {role.points.map((point) => (
                      <li key={point} className="flex items-center gap-2 text-sm text-mist-300">
                        <CheckCircle2 size={15} className="text-emerald-300" />
                        {point}
                      </li>
                    ))}
                  </ul>
                  <Link to={role.href} className="mt-6 inline-flex items-center gap-1.5 text-sm font-bold text-iris-300 hover:text-white">
                    Попробовать <ArrowRight size={15} />
                  </Link>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* how */}
        <section id="how" className="border-y border-white/6 bg-white/[0.015] px-5 py-24 lg:px-8">
          <div className="mx-auto max-w-7xl">
            <div className="mx-auto max-w-2xl text-center">
              <div className="eyebrow">Как это работает</div>
              <h2 className="mt-5 font-display text-3xl font-semibold text-white sm:text-[2.6rem]">
                Три шага до первого результата
              </h2>
            </div>
            <div className="mt-12 grid gap-4 md:grid-cols-3">
              {[
                { n: "01", icon: GraduationCap, title: "Создайте профиль", text: "Укажите роль, класс и имя. Это займёт меньше минуты." },
                { n: "02", icon: MapPin, title: "Пройдите диагностику", text: "Платформа подберёт темы и уровень сложности под ребёнка." },
                { n: "03", icon: Trophy, title: "Учитесь и растите", text: "Ежедневные тренировки, задания и награды формируют привычку." },
              ].map((step) => (
                <div key={step.n} className="relative rounded-3xl border border-white/8 bg-ink-900/40 p-7">
                  <span className="font-display text-4xl font-semibold text-white/10">{step.n}</span>
                  <step.icon size={22} className="mt-4 text-iris-400" />
                  <h3 className="mt-3 font-display text-lg font-semibold text-white">{step.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-mist-500">{step.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* cta */}
        <section className="px-5 py-24 lg:px-8">
          <div className="relative mx-auto max-w-6xl overflow-hidden rounded-[32px] border border-white/10 bg-gradient-to-br from-iris-600/25 via-ink-900 to-cyan-500/10 p-8 text-center sm:p-16">
            <div className="pointer-events-none absolute inset-0 opacity-60">
              <div className="absolute left-1/2 top-0 h-72 w-[680px] -translate-x-1/2 rounded-full bg-iris-500/25 blur-3xl" />
            </div>
            <div className="relative">
              <Badge tone="gold"><Gamepad2 size={13} /> Первый шаг — бесплатно</Badge>
              <h2 className="mx-auto mt-6 max-w-2xl font-display text-3xl font-semibold leading-tight text-white sm:text-[2.8rem]">
                Дайте ребёнку повод гордиться собой
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-mist-300">
                Создайте аккаунт и откройте первый урок уже сегодня. Без оплаты,
                без обязательств, с поддержкой на каждом шаге.
              </p>
              <div className="mt-8 flex flex-wrap justify-center gap-3">
                <Link to="/register">
                  <Button size="lg" icon={Sparkles}>Начать бесплатно</Button>
                </Link>
                <Link to="/login">
                  <Button size="lg" variant="ghost">Войти в кабинет</Button>
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-white/7 px-5 py-12 lg:px-8">
        <div className="mx-auto grid max-w-7xl gap-10 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div>
            <Logo />
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-mist-500">
              Общеобразовательная платформа для учеников 1–11 классов, родителей
              и учителей. Учёба, которая вдохновляет.
            </p>
            <p className="mt-5 text-xs text-mist-600">© {new Date().getFullYear()} Школьник. Все права защищены.</p>
          </div>
          {[
            ["Платформа", ["Возможности", "Предметы", "Роли", "Библиотека"]],
            ["Ученикам", ["Тренировки", "Задания", "Магазин", "Питомец"]],
            ["Помощь", ["Вход", "Регистрация", "Поддержка", "Конфиденциальность"]],
          ].map(([title, items]) => (
            <div key={title}>
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-mist-600">{title}</p>
              <ul className="mt-4 space-y-2.5">
                {items.map((item) => (
                  <li key={item}>
                    <Link to={item === "Вход" ? "/login" : item === "Регистрация" ? "/register" : "/"} className="text-sm text-mist-400 hover:text-white">
                      {item}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </footer>
    </div>
  );
}
