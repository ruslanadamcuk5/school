import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  BellRing,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Clock,
  Compass,
  Crosshair,
  Flame,
  Gamepad2,
  Heart,
  KeyRound,
  Library,
  LifeBuoy,
  LocateFixed,
  MapPin,
  MonitorSmartphone,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Star,
  Target,
  Trophy,
  UserPlus,
  Users,
  Volume2,
  VolumeX,
  Waves,
  Wifi,
  WifiOff,
} from "lucide-react";
import {
  Avatar,
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Input,
  Modal,
  PageHeader,
  Progress,
  Ring,
  SectionTitle,
  Select,
  Skeleton,
  StatCard,
  Tabs,
  Textarea,
} from "../components/ui";
import { useAction, useApi, toast } from "../lib/hooks";
import { api, getToken, invalidate } from "../lib/api";
import {
  formatDate,
  formatDateTime,
  levelInfo,
  plural,
  relativeTime,
  scoreTone,
} from "../lib/format";

/* ------------------------------------------------------------------ pieces */
function ChildrenTabs({ children, value, onChange }) {
  if (!children?.length) return null;
  return (
    <div className="no-scrollbar flex gap-1 overflow-x-auto rounded-2xl border border-white/8 bg-white/[0.025] p-1">
      {children.map((item) => {
        const child = item.user || item;
        const learner = item.learner || item;
        const active = Number(value) === Number(learner.id);
        return (
          <button
            key={learner.id || child.id}
            onClick={() => onChange(learner.id)}
            className={`flex shrink-0 items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold transition ${
              active ? "bg-white/10 text-white shadow-[inset_0_1px_0_rgba(255,255,255,.1)]" : "text-mist-500 hover:text-mist-100"
            }`}
          >
            <span className="text-base">{learner.avatar || child.avatar || "🦊"}</span>
            {child.first_name || learner.name || "Ребёнок"}
          </button>
        );
      })}
    </div>
  );
}

function WeekChart({ data = [] }) {
  const max = Math.max(1, ...data.map((item) => Number(item.attempts || 0)));
  return (
    <div className="flex h-32 items-end gap-1.5">
      {data.map((item) => {
        const attempts = Number(item.attempts || 0);
        const correct = Number(item.correct || 0);
        const height = Math.max(4, Math.round((attempts / max) * 100));
        const accuracy = attempts ? Math.round((correct / attempts) * 100) : 0;
        const label = String(item.day || "").slice(5);
        return (
          <div key={item.day} className="group flex min-w-0 flex-1 flex-col items-center gap-1.5">
            <div className="flex h-24 w-full items-end justify-center">
              <div
                className="relative w-full max-w-6 rounded-t-md bg-gradient-to-t from-iris-500/50 to-cyan-400/80 transition group-hover:from-iris-400/70"
                style={{ height: `${height}%` }}
                title={`${label}: ${attempts} ${plural(attempts, ["попытка", "попытки", "попыток"])}, точность ${accuracy}%`}
              />
            </div>
            <span className="text-[9px] font-semibold text-mist-600">{label}</span>
          </div>
        );
      })}
    </div>
  );
}

function levelOf(stats) {
  return stats?.level_info || levelInfo(stats?.xp || 0);
}

