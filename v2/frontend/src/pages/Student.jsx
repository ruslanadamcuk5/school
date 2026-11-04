import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  Clock,
  Flame,
  Gamepad2,
  Library,
  Medal,
  PawPrint,
  Play,
  ShoppingBag,
  Sparkles,
  Star,
  Target,
  Timer,
  Trophy,
  Zap,
} from "lucide-react";
import { Badge, Button, Card, EmptyState, PageHeader, Progress, Ring, SectionTitle, Skeleton, StatCard } from "../components/ui";
import { useAction, useApi, useSession, toast } from "../lib/hooks";
import { api, invalidate } from "../lib/api";
import {
  formatDate,
  levelInfo,
  plural,
  subjectColor,
  taskTypeLabel,
  todayLabel,
} from "../lib/format";

function greeting() {
  const hour = new Date().getHours();
  if (hour < 6) return "Доброй ночи";
  if (hour < 12) return "Доброе утро";
  if (hour < 18) return "Добрый день";
  return "Добрый вечер";
}

function todayWeekday() {
  const day = new Date().getDay();
  return day === 0 ? 7 : day;
}

export default function StudentDashboard() {
  const { session, refreshSession } = useSession();
  const navigate = useNavigate();
  const learner = session?.learner;
  const user = session?.user;

  const { data: map, loading: mapLoading } = useApi("/map");
  const { data: assignments } = useApi("/assignments");
  const { data: schedule } = useApi("/schedule");
  const { data: topics } = useApi("/topics");
  const { data: daily } = useApi("/daily");
  const { data: pet } = useApi("/pet");
  const { pending, run } = useAction();

  const stats = map?.stats || {};
  const level = levelInfo(stats.xp ?? learner?.xp_total ?? 0);
  const grade = map?.grade || learner?.grade || 3;
  const weekday = todayWeekday();

  const myTopics = useMemo(() => {
    const all = topics?.topics || [];
    return all.filter((topic) => Number(topic.grade) === Number(grade));
  }, [topics, grade]);

  const myAssignments = useMemo(() => {
    const list = assignments?.assignments || [];
    return list
      .filter((item) => !item.result)
      .sort((a, b) => String(a.due_date || "9999").localeCompare(String(b.due_date || "9999")));
  }, [assignments]);

  const todayLessons = useMemo(
    () => (schedule?.schedule || []).filter((item) => Number(item.weekday) === weekday),
    [schedule, weekday],
  );

  const dailyTasks = daily?.tasks || map?.daily || [];
  const dailyDone = daily?.done ?? map?.daily_done;
  const pendingDaily = dailyTasks.filter((task) => !task.done);

  const startDaily = async () => {
    try {
      const data = await run(() =>
        api.post("/daily/start", { generator: pendingDaily[0]?.generator || "" }),
      );
      try { window.sessionStorage.setItem("school.lastMode", "daily"); } catch { /* ignore */ }
      invalidate("/daily");
      invalidate("/map");
      toast("Ежедневная тренировка началась", "success");
      navigate(`/app/play/${data.round_id}`);
    } catch (err) {
      toast(err.message || "Не удалось начать тренировку", "error");
    }
  };

  const startTopic = async (slug) => {
    try {
      const data = await run(() => api.post("/play/start", { topic_slug: slug }));
      try {
        window.sessionStorage.setItem("school.lastTopic", slug);
        window.sessionStorage.setItem("school.lastMode", "practice");
      } catch { /* ignore */ }
      navigate(`/app/play/${data.round_id}`);
    } catch (err) {
      toast(err.message || "Не удалось начать тренировку", "error");
    }
  };

  if (mapLoading && !map) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-40 w-full" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-28" />)}
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={`${greeting()}, ${user?.first_name || learner?.name || "друг"}!`}
        subtitle={`${todayLabel()} · ${grade} класс. Небольшой шаг сегодня — большой результат к концу года.`}
        actions={
          <>
            <Link to="/app/learn">
              <Button variant="ghost" icon={BookOpen}>Все предметы</Button>
            </Link>
            {pendingDaily.length > 0 && (
              <Button icon={Play} loading={pending} onClick={startDaily}>
                Начать день
              </Button>
            )}
          </>
        }
      />

      {/* hero */}
      <Card className="relative overflow-hidden p-6 sm:p-8">
        <div className="pointer-events-none absolute -right-24 -top-28 h-80 w-80 rounded-full bg-iris-500/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 left-1/3 h-72 w-72 rounded-full bg-cyan-400/10 blur-3xl" />
        <div className="relative grid gap-8 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="iris"><Sparkles size={12} /> Уровень {level.level}</Badge>
              {stats.streak_days > 0 && (
                <Badge tone="gold"><Flame size={12} /> серия {stats.streak_days} {plural(stats.streak_days, ["день", "дня", "дней"])}</Badge>
              )}
              {stats.accuracy > 0 && <Badge tone="cyan"><Target size={12} /> точность {stats.accuracy}%</Badge>}
            </div>

            <h2 className="mt-4 max-w-lg font-display text-2xl font-semibold leading-tight text-white sm:text-[2rem]">
              {dailyDone
                ? "План на сегодня выполнен. Отличная работа!"
                : `До цели дня осталось ${pendingDaily.length || dailyTasks.length} ${plural(pendingDaily.length || dailyTasks.length, ["задание", "задания", "заданий"])}`}
            </h2>
            <p className="mt-2 max-w-md text-sm leading-relaxed text-mist-400">
              {dailyDone
                ? "Можно закрепить тему тренировкой или заглянуть в библиотеку — прогресс сохранится."
                : "Короткие тренировки по 3–5 минут держат ритм и приносят опыт. Начните с первой задачи."}
            </p>

            <div className="mt-6 grid max-w-lg grid-cols-3 gap-2.5">
              {[
                ["🪙", stats.coins ?? learner?.coins ?? 0, "монет"],
                ["✨", stats.xp ?? learner?.xp_total ?? 0, "опыта"],
                ["⭐", stats.stars ?? 0, "звёзд"],
              ].map(([icon, value, label]) => (
                <div key={label} className="rounded-2xl border border-white/8 bg-white/[0.03] px-3 py-3">
                  <div className="flex items-center gap-1.5 text-lg">{icon}</div>
                  <p className="mt-1 font-display text-xl font-semibold text-white">{Number(value).toLocaleString("ru-RU")}</p>
                  <p className="text-[10px] font-bold uppercase tracking-wider text-mist-600">{label}</p>
                </div>
              ))}
            </div>

            <div className="mt-6 flex flex-wrap gap-2.5">
              {pendingDaily.length > 0 && (
                <Button icon={Zap} loading={pending} onClick={startDaily}>Продолжить план</Button>
              )}
              {myTopics[0] && (
                <Button variant="ghost" icon={Gamepad2} loading={pending} onClick={() => startTopic(myTopics[0].slug)}>
                  Свободная тренировка
                </Button>
              )}
            </div>
          </div>

          <div className="flex flex-col items-center gap-4">
            <div className="relative">
              <div className="absolute inset-0 rounded-full bg-iris-500/20 blur-2xl" />
              <Ring value={level.percent} size={148} stroke={10}>
                <span className="font-display text-2xl font-semibold text-white">{level.level}</span>
                <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-mist-500">уровень</span>
                <span className="mt-1 text-[10px] font-semibold text-iris-300">{level.percent}%</span>
              </Ring>
            </div>
            <div className="text-center">
              <p className="text-xs font-semibold text-mist-500">
                {level.need > 0 ? `Ещё ${level.need} XP до уровня ${level.level + 1}` : "Максимальный уровень"}
              </p>
              <div className="mt-2 flex items-center justify-center gap-2 text-sm font-bold text-white">
                <span>{learner?.avatar || "🦊"}</span>
                {pet?.pet?.name || "Питомец ждёт"}
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* stats */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Trophy} label="Уровень" value={level.level} hint={`${stats.level_title || "Новичок"} · ${level.xp} XP`} tone="iris" />
        <StatCard icon={Flame} label="Серия дней" value={stats.streak_days || 0} suffix={plural(stats.streak_days || 0, ["день", "дня", "дней"])} hint="Заходите каждый день" tone="gold" />
        <StatCard icon={Target} label="Точность" value={`${stats.accuracy || 0}%`} hint={`${stats.total_correct || 0} верных из ${stats.total_attempts || 0}`} tone="cyan" />
        <StatCard icon={Medal} label="Звёзды" value={stats.stars || 0} hint="За успешные раунды" tone="green" />
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.25fr_0.75fr]">
        {/* daily + assignments */}
        <div className="min-w-0 space-y-5">
          <Card className="p-5 sm:p-6">
            <SectionTitle
              eyebrow="План дня"
              title="Ежедневные задания"
              subtitle={dailyDone ? "Все задачи выполнены — отличный день." : "Три коротких задания, подобранные под ваш уровень."}
              action={dailyDone ? <Badge tone="green"><CheckCircle2 size={12} /> выполнено</Badge> : null}
            />
            <div className="mt-5 space-y-2.5">
              {dailyTasks.length === 0 && (
                <EmptyState icon="🌤" title="На сегодня заданий нет" text="Загляните позже или начните свободную тренировку по любому предмету." />
              )}
              {dailyTasks.map((task, index) => (
                <div
                  key={`${task.generator}-${index}`}
                  className={`flex items-center gap-3 rounded-2xl border px-3.5 py-3 transition ${
                    task.done ? "border-emerald-400/20 bg-emerald-500/[0.05]" : "border-white/8 bg-white/[0.025] hover:border-white/16"
                  }`}
                >
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/8 bg-white/5 text-lg">
                    {task.icon || "✨"}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-bold text-white">{task.topic || "Тренировка"}</p>
                    <p className="truncate text-[11px] text-mist-500">{task.label || "задание"}</p>
                  </div>
                  {task.done ? (
                    <span className={`badge ${task.correct ? "badge-green" : "badge-rose"}`}>
                      {task.correct ? "верно" : "разобрано"}
                    </span>
                  ) : (
                    <Button
                      size="sm"
                      variant="ghost"
                      icon={Play}
                      loading={pending}
                      onClick={() => startDaily()}
                    >
                      Решить
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </Card>

          <Card className="p-5 sm:p-6">
            <SectionTitle
              eyebrow="Школа"
              title="Активные задания"
              subtitle="Работы от учителя с указанным сроком сдачи."
              action={<Link to="/app/assignments" className="text-sm font-bold text-iris-300 hover:text-white">Все задания →</Link>}
            />
            <div className="mt-5 space-y-2.5">
              {myAssignments.length === 0 && (
                <EmptyState icon="✅" title="Нет новых заданий" text="Когда учитель опубликует работу, она появится здесь и в уведомлениях." />
              )}
              {myAssignments.slice(0, 3).map((item) => (
                <Link
                  key={item.id}
                  to={`/app/assignments/${item.id}`}
                  className="flex items-center gap-3 rounded-2xl border border-white/8 bg-white/[0.025] px-3.5 py-3 transition hover:border-iris-400/30 hover:bg-white/[0.045]"
                >
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/8 bg-white/5 text-lg">
                    {item.subject_icon || "📘"}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-bold text-white">{item.title}</p>
                    <p className="truncate text-[11px] text-mist-500">
                      {item.subject_name} · {item.questions_count} {plural(item.questions_count, ["задание", "задания", "заданий"])}
                      {item.due_date ? ` · до ${formatDate(item.due_date)}` : ""}
                    </p>
                  </div>
                  {item.overdue ? <Badge tone="rose">просрочено</Badge> : <Badge tone="iris"><Clock size={11} /> {taskTypeLabel(item.task_type)}</Badge>}
                  <ArrowRight size={15} className="shrink-0 text-mist-600" />
                </Link>
              ))}
            </div>
          </Card>

          <Card className="p-5 sm:p-6">
            <SectionTitle
              eyebrow="Продолжить"
              title={`Учимся в ${grade} классе`}
              subtitle="Темы по текущей программе. Каждая — с тренировкой и объяснением."
              action={<Link to="/app/learn" className="text-sm font-bold text-iris-300 hover:text-white">Все темы →</Link>}
            />
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              {myTopics.slice(0, 4).map((topic) => {
                const tone = subjectColor(topic.color);
                return (
                  <Link
                    key={topic.slug}
                    to={`/app/learn/${topic.slug}`}
                    className="group relative overflow-hidden rounded-2xl border border-white/8 p-4 transition hover:border-iris-400/30"
                    style={{ background: `linear-gradient(150deg, ${tone.soft}, rgba(255,255,255,.015))` }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-ink-900/40 text-lg">
                        {topic.icon || "📖"}
                      </span>
                      <span className="badge">{topic.kind === "reading" ? "чтение" : "практика"}</span>
                    </div>
                    <p className="mt-3 text-sm font-bold leading-snug text-white">{topic.title}</p>
                    <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-mist-500">{topic.description}</p>
                    <span className="mt-3 inline-flex items-center gap-1 text-[11px] font-bold text-iris-300 opacity-0 transition group-hover:opacity-100">
                      Открыть <ArrowRight size={12} />
                    </span>
                  </Link>
                );
              })}
            </div>
          </Card>
        </div>

        {/* right column */}
        <div className="min-w-0 space-y-5">
          <Card className="p-5">
            <SectionTitle eyebrow="Сегодня" title="Расписание" action={<Link to="/app/schedule" className="text-xs font-bold text-iris-300 hover:text-white">Всё →</Link>} />
            <div className="mt-4 space-y-2">
              {todayLessons.length === 0 && (
                <p className="rounded-xl border border-white/7 bg-white/[0.02] px-3 py-4 text-center text-xs text-mist-500">
                  На сегодня уроков нет.
                </p>
              )}
              {todayLessons.map((lesson) => (
                <div key={lesson.id} className="flex items-center gap-3 rounded-xl border border-white/7 bg-white/[0.02] px-3 py-2.5">
                  <div className="w-12 text-center">
                    <p className="text-[11px] font-bold text-white">{lesson.time_start}</p>
                    <p className="text-[9px] text-mist-600">{lesson.time_end}</p>
                  </div>
                  <span className="h-8 w-px bg-white/10" />
                  <span className="text-base">{lesson.subject_icon || "📘"}</span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-bold text-white">{lesson.subject_name}</p>
                    <p className="truncate text-[10px] text-mist-500">{lesson.topic_title || lesson.note || "Урок"}</p>
                  </div>
                  {lesson.topic_slug && (
                    <Link to={`/app/learn/${lesson.topic_slug}`} className="icon-btn h-8 w-8">
                      <ArrowRight size={14} />
                    </Link>
                  )}
                </div>
              ))}
            </div>
          </Card>

          <Card className="relative overflow-hidden p-5">
            <div className="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full bg-amber-400/15 blur-2xl" />
            <SectionTitle eyebrow="Мотивация" title={pet?.pet ? pet.pet.name : "Заведите питомца"} />
            <div className="mt-5 flex items-center gap-4">
              <div className="flex h-20 w-20 items-center justify-center rounded-3xl border border-white/10 bg-gradient-to-br from-amber-300/20 to-iris-500/10 text-4xl">
                {pet?.pet?.emoji || "🥚"}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-white">
                  {pet?.pet ? `Настроение: ${pet.pet.mood || "хорошее"}` : "Яйцо ждёт заботы"}
                </p>
                <p className="mt-1 text-[11px] leading-relaxed text-mist-500">
                  {pet?.tip || "Питомец растёт вместе с вами: тренировки приносят опыт и монеты."}
                </p>
                <Link to="/app/pet" className="mt-3 inline-flex items-center gap-1 text-xs font-bold text-amber-300 hover:text-white">
                  {pet?.pet ? "Проведать" : "Открыть питомца"} <ArrowRight size={12} />
                </Link>
              </div>
            </div>
          </Card>

          <Card className="p-5">
            <SectionTitle eyebrow="Быстрый доступ" title="Куда дальше" />
            <div className="mt-4 grid grid-cols-2 gap-2">
              {[
                ["/app/assignments", ClipboardList, "Задания", "iris"],
                ["/app/library", Library, "Библиотека", "cyan"],
                ["/app/shop", ShoppingBag, "Магазин", "gold"],
                ["/app/pet", PawPrint, "Питомец", "green"],
              ].map(([to, Icon, label, tone]) => (
                <Link key={to} to={to} className="rounded-2xl border border-white/8 bg-white/[0.025] p-3.5 transition hover:border-iris-400/30 hover:bg-white/[0.05]">
                  <Icon size={17} className={tone === "gold" ? "text-amber-300" : tone === "green" ? "text-emerald-300" : tone === "cyan" ? "text-cyan-300" : "text-iris-300"} />
                  <p className="mt-2 text-xs font-bold text-white">{label}</p>
                </Link>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