/* ------------------------------------------------------------------ dashboard */
export function ParentDashboard() {
  const { data, loading, error, refresh } = useApi("/parent/dashboard");
  const [linkOpen, setLinkOpen] = useState(false);
  const [code, setCode] = useState("");
  const { pending, run } = useAction();

  const children = data?.children || [];
  const stats = data?.stats || {};

  const linkChild = async () => {
    if (!code.trim()) {
      toast("Введите код из профиля ребёнка", "info");
      return;
    }
    try {
      await run(() => api.post("/parent/link", { code: code.trim() }));
      invalidate("/parent");
      await refresh();
      setLinkOpen(false);
      setCode("");
      toast("Ребёнок привязан", "success");
    } catch (err) {
      toast(err.message || "Не удалось привязать ребёнка", "error");
    }
  };

  if (loading && !data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-40 w-full" />
        <div className="grid gap-3 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => <Skeleton key={index} className="h-28" />)}
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Семейный кабинет"
        subtitle="Прогресс, местоположение и помощь — всё о ребёнке в одном месте, без лишних звонков."
        actions={
          <>
            <Button variant="ghost" icon={UserPlus} onClick={() => setLinkOpen(true)}>Добавить ребёнка</Button>
            <Link to="/app/parent/help"><Button icon={LifeBuoy}>Помочь сейчас</Button></Link>
          </>
        }
      />

      {error && <ErrorState error={error} onRetry={refresh} />}

      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard icon={Users} label="Детей в семье" value={stats.children ?? children.length} tone="iris" />
        <StatCard icon={Star} label="Звёзд вместе" value={stats.stars || 0} hint="За успешные темы" tone="gold" />
        <StatCard icon={Target} label="Попыток всего" value={stats.attempts || 0} hint="Каждая — шаг вперёд" tone="cyan" />
      </div>

      {children.length === 0 ? (
        <Card>
          <EmptyState
            icon="👨‍👩‍👧"
            title="Пока нет привязанных детей"
            text="Возьмите код в профиле ребёнка — он начинается с буквы и цифр. После привязки появится прогресс и карта."
            action={<Button icon={UserPlus} onClick={() => setLinkOpen(true)}>Привязать ребёнка</Button>}
          />
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {children.map((item) => {
            const child = item.user || {};
            const learner = item.learner || {};
            const childStats = item.stats || {};
            const level = levelInfo(childStats.xp || 0);
            const klass = item.classes?.[0];
            return (
              <Card key={learner.id || child.id} className="relative overflow-hidden p-5 sm:p-6">
                <div className="pointer-events-none absolute -right-16 -top-20 h-48 w-48 rounded-full bg-iris-500/15 blur-3xl" />
                <div className="relative flex items-start gap-4">
                  <Avatar emoji={learner.avatar || child.avatar || "🦊"} size={64} seed={child.login} ring />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-display text-lg font-semibold text-white">{learner.name || child.first_name}</h3>
                      <Badge tone="iris">{item.grade} класс</Badge>
                      {childStats.streak_days > 0 && (
                        <Badge tone="gold"><Flame size={11} /> {childStats.streak_days}</Badge>
                      )}
                    </div>
                    <p className="mt-1 truncate text-xs text-mist-500">
                      {klass ? `${klass.school_name} · ${klass.title}` : "Класс ещё не назначен"}
                      {klass?.teacher_first ? ` · ${klass.teacher_first} ${klass.teacher_last || ""}` : ""}
                    </p>
                    <div className="mt-3 max-w-xs">
                      <div className="mb-1 flex items-center justify-between text-[10px] font-bold text-mist-500">
                        <span>Уровень {level.level} · {level.title}</span>
                        <span>{level.percent}%</span>
                      </div>
                      <Progress value={level.percent} />
                    </div>
                  </div>
                </div>

                <div className="relative mt-5 grid grid-cols-3 gap-2">
                  {[
                    ["Точность", `${childStats.accuracy || 0}%`],
                    ["Звёзды", childStats.stars || 0],
                    ["Монеты", childStats.coins || 0],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-xl border border-white/7 bg-white/[0.025] px-3 py-2.5 text-center">
                      <p className="font-display text-base font-semibold text-white">{value}</p>
                      <p className="mt-0.5 text-[10px] font-bold uppercase tracking-wider text-mist-600">{label}</p>
                    </div>
                  ))}
                </div>

                <div className="relative mt-4 flex flex-wrap gap-2">
                  <Link to={`/app/parent/children/${learner.id}`} className="flex-1">
                    <Button variant="ghost" className="w-full" icon={Trophy}>Подробнее</Button>
                  </Link>
                  <Link to={`/app/parent/children/${learner.id}`}>
                    <Button variant="ghost" icon={MapPin}>Карта</Button>
                  </Link>
                  <Link to="/app/parent/help">
                    <Button icon={LifeBuoy}>Помощь</Button>
                  </Link>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        {[
          [Compass, "Карта и маршрут", "Где ребёнок сейчас и как прошёл день.", "/app/parent/map", "map"],
          [LifeBuoy, "Удалённая помощь", "Показать экран и подсказать прямо на телефоне.", "/app/parent/help", "help"],
          [Library, "Семейная библиотека", "Пособия класса и рекомендации учителя.", "/app/parent/library", "library"],
        ].map(([Icon, title, text, to, key]) => (
          <Link key={key} to={to}>
            <Card hover className="h-full p-5">
              <span className="inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-iris-400/20 bg-iris-500/10 text-iris-300">
                <Icon size={20} />
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

      <Modal
        open={linkOpen}
        onClose={() => setLinkOpen(false)}
        title="Привязать ребёнка"
        description="Код находится в профиле ребёнка в приложении «Школьник»."
        footer={
          <>
            <Button variant="ghost" onClick={() => setLinkOpen(false)}>Отмена</Button>
            <Button icon={KeyRound} loading={pending} onClick={linkChild}>Привязать</Button>
          </>
        }
      >
        <Field label="Код ребёнка" hint="Например, SCH-7K2M. Регистр не важен.">
          <Input value={code} onChange={(event) => setCode(event.target.value.toUpperCase())} placeholder="SCH-XXXX" autoFocus />
        </Field>
      </Modal>
    </div>
  );
}

/* ------------------------------------------------------------------ child */
export function ParentChild() {
  const { learnerId } = useParams();
  const navigate = useNavigate();
  const { data, loading, error, refresh } = useApi(`/parent/children/${learnerId}`);
  const { data: locations } = useApi("/parent/locations");
  const { pending, run } = useAction();
  const [tab, setTab] = useState("progress");
  const [form, setForm] = useState(null);
  const [resetOpen, setResetOpen] = useState(false);
  const [resetText, setResetText] = useState("");

  const learner = data?.learner;
  const stats = data?.stats || {};
  const topics = data?.topics || [];
  const results = data?.results || [];
  const weekly = data?.weekly || [];
  const level = levelOf(stats);

  useEffect(() => {
    if (!learner) return;
    setForm({
      name: learner.name || "",
      grade: learner.grade || 1,
      avatar: learner.avatar || "🦊",
      sound_on: Boolean(learner.sound_on),
      voice_on: Boolean(learner.voice_on),
      daily_limit: Number(learner.daily_limit || 0),
    });
  }, [learner]);

  const position = useMemo(
    () => (locations?.children || []).find((item) => Number(item.learner?.id) === Number(learnerId)),
    [locations, learnerId],
  );

  const save = async () => {
    if (!form) return;
    try {
      await run(() => api.patch(`/parent/children/${learnerId}`, { ...form, grade: Number(form.grade) }));
      invalidate("/parent");
      await refresh();
      toast("Настройки сохранены", "success");
    } catch (err) {
      toast(err.message || "Не удалось сохранить", "error");
    }
  };

  const reset = async () => {
    if (resetText.trim().toLowerCase() !== "сброс") {
      toast("Напишите слово «сброс» для подтверждения", "info");
      return;
    }
    try {
      await run(() => api.post(`/parent/children/${learnerId}/reset`, { confirm: "yes" }));
      setResetOpen(false);
      setResetText("");
      invalidate("/parent");
      await refresh();
      toast("Прогресс ребёнка сброшен", "success");
    } catch (err) {
      toast(err.message || "Не удалось сбросить прогресс", "error");
    }
  };

  if (loading && !data) {
    return <div className="space-y-4"><Skeleton className="h-36 w-full" /><Skeleton className="h-64 w-full" /></div>;
  }
  if (error || !learner) {
    return (
      <div className="space-y-4">
        <Button variant="plain" icon={ArrowLeft} onClick={() => navigate("/app/parent")}>К семье</Button>
        <ErrorState error={error} onRetry={refresh} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <button onClick={() => navigate("/app/parent")} className="inline-flex items-center gap-1.5 text-sm font-semibold text-mist-500 hover:text-white">
        <ArrowLeft size={15} /> К семье
      </button>

      <Card className="relative overflow-hidden p-6 sm:p-7">
        <div className="pointer-events-none absolute -right-20 -top-24 h-64 w-64 rounded-full bg-iris-500/20 blur-3xl" />
        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center">
          <Avatar emoji={learner.avatar || "🦊"} size={84} seed={data?.user?.login} ring />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-display text-2xl font-semibold text-white">{learner.name}</h1>
              <Badge tone="iris">{learner.grade} класс</Badge>
              {stats.streak_days > 0 && <Badge tone="gold"><Flame size={11} /> серия {stats.streak_days}</Badge>}
            </div>
            <p className="mt-1 text-sm text-mist-500">
              {data?.classes?.[0] ? `${data.classes[0].school_name} · ${data.classes[0].title}` : "Класс не назначен"}
            </p>
            <p className="mt-1 text-[11px] text-mist-600">
              {position?.last_point
                ? `Последняя точка: ${relativeTime(position.last_point.recorded_at)}`
                : "Геолокация пока не передавалась"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" icon={MapPin} onClick={() => navigate(`/app/parent/map?child=${learnerId}`)}>На карте</Button>
            <Button icon={LifeBuoy} onClick={() => navigate(`/app/parent/help?child=${learnerId}`)}>Помочь</Button>
          </div>
        </div>
      </Card>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Trophy} label="Уровень" value={level.level} hint={level.title} tone="iris" />
        <StatCard icon={Target} label="Точность" value={`${stats.accuracy || 0}%`} hint={`${stats.total_correct || 0} из ${stats.total_attempts || 0}`} tone="cyan" />
        <StatCard icon={Star} label="Звёзды" value={stats.topics_three_stars || 0} hint={`${stats.topics_started || 0} тем начато`} tone="gold" />
        <StatCard icon={Flame} label="Серия" value={stats.streak_days || 0} suffix={plural(stats.streak_days || 0, ["день", "дня", "дней"])} tone="green" />
      </div>

      <Tabs
        tabs={[
          { key: "progress", label: "Прогресс", count: topics.length },
          { key: "results", label: "Работы", count: results.length },
          { key: "settings", label: "Настройки" },
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === "progress" && (
        <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
          <Card className="p-5 sm:p-6">
            <SectionTitle eyebrow="Активность" title="Две недели занятий" subtitle="Столбик — попытки, цвет — точность." />
            {weekly.length ? <div className="mt-5"><WeekChart data={weekly} /></div> : <EmptyState icon="📈" title="Пока нет данных" text="Активность появится после первых тренировок." />}
            <div className="mt-5 grid grid-cols-3 gap-2">
              <div className="rounded-xl border border-white/7 bg-white/[0.025] p-3 text-center">
                <p className="font-display text-base font-semibold text-white">{stats.total_attempts || 0}</p>
                <p className="text-[10px] text-mist-600">попыток</p>
              </div>
              <div className="rounded-xl border border-white/7 bg-white/[0.025] p-3 text-center">
                <p className="font-display text-base font-semibold text-white">{stats.max_combo || 0}</p>
                <p className="text-[10px] text-mist-600">лучшее комбо</p>
              </div>
              <div className="rounded-xl border border-white/7 bg-white/[0.025] p-3 text-center">
                <p className="font-display text-base font-semibold text-white">{stats.perfect_rounds || 0}</p>
                <p className="text-[10px] text-mist-600">идеальных раундов</p>
              </div>
            </div>
          </Card>

          <Card className="p-5 sm:p-6">
            <SectionTitle eyebrow="Кругозор" title="Темы" />
            <div className="mt-4 space-y-2">
              {topics.length === 0 && <EmptyState icon="📚" title="Тем пока нет" text="Как только ребёнок начнёт заниматься, здесь появится прогресс." />}
              {topics.slice(0, 8).map((topic) => (
                <div key={topic.slug} className="rounded-xl border border-white/7 bg-white/[0.02] px-3.5 py-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-xs font-bold text-white">{topic.slug}</span>
                    <span className="text-[11px] font-bold text-amber-300">{"★".repeat(topic.stars || 0) || "—"}</span>
                  </div>
                  <div className="mt-1.5 flex items-center justify-between text-[10px] text-mist-600">
                    <span>{topic.correct || 0} из {topic.attempts || 0} верно</span>
                    <span>{topic.attempts ? Math.round((topic.correct / topic.attempts) * 100) : 0}%</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {tab === "results" && (
        <div className="space-y-2.5">
          {results.length === 0 && (
            <Card><EmptyState icon="📝" title="Работ пока нет" text="Когда ребёнок выполнит задание, результат появится здесь." /></Card>
          )}
          {results.map((result, index) => (
            <Card key={`${result.assignment_id}-${index}`} className="p-4 sm:p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <Ring value={result.percent || 0} size={56} stroke={6} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-bold text-white">{result.title}</p>
                  <p className="mt-0.5 text-[11px] text-mist-500">
                    {result.kind || "работа"} · {result.completed_at ? formatDateTime(result.completed_at) : "без даты"}
                  </p>
                </div>
                <Badge tone={scoreTone(result.percent)}>{result.score} / {result.max_score}</Badge>
              </div>
            </Card>
          ))}
        </div>
      )}

      {tab === "settings" && form && (
        <div className="grid gap-5 lg:grid-cols-2">
          <Card className="p-5 sm:p-6">
            <SectionTitle eyebrow="Профиль" title="Данные ребёнка" subtitle="Имя и аватар видны в приложении и в классе." />
            <div className="mt-5 space-y-4">
              <Field label="Имя">
                <Input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} maxLength={60} />
              </Field>
              <Field label="Класс">
                <Select value={form.grade} onChange={(event) => setForm((current) => ({ ...current, grade: Number(event.target.value) }))}>
                  {Array.from({ length: 11 }).map((_, index) => (
                    <option key={index + 1} value={index + 1}>{index + 1} класс</option>
                  ))}
                </Select>
              </Field>
              <Field label="Аватар">
                <div className="flex flex-wrap gap-2">
                  {["🦊", "🐻", "🐼", "🐨", "🦁", "🐯", "🐸", "🐧", "🦉", "🐝", "🦋"].map((avatar) => (
                    <button
                      key={avatar}
                      type="button"
                      onClick={() => setForm((current) => ({ ...current, avatar }))}
                      className={`flex h-10 w-10 items-center justify-center rounded-xl border text-xl transition ${
                        form.avatar === avatar ? "border-iris-400/60 bg-iris-500/20" : "border-white/8 bg-white/[0.03] hover:border-white/20"
                      }`}
                    >
                      {avatar}
                    </button>
                  ))}
                </div>
              </Field>
              <Button icon={Check} loading={pending} onClick={save}>Сохранить</Button>
            </div>
          </Card>

          <div className="space-y-5">
            <Card className="p-5 sm:p-6">
              <SectionTitle eyebrow="Помощь" title="Связь с ребёнком" subtitle="Звук и подсказки на телефоне ребёнка." />
              <div className="mt-4 space-y-2">
                {[
                  ["sound_on", Volume2, "Звуковой вызов", "Родитель может громко позвать ребёнка."],
                  ["voice_on", BellRing, "Голосовые подсказки", "Приложение подсказывает голосом."],
                ].map(([key, Icon, title, text]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setForm((current) => ({ ...current, [key]: !current[key] }))}
                    className="flex w-full items-center gap-3 rounded-xl border border-white/8 bg-white/[0.025] px-3.5 py-3 text-left"
                  >
                    <Icon size={16} className="text-iris-300" />
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-bold text-white">{title}</p>
                      <p className="mt-0.5 text-[11px] text-mist-500">{text}</p>
                    </div>
                    <span className={`relative h-5 w-9 rounded-full transition ${form[key] ? "bg-emerald-500/70" : "bg-white/10"}`}>
                      <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition ${form[key] ? "left-[18px]" : "left-0.5"}`} />
                    </span>
                  </button>
                ))}
                <Field label="Дневной лимит заданий" hint="0 — без ограничений.">
                  <Input
                    type="number"
                    min={0}
                    value={form.daily_limit}
                    onChange={(event) => setForm((current) => ({ ...current, daily_limit: Number(event.target.value) }))}
                  />
                </Field>
                <Button icon={Check} loading={pending} onClick={save}>Сохранить настройки</Button>
              </div>
            </Card>

            <Card className="p-5">
              <SectionTitle eyebrow="Осторожно" title="Сброс прогресса" />
              <p className="mt-2 text-[11px] leading-relaxed text-mist-500">
                Удаляет попытки, звёзды и достижения ребёнка. Настройки и аккаунт останутся.
              </p>
              <Button variant="danger" icon={RotateCcw} className="mt-4 w-full" onClick={() => setResetOpen(true)}>Сбросить прогресс</Button>
            </Card>
          </div>
        </div>
      )}

      <Modal
        open={resetOpen}
        onClose={() => setResetOpen(false)}
        title="Сбросить прогресс?"
        description="Это действие нельзя отменить."
        footer={
          <>
            <Button variant="ghost" onClick={() => setResetOpen(false)}>Отмена</Button>
            <Button variant="danger" loading={pending} onClick={reset}>Сбросить</Button>
          </>
        }
      >
        <Field label="Введите «сброс»" hint="Так мы убедимся, что это не случайное нажатие.">
          <Input value={resetText} onChange={(event) => setResetText(event.target.value)} placeholder="сброс" autoFocus />
        </Field>
      </Modal>
    </div>
  );
}

/* ------------------------------------------------------------------ map */
function embedUrl(map, lat, lon) {
  const zoom = Number(map?.zoom || 16);
  const span = Math.max(0.0015, 0.02 / Math.max(1, zoom - 8));
  const bbox = [lon - span, lat - span / 1.7, lon + span, lat + span / 1.7]
    .map((value) => value.toFixed(6))
    .join("%2C");
  return `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat.toFixed(6)}%2C${lon.toFixed(6)}`;
}

export function ParentMap() {
  const { data: overview, loading, error, refresh } = useApi("/parent/locations");
  const [childId, setChildId] = useState("");
  const [trail, setTrail] = useState(null);
  const [trailLoading, setTrailLoading] = useState(false);
  const { pending, run } = useAction();

  const children = overview?.children || [];
  const activeId = childId || children[0]?.learner?.id;
  const map = overview?.map || {};

  useEffect(() => {
    if (!activeId) return undefined;
    let alive = true;
    setTrailLoading(true);
    api.get(`/parent/children/${activeId}/location`)
      .then((payload) => alive && setTrail(payload))
      .catch(() => alive && setTrail(null))
      .finally(() => alive && setTrailLoading(false));
    return () => { alive = false; };
  }, [activeId]);

  const latest = trail?.latest || children.find((item) => Number(item.learner?.id) === Number(activeId))?.last_point;
  const points = trail?.points || [];
  const center = latest
    ? { lat: Number(latest.lat), lon: Number(latest.lon) }
    : { lat: Number(map.center_lat || 53.9023), lon: Number(map.center_lon || 27.5619) };
  const child = children.find((item) => Number(item.learner?.id) === Number(activeId));
  const summary = trail?.summary || {};

  const force = async () => {
    if (!activeId) return;
    try {
      const payload = await run(() => api.post(`/parent/children/${activeId}/location/force`, {}));
      toast(payload.message || "Запрос отправлен на телефон ребёнка", "success");
      invalidate("/parent");
      await refresh();
    } catch (err) {
      toast(err.message || "Не удалось запросить геолокацию", "error");
    }
  };

  if (loading && !overview) {
    return <div className="space-y-4"><Skeleton className="h-14 w-full" /><Skeleton className="h-[420px] w-full" /></div>;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Карта семьи"
        subtitle="Последняя точка и маршрут за сегодня. Геолокацию передаёт только телефон ребёнка."
        actions={<Badge tone="iris"><MapPin size={12} /> {children.length} {plural(children.length, ["ребёнок", "ребёнка", "детей"])}</Badge>}
      />

      {error && <ErrorState error={error} onRetry={refresh} />}
      <ChildrenTabs children={children} value={activeId} onChange={setChildId} />

      {children.length === 0 ? (
        <Card><EmptyState icon="🗺" title="Нет детей на карте" text="Привяжите ребёнка в семейном кабинете." action={<Link to="/app/parent"><Button>В кабинет</Button></Link>} /></Card>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[1.4fr_0.6fr]">
          <Card className="overflow-hidden p-0">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/8 px-5 py-4">
              <div className="flex items-center gap-3">
                <Avatar emoji={child?.learner?.avatar || "🦊"} size={40} />
                <div>
                  <p className="text-sm font-bold text-white">{child?.learner?.name || "Ребёнок"}</p>
                  <p className="text-[11px] text-mist-500">
                    {latest ? `Обновлено ${relativeTime(latest.recorded_at)}` : "Точек пока нет"}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={latest && !child?.stale ? "green" : "gold"}>
                  {latest && !child?.stale ? <Wifi size={11} /> : <WifiOff size={11} />}
                  {latest && !child?.stale ? "онлайн" : "нет свежих данных"}
                </Badge>
                <Button size="sm" variant="ghost" icon={LocateFixed} loading={pending} onClick={force}>Запросить</Button>
              </div>
            </div>
            <div className="relative h-[360px] bg-ink-950 sm:h-[440px]">
              <iframe
                title="Карта ребёнка"
                src={embedUrl(map, center.lat, center.lon)}
                className="h-full w-full border-0 opacity-90"
                loading="lazy"
                referrerPolicy="no-referrer"
              />
              {!latest && (
                <div className="pointer-events-none absolute inset-x-4 bottom-4 rounded-2xl border border-amber-400/20 bg-ink-950/85 px-4 py-3 backdrop-blur">
                  <p className="text-xs font-bold text-amber-200">Точка ещё не появилась</p>
                  <p className="mt-0.5 text-[11px] text-mist-400">Попросите ребёнка открыть приложение — геолокация включится автоматически.</p>
                </div>
              )}
            </div>
          </Card>

          <div className="space-y-5">
            <Card className="p-5">
              <SectionTitle eyebrow="Сегодня" title="Итоги дня" />
              <div className="mt-4 grid grid-cols-2 gap-2">
                {[
                  ["Точек", summary.points || 0],
                  ["Расстояние", `${((Number(summary.distance_m || 0)) / 1000).toFixed(1)} км`],
                  ["В движении", `${summary.duration_min || 0} мин`],
                  ["Макс. скорость", `${Math.round(Number(summary.max_speed || 0))} км/ч`],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-xl border border-white/7 bg-white/[0.025] px-3 py-2.5">
                    <p className="font-display text-sm font-semibold text-white">{value}</p>
                    <p className="mt-0.5 text-[10px] font-bold uppercase tracking-wider text-mist-600">{label}</p>
                  </div>
                ))}
              </div>
              <p className="mt-3 flex items-start gap-1.5 text-[10px] leading-relaxed text-mist-600">
                <ShieldCheck size={12} className="mt-0.5 shrink-0 text-emerald-300" />
                История хранится {overview?.retention_days || trail?.retention_days || 3} дня и видна только родителям.
              </p>
            </Card>

            <Card className="p-5">
              <SectionTitle eyebrow="Маршрут" title="Последние точки" action={trailLoading ? <RefreshCw size={14} className="animate-spin text-mist-500" /> : null} />
              <div className="mt-4 max-h-64 space-y-2 overflow-y-auto pr-1">
                {points.length === 0 && <p className="rounded-xl border border-white/7 bg-white/[0.02] px-3 py-4 text-center text-[11px] text-mist-500">Маршрут за сегодня пуст.</p>}
                {[...points].reverse().slice(0, 12).map((point, index) => (
                  <div key={`${point.recorded_at}-${index}`} className="flex items-center gap-2.5 rounded-xl border border-white/7 bg-white/[0.02] px-3 py-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
                    <div className="min-w-0 flex-1">
                      <p className="text-[11px] font-semibold text-white">{point.time || formatDateTime(point.recorded_at)}</p>
                      <p className="text-[10px] text-mist-600">
                        {Number(point.lat).toFixed(5)}, {Number(point.lon).toFixed(5)}
                        {point.battery != null ? ` · 🔋 ${point.battery}%` : ""}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ help */
export function ParentHelp() {
  const { data, loading } = useApi("/parent/children");
  const [childId, setChildId] = useState("");
  const [session, setSession] = useState(null);
  const [frame, setFrame] = useState("");
  const [sound, setSound] = useState(null);
  const [busy, setBusy] = useState(false);
  const { pending, run } = useAction();
  const frameRef = useRef("");

  const children = data?.children || [];
  const activeId = childId || children[0]?.learner?.id;
  const child = children.find((item) => Number(item.learner?.id) === Number(activeId));

  const setFrameUrl = useCallback((url) => {
    if (frameRef.current) URL.revokeObjectURL(frameRef.current);
    frameRef.current = url;
    setFrame(url);
  }, []);

  useEffect(() => () => {
    if (frameRef.current) URL.revokeObjectURL(frameRef.current);
  }, []);

  const loadFrame = useCallback(async (sessionId) => {
    try {
      const response = await fetch(`/api/v1/remote/frame?session_id=${sessionId}`, {
        headers: { Authorization: `Bearer ${getToken()}` },
        cache: "no-store",
      });
      if (!response.ok) return;
      const blob = await response.blob();
      setFrameUrl(URL.createObjectURL(blob));
    } catch {
      /* the child's phone may be between frames */
    }
  }, [setFrameUrl]);

  const poll = useCallback(async () => {
    if (!activeId) return;
    try {
      const payload = await api.get(`/remote/current?learner_id=${activeId}`);
      setSession(payload.session || null);
      if (payload.session?.status === "active" && payload.session?.has_frame) {
        loadFrame(payload.session.id);
      }
    } catch {
      /* keep the last known state */
    }
  }, [activeId, loadFrame]);

  useEffect(() => {
    setSession(null);
    setFrameUrl("");
    poll();
    const timer = setInterval(poll, 3500);
    return () => clearInterval(timer);
  }, [activeId, poll, setFrameUrl]);

  useEffect(() => {
    if (!activeId) return undefined;
    api.get(`/parent/children/${activeId}/sound`)
      .then((payload) => setSound(payload.command))
      .catch(() => setSound(null));
    return undefined;
  }, [activeId]);

  const start = async () => {
    if (!activeId) return;
    try {
      const payload = await run(() => api.post("/remote/start", { learner_id: Number(activeId) }));
      setSession(payload.session);
      toast("Запрос отправлен — ребёнок увидит его в приложении", "success");
    } catch (err) {
      toast(err.message || "Не удалось начать помощь", "error");
    }
  };

  const stop = async () => {
    if (!session?.id) return;
    try {
      await run(() => api.post("/remote/stop", { session_id: session.id }));
      setSession(null);
      setFrameUrl("");
      toast("Сессия помощи завершена", "success");
    } catch (err) {
      toast(err.message || "Не удалось завершить", "error");
    }
  };

  const command = async (kind, extra = {}) => {
    if (!session?.id) return;
    try {
      await run(() => api.post("/remote/command", { session_id: session.id, kind, ...extra }));
    } catch (err) {
      toast(err.message || "Команда не отправилась", "error");
    }
  };

  const soundCall = async () => {
    if (!activeId) return;
    setBusy(true);
    try {
      const payload = await run(() => api.post(`/parent/children/${activeId}/sound`, {}));
      setSound(payload.command);
      toast(payload.message || "Звуковой вызов отправлен", "success");
    } catch (err) {
      toast(err.message || "Не удалось позвать ребёнка", "error");
    } finally {
      setBusy(false);
    }
  };

  const tap = (event) => {
    if (!session?.can_control) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
    const y = Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height));
    command("tap", { x, y });
  };

  if (loading && !data) {
    return <div className="space-y-4"><Skeleton className="h-14 w-full" /><Skeleton className="h-80 w-full" /></div>;
  }

  if (children.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader title="Удалённая помощь" subtitle="Покажите ребёнку, где нажать — прямо на его экране." />
        <Card><EmptyState icon="🤝" title="Нет привязанных детей" text="Сначала добавьте ребёнка в семейном кабинете." action={<Link to="/app/parent"><Button>В кабинет</Button></Link>} /></Card>
      </div>
    );
  }

  const active = session?.status === "active";
  const waiting = session?.status === "pending";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Удалённая помощь"
        subtitle="Попросите ребёнка разрешить показ экрана — и подсказывайте прямо на его телефоне."
        actions={<Badge tone={active ? "green" : waiting ? "gold" : "iris"}><MonitorSmartphone size={12} /> {active ? "экран подключён" : waiting ? "ждём разрешения" : "готова к запуску"}</Badge>}
      />

      <ChildrenTabs children={children} value={activeId} onChange={setChildId} />

      <div className="grid gap-5 lg:grid-cols-[1.25fr_0.75fr]">
        <Card className="overflow-hidden p-0">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/8 px-5 py-4">
            <div className="flex items-center gap-3">
              <Avatar emoji={child?.learner?.avatar || "🦊"} size={40} />
              <div>
                <p className="text-sm font-bold text-white">{child?.learner?.name || "Ребёнок"}</p>
                <p className="text-[11px] text-mist-500">{active ? "Экран транслируется" : waiting ? "Ребёнок должен разрешить показ" : "Нажмите «Начать помощь»"}</p>
              </div>
            </div>
            {active ? (
              <Button variant="danger" icon={WifiOff} loading={pending} onClick={stop}>Завершить</Button>
            ) : (
              <Button icon={MonitorSmartphone} loading={pending} onClick={start}>Начать помощь</Button>
            )}
          </div>

          <div className="relative flex min-h-[320px] items-center justify-center bg-ink-950 p-3 sm:min-h-[420px]">
            {frame ? (
              <img
                src={frame}
                alt="Экран ребёнка"
                onClick={tap}
                className={`max-h-[60vh] w-auto max-w-full rounded-xl border border-white/10 object-contain ${session?.can_control ? "cursor-crosshair" : ""}`}
              />
            ) : (
              <div className="px-6 py-16 text-center">
                <div className={`mx-auto flex h-20 w-20 items-center justify-center rounded-3xl border border-white/10 text-4xl ${active ? "animate-pulse-soft bg-emerald-500/10" : "bg-white/[0.04]"}`}>
                  {active ? "📱" : waiting ? "⏳" : "🤝"}
                </div>
                <p className="mt-4 font-display text-base font-semibold text-white">
                  {active ? "Ждём первый кадр" : waiting ? "Ребёнок видит запрос" : "Помощь в один клик"}
                </p>
                <p className="mx-auto mt-1.5 max-w-sm text-xs leading-relaxed text-mist-500">
                  {active
                    ? "Экран появится здесь автоматически. Обычно это занимает несколько секунд."
                    : waiting
                      ? "Попросите открыть приложение и нажать «Разрешить». Сессия активна 10 минут."
                      : "Мы отправим запрос на телефон ребёнка. Он разрешит показ экрана — и вы увидите, что происходит."}
                </p>
              </div>
            )}
            {active && (
              <span className="absolute left-3 top-3 inline-flex items-center gap-1.5 rounded-lg bg-emerald-500/20 px-2 py-1 text-[10px] font-bold text-emerald-200 backdrop-blur">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" /> live
              </span>
            )}
          </div>

          {active && (
            <div className="flex flex-wrap items-center gap-2 border-t border-white/8 px-5 py-4">
              <Button size="sm" variant="ghost" disabled={!session?.can_control} onClick={() => command("back")}><ChevronLeft size={15} /> Назад</Button>
              <Button size="sm" variant="ghost" disabled={!session?.can_control} onClick={() => command("home")}>Домой</Button>
              <Button size="sm" variant="ghost" disabled={!session?.can_control} onClick={() => command("recents")}>Недавние</Button>
              <Button size="sm" variant="ghost" disabled={!session?.can_control} onClick={() => command("notifications")}>Шторка</Button>
              <span className="ml-auto text-[10px] text-mist-600">
                {session?.can_control ? "Нажмите на экран, чтобы передать касание" : "Управление не разрешено"}
              </span>
            </div>
          )}
        </Card>

        <div className="space-y-5">
          <Card className="p-5 sm:p-6">
            <SectionTitle eyebrow="Звук" title="Позвать ребёнка" subtitle="Телефон зазвонит громко, даже если включён беззвучный режим." />
            <div className="mt-4 flex items-center gap-3">
              <span className={`flex h-14 w-14 items-center justify-center rounded-2xl border text-2xl ${sound?.status === "ringing" ? "border-amber-400/30 bg-amber-400/10" : "border-white/10 bg-white/[0.04]"}`}>
                {sound?.status === "ringing" ? "🔔" : "📣"}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-bold text-white">
                  {sound?.status === "ringing" ? "Звонит сейчас" : sound?.status === "pending" ? "Команда отправлена" : sound ? "Последний вызов" : "Ещё не вызывали"}
                </p>
                <p className="mt-0.5 text-[11px] text-mist-500">
                  {sound?.created_at ? formatDateTime(sound.created_at) : "Работает, когда приложение установлено"}
                </p>
              </div>
              <Button variant={sound?.status === "ringing" ? "gold" : "primary"} icon={Volume2} loading={busy || pending} onClick={soundCall}>Позвать</Button>
            </div>
            <p className="mt-3 flex items-start gap-1.5 text-[10px] leading-relaxed text-mist-600">
              <VolumeX size={12} className="mt-0.5 shrink-0" />
              Если телефон выключен или нет сети, команда придёт при следующем включении.
            </p>
          </Card>

          <Card className="p-5 sm:p-6">
            <SectionTitle eyebrow="Как это работает" title="Спокойно и безопасно" />
            <div className="mt-4 space-y-2.5">
              {[
                ["1", "Ребёнок разрешает показ", "Без его согласия экран не откроется."],
                ["2", "Вы видите происходящее", "Только экран приложения, не галерея и не переписка."],
                ["3", "Сессия закрывается сама", "Через 10 минут или по кнопке «Завершить»."],
              ].map(([number, title, text]) => (
                <div key={number} className="flex items-start gap-3 rounded-xl border border-white/7 bg-white/[0.02] px-3.5 py-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-iris-500/20 text-[11px] font-bold text-iris-200">{number}</span>
                  <div>
                    <p className="text-xs font-bold text-white">{title}</p>
                    <p className="mt-0.5 text-[11px] leading-relaxed text-mist-500">{text}</p>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-5">
            <div className="flex items-start gap-2.5 text-[11px] leading-relaxed text-mist-500">
              <ShieldCheck size={15} className="mt-0.5 shrink-0 text-emerald-300" />
              Все действия фиксируются в журнале. Помощь доступна только родителям, привязанным к ребёнку.
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ library */
export function ParentLibrary() {
  const [childId, setChildId] = useState("");
  const path = childId ? `/parent/library?child_id=${childId}` : "/parent/library";
  const { data, loading, error, refresh } = useApi(path);
  const [tab, setTab] = useState("books");
  const [search, setSearch] = useState("");

  const children = data?.children || [];
  const child = data?.child;
  const books = data?.books || [];
  const recommendations = data?.recommendations || [];
  const stats = data?.stats || {};

  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return books;
    return books.filter((book) => `${book.title} ${book.author} ${book.subject_name}`.toLowerCase().includes(query));
  }, [books, search]);

  if (loading && !data) {
    return <div className="space-y-4"><Skeleton className="h-14 w-full" /><div className="grid gap-3 sm:grid-cols-3">{Array.from({ length: 3 }).map((_, index) => <Skeleton key={index} className="h-24" />)}</div><Skeleton className="h-56 w-full" /></div>;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Семейная библиотека"
        subtitle="Пособия класса и рекомендации учителя. Открывайте вместе — так интереснее."
        actions={<Badge tone="iris"><Library size={12} /> {books.length} {plural(books.length, ["книга", "книги", "книг"])}</Badge>}
      />

      {children.length > 0 && (
        <div className="no-scrollbar flex gap-1 overflow-x-auto rounded-2xl border border-white/8 bg-white/[0.025] p-1">
          {children.map((item) => (
            <button
              key={item.id}
              onClick={() => setChildId(String(item.id))}
              className={`flex shrink-0 items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold transition ${
                Number(item.id) === Number(child?.id) ? "bg-white/10 text-white" : "text-mist-500 hover:text-white"
              }`}
            >
              <span>{item.avatar || "🦊"}</span>
              {item.first_name || item.login}
            </button>
          ))}
        </div>
      )}

      {error && <ErrorState error={error} onRetry={refresh} />}

      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard icon={BookOpen} label="Книг доступно" value={stats.books || books.length} tone="iris" />
        <StatCard icon={Sparkles} label="Рекомендации" value={stats.active || 0} hint="От учителя" tone="gold" />
        <StatCard icon={CheckCircle2} label="Прочитано" value={stats.done || 0} tone="green" />
      </div>

      <Tabs
        tabs={[
          { key: "books", label: "Книги", count: books.length },
          { key: "recs", label: "Рекомендации", count: recommendations.length },
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === "books" && (
        <Card className="p-4">
          <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Найти книгу или автора…" />
        </Card>
      )}

      {tab === "books" && visible.length === 0 && (
        <Card><EmptyState icon="📚" title={books.length ? "Ничего не нашлось" : "Книг пока нет"} text={books.length ? "Попробуйте другой запрос." : "Учитель добавит пособия — они появятся здесь."} /></Card>
      )}

      {tab === "books" && visible.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {visible.map((book) => (
            <Link key={book.id} to={`/app/library/${book.id}`} className="card card-hover group p-5">
              <div className="flex items-start justify-between gap-3">
                <span className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-2xl">{book.subject_icon || "📘"}</span>
                {book.grade ? <Badge>{book.grade} класс</Badge> : null}
              </div>
              <h3 className="mt-4 font-display text-sm font-semibold leading-snug text-white">{book.title}</h3>
              <p className="mt-1 truncate text-[11px] text-mist-500">{book.author || "Учебное пособие"}</p>
              <p className="mt-2 line-clamp-2 text-[11px] leading-relaxed text-mist-600">{book.description}</p>
              <span className="mt-3 inline-flex items-center gap-1 text-[11px] font-bold text-iris-300">
                Открыть <ArrowRight size={12} />
              </span>
            </Link>
          ))}
        </div>
      )}

      {tab === "recs" && (
        <div className="space-y-2.5">
          {recommendations.length === 0 && (
            <Card><EmptyState icon="💡" title="Рекомендаций пока нет" text="Учитель сможет порекомендовать книгу или тему — они появятся здесь." /></Card>
          )}
          {recommendations.map((rec) => (
            <Card key={rec.id} className="p-4 sm:p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-xl">📖</span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={rec.done ? "green" : "gold"}>{rec.done ? "прочитано" : "рекомендация"}</Badge>
                    {rec.topic_title ? <Badge tone="cyan">{rec.topic_title}</Badge> : null}
                  </div>
                  <p className="mt-1.5 text-sm font-bold text-white">{rec.title || "Книга"}</p>
                  {rec.note ? <p className="mt-1 text-[11px] text-mist-500">{rec.note}</p> : null}
                </div>
                <Link to={`/app/library/${rec.book_id}`}><Button size="sm" variant="ghost" icon={BookOpen}>Открыть</Button></Link>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Card className="p-5">
        <div className="flex items-start gap-2.5 text-[11px] leading-relaxed text-mist-500">
          <BookOpen size={15} className="mt-0.5 shrink-0 text-iris-300" />
          Пособия открываются постранично — можно читать с телефона или планшета без скачивания.
        </div>
      </Card>
    </div>
  );
}
