import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  BarChart3,
  BookOpen,
  CalendarDays,
  Check,
  CheckCircle2,
  ClipboardList,
  Clock,
  FileText,
  GraduationCap,
  Library,
  ListChecks,
  MapPin,
  Plus,
  RefreshCw,
  Search,
  Send,
  Sparkles,
  Star,
  Target,
  Trash2,
  Upload,
  UserRound,
  Users,
  X,
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
import { useAction, useApi, useSession, toast } from "../lib/hooks";
import { api, invalidate } from "../lib/api";
import {
  formatDate,
  formatDateTime,
  levelInfo,
  parseJsonArray,
  plural,
  relativeTime,
  scoreTone,
  taskTypeLabel,
  todayLabel,
} from "../lib/format";

const TODAY = (() => {
  const day = new Date().getDay();
  return day === 0 ? 7 : day;
})();

const WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];

function topicsOf(assignment) {
  return parseJsonArray(assignment?.topic_slugs, []);
}

function WeekBars({ data = [] }) {
  const max = Math.max(1, ...data.map((item) => Number(item.attempts || 0)));
  return (
    <div className="flex h-28 items-end gap-1.5">
      {data.map((item) => {
        const attempts = Number(item.attempts || 0);
        const correct = Number(item.correct || 0);
        return (
          <div key={item.day} className="flex min-w-0 flex-1 flex-col items-center gap-1">
            <div className="flex h-20 w-full items-end">
              <div
                className="w-full rounded-t-md bg-gradient-to-t from-iris-500/40 to-cyan-400/80"
                style={{ height: `${Math.max(4, Math.round((attempts / max) * 100))}%` }}
                title={`${String(item.day).slice(5)}: ${correct}/${attempts}`}
              />
            </div>
            <span className="text-[8px] font-semibold text-mist-600">{String(item.day).slice(8)}</span>
          </div>
        );
      })}
    </div>
  );
}

function statusTone(status) {
  if (status === "опубликована") return "green";
  if (status === "закрыта") return "rose";
  return "gold";
}

function ClassCard({ klass, students = 0 }) {
  return (
    <Link to={`/app/teacher/classes/${klass.id}`}>
      <Card hover className="group relative h-full overflow-hidden p-5">
        <div className="pointer-events-none absolute -right-10 -top-14 h-36 w-36 rounded-full bg-iris-500/15 blur-2xl" />
        <div className="relative flex items-start justify-between gap-3">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/5 font-display text-lg font-semibold text-white">
            {klass.grade}
          </span>
          <Badge tone="iris">{students ?? klass.students_count ?? 0} {plural(students ?? klass.students_count ?? 0, ["ученик", "ученика", "учеников"])}</Badge>
        </div>
        <h3 className="mt-4 font-display text-base font-semibold text-white">{klass.title || `${klass.grade} «${klass.letter}»`}</h3>
        <p className="mt-1 truncate text-[11px] text-mist-500">{klass.school_name || "Школа"}</p>
        <p className="mt-0.5 text-[10px] text-mist-600">{klass.city_name || ""} · {klass.year || ""}</p>
        <span className="mt-4 inline-flex items-center gap-1 text-[11px] font-bold text-iris-300 opacity-80 transition group-hover:opacity-100">
          Открыть класс <ArrowRight size={12} />
        </span>
      </Card>
    </Link>
  );
}

function AssignmentRow({ item, onResults, onPublish, onClose, onDelete, compact = false }) {
  const percent = item.students_count
    ? Math.round(((item.done_count || 0) / item.students_count) * 100)
    : 0;
  return (
    <Card className="p-4 sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-iris-300">
          <ClipboardList size={19} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-bold text-white">{item.title}</h3>
            <Badge tone={statusTone(item.status)}>{item.status}</Badge>
            <Badge>{taskTypeLabel(item.task_type)}</Badge>
            {item.overdue && <Badge tone="rose">срок прошёл</Badge>}
          </div>
          <p className="mt-1 text-[11px] text-mist-500">
            {item.class_id ? `${item.grade || ""} «${item.letter || ""}»` : item.student_first ? `${item.student_first} ${item.student_last || ""}` : "Весь класс"}
            {item.subject_name ? ` · ${item.subject_name}` : ""}
            {item.due_date ? ` · до ${formatDate(item.due_date)}` : ""}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-[10px] font-semibold text-mist-600">
            <span>{item.questions_count || 0} заданий</span>
            {item.time_limit ? <span>· {item.time_limit} мин</span> : null}
            <span>· сдали {item.done_count || 0} из {item.students_count || 0}</span>
          </div>
          <div className="mt-2 max-w-sm"><Progress value={percent} className="h-1.5" /></div>
        </div>
        {!compact && (
          <div className="flex flex-wrap gap-1.5">
            <Button size="sm" variant="ghost" icon={BarChart3} onClick={() => onResults(item)}>Итоги</Button>
            {item.status !== "опубликована" && item.status !== "закрыта" && (
              <Button size="sm" variant="ghost" icon={Send} onClick={() => onPublish(item)}>Опубликовать</Button>
            )}
            {item.status === "опубликована" && (
              <Button size="sm" variant="ghost" icon={CheckCircle2} onClick={() => onClose(item)}>Закрыть</Button>
            )}
            <Button size="sm" variant="plain" icon={Trash2} onClick={() => onDelete(item)} />
          </div>
        )}
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ dashboard */
export function TeacherDashboard() {
  const { session } = useSession();
  const navigate = useNavigate();
  const { data, loading, error, refresh } = useApi("/teacher/dashboard");
  const stats = data?.stats || {};

  if (loading && !data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-40 w-full" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-28" />)}
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Кабинет учителя`}
        subtitle={`${todayLabel()} · ${session?.user?.first_name || "Коллега"}, всё по классам и работам собрано здесь.`}
        actions={
          <>
            <Link to="/app/teacher/schedule"><Button variant="ghost" icon={CalendarDays}>Расписание</Button></Link>
            <Button icon={Plus} onClick={() => navigate("/app/teacher/assignments?new=1")}>Новое задание</Button>
          </>
        }
      />

      {error && <ErrorState error={error} onRetry={refresh} />}

      <Card className="relative overflow-hidden p-6 sm:p-8">
        <div className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-iris-500/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-28 left-1/3 h-64 w-64 rounded-full bg-cyan-400/10 blur-3xl" />
        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center">
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="iris"><Sparkles size={12} /> {stats.classes || 0} {plural(stats.classes || 0, ["класс", "класса", "классов"])}</Badge>
              <Badge tone="cyan">{stats.students || 0} учеников</Badge>
              {stats.open_assignments > 0 && <Badge tone="gold">{stats.open_assignments} активных работ</Badge>}
            </div>
            <h2 className="mt-3 font-display text-xl font-semibold text-white sm:text-2xl">Класс под контролем — без лишней бумаги</h2>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-mist-400">
              Создавайте работы по темам, следите за сдачей и смотрите точность каждого ученика.
              Все результаты — сразу после выполнения.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:w-[430px]">
            {[
              [Users, "Ученики", stats.students || 0],
              [ClipboardList, "Задания", stats.assignments || 0],
              [BookOpen, "Книги", stats.books || 0],
              [Star, "Рекоменд.", stats.recommendations || 0],
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
        <StatCard icon={Users} label="Классов" value={stats.classes || 0} tone="iris" />
        <StatCard icon={GraduationCap} label="Учеников" value={stats.students || 0} tone="cyan" />
        <StatCard icon={ClipboardList} label="Работ" value={stats.assignments || 0} hint={`${stats.open_assignments || 0} опубликовано`} tone="gold" />
        <StatCard icon={Library} label="Книг в библиотеке" value={stats.books || 0} tone="green" />
      </div>

      <div>
        <SectionTitle
          eyebrow="Классы"
          title="Ваши классы"
          action={<Link to="/app/teacher/classes" className="text-[11px] font-bold text-iris-300">Все классы →</Link>}
        />
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {(data?.classes || []).slice(0, 6).map((klass) => <ClassCard key={klass.id} klass={klass} />)}
          {!data?.classes?.length && <Card className="sm:col-span-2 lg:col-span-3"><EmptyState icon="🏫" title="Классов пока нет" text="Администратор назначит классы — они появятся здесь." /></Card>}
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.15fr_0.85fr]">
        <div>
          <SectionTitle
            eyebrow="Работы"
            title="Последние задания"
            action={<Link to="/app/teacher/assignments" className="text-[11px] font-bold text-iris-300">Все задания →</Link>}
          />
          <div className="mt-4 space-y-2.5">
            {(data?.recent_assignments || []).map((item) => (
              <AssignmentRow
                key={item.id}
                item={item}
                compact
                onResults={() => navigate(`/app/teacher/assignments?results=${item.id}`)}
              />
            ))}
            {!data?.recent_assignments?.length && <Card><EmptyState icon="📝" title="Работ пока нет" text="Создайте первую работу — темы подберутся автоматически." action={<Button icon={Plus} onClick={() => navigate("/app/teacher/assignments?new=1")}>Создать</Button>} /></Card>}
          </div>
        </div>

        <div>
          <SectionTitle
            eyebrow="Ученики"
            title="Ваши ученики"
            action={<Link to="/app/teacher/students" className="text-[11px] font-bold text-iris-300">Все ученики →</Link>}
          />
          <Card className="mt-4 p-2">
            {(data?.students || []).slice(0, 8).map((student) => (
              <Link key={student.id} to={`/app/teacher/students/${student.id}`} className="flex items-center gap-3 rounded-xl px-3 py-2.5 transition hover:bg-white/5">
                <Avatar emoji={student.learner?.avatar || student.avatar || "🦊"} size={36} seed={student.login} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-bold text-white">{student.first_name} {student.last_name}</p>
                  <p className="text-[10px] text-mist-600">
                    {student.learner?.grade ? `${student.learner.grade} класс` : "класс не назначен"}
                    {student.stats?.accuracy ? ` · ${student.stats.accuracy}% точность` : ""}
                  </p>
                </div>
                <ArrowRight size={13} className="text-mist-600" />
              </Link>
            ))}
            {!data?.students?.length && <EmptyState icon="🧑‍🎓" title="Учеников пока нет" text="Они появятся после зачисления в класс." />}
          </Card>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ classes */
export function TeacherClasses() {
  const { data, loading, error, refresh } = useApi("/teacher/classes");
  const classes = data?.classes || [];

  return (
    <div className="space-y-6">
      <PageHeader title="Классы" subtitle="Все классы, которые вы ведёте. Внутри — ученики, работы и расписание." actions={<Badge tone="iris">{classes.length} {plural(classes.length, ["класс", "класса", "классов"])}</Badge>} />
      {error && <ErrorState error={error} onRetry={refresh} />}
      {loading && !data ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-44" />)}</div>
      ) : classes.length === 0 ? (
        <Card><EmptyState icon="🏫" title="Классов пока нет" text="Обратитесь к администратору школы." /></Card>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {classes.map((klass) => <ClassCard key={klass.id} klass={klass} />)}
        </div>
      )}
    </div>
  );
}

export function TeacherClass() {
  const { classId } = useParams();
  const navigate = useNavigate();
  const { data, loading, error, refresh } = useApi(`/teacher/classes/${classId}`);
  const [tab, setTab] = useState("students");
  const klass = data?.class;
  const students = data?.students || [];
  const assignments = data?.assignments || [];
  const schedule = data?.schedule || [];
  const { pending, run } = useAction();

  const publish = async (item) => {
    try {
      await run(() => api.post(`/teacher/assignments/${item.id}/publish`, {}));
      invalidate("/teacher");
      await refresh();
      toast("Работа опубликована", "success");
    } catch (err) {
      toast(err.message || "Не удалось опубликовать", "error");
    }
  };

  const close = async (item) => {
    try {
      await run(() => api.post(`/teacher/assignments/${item.id}/close`, {}));
      invalidate("/teacher");
      await refresh();
      toast("Работа закрыта", "success");
    } catch (err) {
      toast(err.message || "Не удалось закрыть", "error");
    }
  };

  if (loading && !data) return <div className="space-y-4"><Skeleton className="h-32 w-full" /><Skeleton className="h-64 w-full" /></div>;
  if (error || !klass) {
    return <div className="space-y-4"><Button variant="plain" icon={ArrowLeft} onClick={() => navigate("/app/teacher/classes")}>К классам</Button><ErrorState error={error} onRetry={refresh} /></div>;
  }

  const weekByDay = {};
  schedule.forEach((lesson) => {
    weekByDay[lesson.weekday] = weekByDay[lesson.weekday] || [];
    weekByDay[lesson.weekday].push(lesson);
  });

  return (
    <div className="space-y-6">
      <button onClick={() => navigate("/app/teacher/classes")} className="inline-flex items-center gap-1.5 text-sm font-semibold text-mist-500 hover:text-white"><ArrowLeft size={15} /> К классам</button>

      <Card className="relative overflow-hidden p-6 sm:p-7">
        <div className="pointer-events-none absolute -right-16 -top-20 h-56 w-56 rounded-full bg-iris-500/20 blur-3xl" />
        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center">
          <span className="flex h-20 w-20 items-center justify-center rounded-3xl border border-white/10 bg-white/5 font-display text-3xl font-semibold text-white">
            {klass.grade}
          </span>
          <div className="min-w-0 flex-1">
            <h1 className="font-display text-2xl font-semibold text-white">{klass.title || `${klass.grade} «${klass.letter}»`}</h1>
            <p className="mt-1 text-sm text-mist-500">{klass.school_name} · {klass.city_name} · {klass.year}</p>
            <p className="mt-1 text-[11px] text-mist-600">{students.length} учеников · {assignments.length} работ · {schedule.length} уроков в неделю</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="ghost" icon={CalendarDays} onClick={() => navigate(`/app/teacher/schedule?class=${klass.id}`)}>Расписание</Button>
            <Button icon={Plus} onClick={() => navigate(`/app/teacher/assignments?new=1&class=${klass.id}`)}>Новое задание</Button>
          </div>
        </div>
      </Card>

      <Tabs
        tabs={[
          { key: "students", label: "Ученики", count: students.length },
          { key: "assignments", label: "Задания", count: assignments.length },
          { key: "schedule", label: "Расписание", count: schedule.length },
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === "students" && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {students.map((student) => (
            <Link key={student.id} to={`/app/teacher/students/${student.id}`}>
              <Card hover className="h-full p-4">
                <div className="flex items-center gap-3">
                  <Avatar emoji={student.learner?.avatar || student.avatar || "🦊"} size={44} seed={student.login} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-bold text-white">{student.first_name} {student.last_name}</p>
                    <p className="text-[10px] text-mist-500">@{student.login} · {student.learner?.grade || klass.grade} класс</p>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-1.5">
                  {[["Ур.", student.stats?.level || 1], ["Точн.", `${student.stats?.accuracy || 0}%`], ["Серия", student.stats?.streak_days || 0]].map(([label, value]) => (
                    <div key={label} className="rounded-lg border border-white/7 bg-white/[0.025] py-1.5 text-center">
                      <p className="text-xs font-bold text-white">{value}</p>
                      <p className="text-[9px] text-mist-600">{label}</p>
                    </div>
                  ))}
                </div>
              </Card>
            </Link>
          ))}
          {students.length === 0 && <Card className="sm:col-span-2 lg:col-span-3"><EmptyState icon="🧑‍🎓" title="В классе нет учеников" text="Администратор добавит их в организационном разделе." /></Card>}
        </div>
      )}

      {tab === "assignments" && (
        <div className="space-y-2.5">
          {assignments.map((item) => (
            <AssignmentRow
              key={item.id}
              item={item}
              onPublish={publish}
              onClose={close}
              onResults={() => navigate(`/app/teacher/assignments?results=${item.id}`)}
              onDelete={() => navigate(`/app/teacher/assignments?new=0`)}
            />
          ))}
          {assignments.length === 0 && <Card><EmptyState icon="📝" title="Работ пока нет" text="Создайте работу для этого класса." action={<Button icon={Plus} onClick={() => navigate(`/app/teacher/assignments?new=1&class=${klass.id}`)}>Создать</Button>} /></Card>}
        </div>
      )}

      {tab === "schedule" && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {WEEKDAYS.map((label, index) => {
            const day = index + 1;
            const lessons = (weekByDay[day] || []).sort((a, b) => (a.lesson_no || 0) - (b.lesson_no || 0));
            return (
              <Card key={label} className={`p-4 ${day === TODAY ? "border-iris-400/25 bg-iris-500/[0.035]" : ""}`}>
                <div className="flex items-center justify-between">
                  <p className="text-xs font-bold text-white">{label}</p>
                  {day === TODAY && <Badge tone="iris">сегодня</Badge>}
                </div>
                <div className="mt-3 space-y-2">
                  {lessons.length === 0 && <p className="text-[10px] text-mist-600">Нет уроков</p>}
                  {lessons.map((lesson) => (
                    <div key={lesson.id} className="rounded-xl border border-white/7 bg-white/[0.025] px-2.5 py-2">
                      <p className="text-[10px] font-bold text-iris-300">{lesson.time_start || "—"} · {lesson.lesson_no}</p>
                      <p className="mt-0.5 truncate text-[11px] font-semibold text-white">{lesson.subject_name || lesson.note || "Урок"}</p>
                      {lesson.topic_title && <p className="truncate text-[10px] text-mist-600">{lesson.topic_title}</p>}
                    </div>
                  ))}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ students */
export function TeacherStudents() {
  const { data, loading, error, refresh } = useApi("/teacher/students");
  const [search, setSearch] = useState("");
  const students = data?.students || [];

  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return students;
    return students.filter((student) =>
      `${student.first_name} ${student.last_name} ${student.login} ${student.grade} ${student.letter}`.toLowerCase().includes(query),
    );
  }, [students, search]);

  return (
    <div className="space-y-6">
      <PageHeader title="Ученики" subtitle="Все дети из ваших классов. Откройте карточку, чтобы увидеть прогресс и работы." actions={<Badge tone="iris">{students.length} {plural(students.length, ["ученик", "ученика", "учеников"])}</Badge>} />
      {error && <ErrorState error={error} onRetry={refresh} />}
      <Card className="p-4">
        <div className="relative">
          <Search size={15} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-mist-500" />
          <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Имя, логин или класс…" className="pl-9" />
        </div>
      </Card>

      {loading && !data ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-36" />)}</div>
      ) : visible.length === 0 ? (
        <Card><EmptyState icon="🔍" title={students.length ? "Ничего не нашлось" : "Учеников пока нет"} text={students.length ? "Попробуйте другой запрос." : "Они появятся после зачисления в класс."} /></Card>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {visible.map((student) => (
            <Link key={student.id} to={`/app/teacher/students/${student.id}`}>
              <Card hover className="h-full p-4">
                <div className="flex items-center gap-3">
                  <Avatar emoji={student.learner?.avatar || student.avatar || "🦊"} size={46} seed={student.login} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-bold text-white">{student.first_name} {student.last_name}</p>
                    <p className="truncate text-[10px] text-mist-500">@{student.login}</p>
                  </div>
                  <Badge>{student.grade}{student.letter ? ` «${student.letter}»` : ""}</Badge>
                </div>
                <div className="mt-3 grid grid-cols-3 gap-1.5">
                  {[["Ур.", student.stats?.level || 1], ["Точн.", `${student.stats?.accuracy || 0}%`], ["Звёзды", student.stats?.stars || 0]].map(([label, value]) => (
                    <div key={label} className="rounded-lg border border-white/7 bg-white/[0.025] py-1.5 text-center">
                      <p className="text-xs font-bold text-white">{value}</p>
                      <p className="text-[9px] text-mist-600">{label}</p>
                    </div>
                  ))}
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export function TeacherStudent() {
  const { studentId } = useParams();
  const navigate = useNavigate();
  const { data, loading, error, refresh } = useApi(`/teacher/students/${studentId}`);
  const [tab, setTab] = useState("progress");
  const student = data?.student;
  const stats = data?.stats || {};
  const learner = data?.learner;
  const level = stats.level_info || levelInfo(stats.xp || 0);
  const topics = data?.topics || [];
  const results = data?.results || [];

  if (loading && !data) return <div className="space-y-4"><Skeleton className="h-32 w-full" /><Skeleton className="h-64 w-full" /></div>;
  if (error || !student) {
    return <div className="space-y-4"><Button variant="plain" icon={ArrowLeft} onClick={() => navigate("/app/teacher/students")}>К ученикам</Button><ErrorState error={error} onRetry={refresh} /></div>;
  }

  return (
    <div className="space-y-6">
      <button onClick={() => navigate("/app/teacher/students")} className="inline-flex items-center gap-1.5 text-sm font-semibold text-mist-500 hover:text-white"><ArrowLeft size={15} /> К ученикам</button>

      <Card className="relative overflow-hidden p-5 sm:p-6">
        <div className="pointer-events-none absolute -right-20 -top-24 h-56 w-56 rounded-full bg-iris-500/20 blur-3xl" />
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:gap-5">
          <Avatar emoji={learner?.avatar || student.avatar || "🦊"} size={68} seed={student.login} ring />
          <div className="min-w-0 flex-1">
            <h1 className="break-words font-display text-xl font-semibold text-white sm:text-2xl">{student.first_name} {student.last_name}</h1>
            <p className="mt-1 text-xs text-mist-500">@{student.login} · {data?.classes?.[0]?.title || "класс не назначен"}</p>
            <div className="mt-3 max-w-xs">
              <div className="mb-1 flex items-center justify-between text-[10px] font-bold text-mist-500">
                <span>Уровень {level.level} · {level.title}</span>
                <span>{level.percent}%</span>
              </div>
              <Progress value={level.percent} />
            </div>
          </div>
          <Link to={`/app/teacher/assignments?new=1&student=${student.id}`} className="w-full sm:w-auto"><Button icon={Plus} className="w-full sm:w-auto">Дать задание</Button></Link>
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard icon={Target} label="Точность" value={`${stats.accuracy || 0}%`} hint={`${stats.total_correct || 0} из ${stats.total_attempts || 0}`} tone="cyan" />
        <StatCard icon={Star} label="Звёзды" value={stats.topics_three_stars || 0} tone="gold" />
        <StatCard icon={TrophyIcon} label="Уровень" value={level.level} hint={level.title} tone="iris" />
        <StatCard icon={ClipboardList} label="Работ сдано" value={results.length} tone="green" />
      </div>

      <Tabs
        tabs={[
          { key: "progress", label: "Прогресс", count: topics.length },
          { key: "results", label: "Работы", count: results.length },
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === "progress" && (
        <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
          <Card className="p-5 sm:p-6">
            <SectionTitle eyebrow="Активность" title="Две недели" />
            <div className="mt-5"><WeekBars data={data?.weekly || []} /></div>
          </Card>
          <Card className="p-5 sm:p-6">
            <SectionTitle eyebrow="Темы" title="Освоение" />
            <div className="mt-4 space-y-2">
              {topics.length === 0 && <EmptyState icon="📚" title="Пока без тем" text="Ученик ещё не начинал тренировки." />}
              {topics.slice(0, 10).map((topic) => (
                <div key={topic.slug} className="flex items-center gap-3 rounded-xl border border-white/7 bg-white/[0.02] px-3 py-2.5">
                  <span className="text-xs font-bold text-amber-300">{"★".repeat(topic.stars || 0) || "—"}</span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[11px] font-bold text-white">{topic.slug}</p>
                    <p className="text-[10px] text-mist-600">{topic.correct}/{topic.attempts} верно</p>
                  </div>
                  <span className="text-[10px] font-bold text-mist-500">{topic.attempts ? Math.round((topic.correct / topic.attempts) * 100) : 0}%</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {tab === "results" && (
        <div className="space-y-2.5">
          {results.length === 0 && <Card><EmptyState icon="📝" title="Работ пока нет" text="Когда ученик сдаст работу, она появится здесь." /></Card>}
          {results.map((result, index) => {
            const percent = result.max_score ? Math.round((result.score / result.max_score) * 100) : 0;
            return (
              <Card key={`${result.assignment_id}-${index}`} className="p-4">
                <div className="flex items-center gap-3">
                  <Ring value={percent} size={50} stroke={5} />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-bold text-white">{result.title}</p>
                    <p className="text-[10px] text-mist-600">{result.completed_at ? formatDateTime(result.completed_at) : ""}</p>
                  </div>
                  <Badge tone={scoreTone(percent)}>{result.score} / {result.max_score}</Badge>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

const TrophyIcon = Star;

/* ------------------------------------------------------------------ assignments */
const EMPTY_FORM = {
  title: "",
  class_id: "",
  subject_id: "",
  task_type: "test",
  topic_slugs: [],
  description: "",
  due_date: "",
  time_limit: 0,
  questions_count: 10,
  status: "опубликована",
  kind: "проверочная",
  allow_photo: true,
  allow_text: true,
};

export function TeacherAssignments() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { data, loading, error, refresh } = useApi("/teacher/assignments");
  const { data: classesData } = useApi("/teacher/classes");
  const { data: meta } = useApi("/meta", { ttl: 120_000 });
  const [status, setStatus] = useState("all");
  const [search, setSearch] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [resultsFor, setResultsFor] = useState(null);
  const [results, setResults] = useState(null);
  const [resultsLoading, setResultsLoading] = useState(false);
  const { pending, run } = useAction();

  const classes = classesData?.classes || [];
  const subjects = meta?.subjects || [];
  const assignments = data?.assignments || [];

  const initialClass = searchParams.get("class");
  const initialStudent = searchParams.get("student");

  useEffect(() => {
    if (searchParams.get("new") === "1") {
      const klass = classes.find((item) => Number(item.id) === Number(initialClass));
      setForm({
        ...EMPTY_FORM,
        class_id: klass ? String(klass.id) : "",
        subject_id: subjects[0] ? String(subjects[0].id) : "",
      });
      setFormOpen(true);
      const next = new URLSearchParams(searchParams);
      next.delete("new");
      next.delete("class");
      next.delete("student");
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, classes, subjects, initialClass, initialStudent, setSearchParams]);

  useEffect(() => {
    const requested = searchParams.get("results");
    if (requested) {
      const item = assignments.find((entry) => Number(entry.id) === Number(requested));
      if (item) openResults(item);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, assignments]);

  const activeClass = classes.find((item) => Number(item.id) === Number(form.class_id));
  const grade = activeClass?.grade || 3;
  const { data: topicData } = useApi(
    `/topics?grade=${grade}&subject_id=${form.subject_id || 1}`,
    { enabled: formOpen && Boolean(form.subject_id), ttl: 60_000 },
  );
  const topics = topicData?.topics || [];

  const visible = useMemo(() => {
    let list = assignments;
    if (status !== "all") list = list.filter((item) => item.status === status);
    const query = search.trim().toLowerCase();
    if (query) {
      list = list.filter((item) => `${item.title} ${item.subject_name} ${item.grade} ${item.letter}`.toLowerCase().includes(query));
    }
    return list;
  }, [assignments, status, search]);

  const openForm = (klassId = "") => {
    const klass = classes.find((item) => Number(item.id) === Number(klassId));
    setForm({
      ...EMPTY_FORM,
      class_id: klass ? String(klass.id) : "",
      subject_id: subjects[0] ? String(subjects[0].id) : "",
    });
    setFormOpen(true);
  };

  const openResults = async (item) => {
    setResultsFor(item);
    setResults(null);
    setResultsLoading(true);
    try {
      const payload = await api.get(`/teacher/assignments/${item.id}/results`);
      setResults(payload);
    } catch (err) {
      toast(err.message || "Не удалось загрузить итоги", "error");
      setResultsFor(null);
    } finally {
      setResultsLoading(false);
    }
  };

  const submit = async () => {
    if (!form.title.trim()) {
      toast("Введите название работы", "info");
      return;
    }
    if (!form.class_id) {
      toast("Выберите класс", "info");
      return;
    }
    if (["test", "read"].includes(form.task_type) && form.topic_slugs.length === 0) {
      toast("Выберите хотя бы одну тему", "info");
      return;
    }
    if (form.task_type === "other" && !form.description.trim()) {
      toast("Опишите задание", "info");
      return;
    }
    try {
      await run(() => api.post("/teacher/assignments", {
        ...form,
        class_id: Number(form.class_id),
        subject_id: Number(form.subject_id) || null,
        time_limit: Number(form.time_limit) || 0,
        questions_count: Number(form.questions_count) || 10,
        topic_slugs: form.task_type === "read" ? form.topic_slugs.slice(0, 1) : form.topic_slugs,
      }));
      invalidate("/teacher");
      await refresh();
      setFormOpen(false);
      setForm(EMPTY_FORM);
      toast("Работа создана", "success");
    } catch (err) {
      toast(err.message || "Не удалось создать работу", "error");
    }
  };

  const publish = async (item) => {
    try {
      await run(() => api.post(`/teacher/assignments/${item.id}/publish`, {}));
      invalidate("/teacher");
      await refresh();
      toast("Работа опубликована", "success");
    } catch (err) {
      toast(err.message || "Не удалось опубликовать", "error");
    }
  };

  const close = async (item) => {
    try {
      await run(() => api.post(`/teacher/assignments/${item.id}/close`, {}));
      invalidate("/teacher");
      await refresh();
      toast("Работа закрыта", "success");
    } catch (err) {
      toast(err.message || "Не удалось закрыть", "error");
    }
  };

  const remove = async (item) => {
    if (!window.confirm(`Удалить работу «${item.title}»? Действие нельзя отменить.`)) return;
    try {
      await run(() => api.del(`/teacher/assignments/${item.id}`));
      invalidate("/teacher");
      await refresh();
      toast("Работа удалена", "success");
    } catch (err) {
      toast(err.message || "Не удалось удалить", "error");
    }
  };

  const toggleTopic = (slug) => {
    setForm((current) => {
      const exists = current.topic_slugs.includes(slug);
      return {
        ...current,
        topic_slugs: exists ? current.topic_slugs.filter((item) => item !== slug) : [...current.topic_slugs, slug],
      };
    });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Задания"
        subtitle="Работы для классов и отдельных учеников. Темы и вопросы подбираются автоматически."
        actions={<Button icon={Plus} onClick={() => openForm()}>Создать работу</Button>}
      />

      {error && <ErrorState error={error} onRetry={refresh} />}

      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard icon={ClipboardList} label="Всего работ" value={assignments.length} tone="iris" />
        <StatCard icon={Send} label="Опубликовано" value={assignments.filter((item) => item.status === "опубликована").length} tone="green" />
        <StatCard icon={FileText} label="Черновиков" value={assignments.filter((item) => item.status === "черновик").length} tone="gold" />
      </div>

      <Card className="space-y-3 p-4">
        <div className="relative">
          <Search size={15} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-mist-500" />
          <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Найти работу…" className="pl-9" />
        </div>
        <Tabs
          tabs={[
            { key: "all", label: "Все", count: assignments.length },
            { key: "опубликована", label: "Активные" },
            { key: "черновик", label: "Черновики" },
            { key: "закрыта", label: "Закрытые" },
          ]}
          value={status}
          onChange={setStatus}
        />
      </Card>

      {loading && !data ? (
        <div className="space-y-2.5">{Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-32" />)}</div>
      ) : visible.length === 0 ? (
        <Card><EmptyState icon="📝" title={assignments.length ? "Ничего не нашлось" : "Работ пока нет"} text={assignments.length ? "Измените фильтр или запрос." : "Создайте первую работу — это займёт минуту."} action={<Button icon={Plus} onClick={() => openForm()}>Создать работу</Button>} /></Card>
      ) : (
        <div className="space-y-2.5">
          {visible.map((item) => (
            <AssignmentRow key={item.id} item={item} onResults={openResults} onPublish={publish} onClose={close} onDelete={remove} />
          ))}
        </div>
      )}

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title="Новая работа"
        description="Выберите класс и темы — задания соберутся автоматически."
        size="lg"
        footer={<><Button variant="ghost" onClick={() => setFormOpen(false)}>Отмена</Button><Button icon={Check} loading={pending} onClick={submit}>Создать</Button></>}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Название" className="sm:col-span-2">
            <Input value={form.title} onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))} placeholder="Проверочная работа: …" />
          </Field>
          <Field label="Класс">
            <Select value={form.class_id} onChange={(event) => setForm((current) => ({ ...current, class_id: event.target.value, topic_slugs: [] }))}>
              <option value="">Выберите класс</option>
              {classes.map((klass) => <option key={klass.id} value={klass.id}>{klass.title || `${klass.grade} «${klass.letter}»`}</option>)}
            </Select>
          </Field>
          <Field label="Предмет">
            <Select value={form.subject_id} onChange={(event) => setForm((current) => ({ ...current, subject_id: event.target.value, topic_slugs: [] }))}>
              <option value="">Любой</option>
              {subjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.icon} {subject.name}</option>)}
            </Select>
          </Field>
          <Field label="Тип работы">
            <Select value={form.task_type} onChange={(event) => setForm((current) => ({ ...current, task_type: event.target.value, topic_slugs: [] }))}>
              <option value="test">Тест</option>
              <option value="read">Чтение</option>
              <option value="dictation">Диктант</option>
              <option value="other">Другое</option>
            </Select>
          </Field>
          <Field label="Тип оценивания">
            <Select value={form.kind} onChange={(event) => setForm((current) => ({ ...current, kind: event.target.value }))}>
              <option value="проверочная">Проверочная</option>
              <option value="контрольная">Контрольная</option>
              <option value="домашняя">Домашняя</option>
              <option value="самостоятельная">Самостоятельная</option>
            </Select>
          </Field>

          {["test", "read"].includes(form.task_type) && (
            <Field label={`Темы (${form.topic_slugs.length})`} hint={form.task_type === "read" ? "Для чтения выбирается одна тема." : "Можно выбрать несколько."} className="sm:col-span-2">
              <div className="max-h-48 space-y-1.5 overflow-y-auto rounded-xl border border-white/8 bg-white/[0.02] p-2">
                {topics.length === 0 && <p className="px-2 py-3 text-center text-[11px] text-mist-500">{form.class_id ? "Для класса нет тем — выберите другую тему или предмет." : "Сначала выберите класс."}</p>}
                {topics.map((topic) => {
                  const checked = form.topic_slugs.includes(topic.slug);
                  return (
                    <button
                      key={topic.slug}
                      type="button"
                      onClick={() => toggleTopic(topic.slug)}
                      className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition ${checked ? "bg-iris-500/15 text-white" : "text-mist-400 hover:bg-white/5"}`}
                    >
                      <span className={`flex h-4 w-4 items-center justify-center rounded border ${checked ? "border-iris-400 bg-iris-500" : "border-white/20"}`}>
                        {checked && <Check size={11} />}
                      </span>
                      <span className="text-[11px] font-semibold">{topic.icon} {topic.title}</span>
                      <span className="ml-auto text-[10px] text-mist-600">{topic.grade} кл.</span>
                    </button>
                  );
                })}
              </div>
            </Field>
          )}

          <Field label="Описание" hint="Необязательно, но дети увидят его перед началом." className="sm:col-span-2">
            <Textarea value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} placeholder="Что важно помнить при выполнении…" />
          </Field>
          <Field label="Срок сдачи">
            <Input type="date" value={form.due_date} onChange={(event) => setForm((current) => ({ ...current, due_date: event.target.value }))} />
          </Field>
          <Field label="Время, минут" hint="0 — без ограничения.">
            <Input type="number" min={0} value={form.time_limit} onChange={(event) => setForm((current) => ({ ...current, time_limit: event.target.value }))} />
          </Field>
          <Field label="Количество вопросов">
            <Input type="number" min={1} max={50} value={form.questions_count} onChange={(event) => setForm((current) => ({ ...current, questions_count: event.target.value }))} />
          </Field>
          <Field label="Статус">
            <Select value={form.status} onChange={(event) => setForm((current) => ({ ...current, status: event.target.value }))}>
              <option value="опубликована">Опубликовать сразу</option>
              <option value="черновик">Сохранить черновик</option>
            </Select>
          </Field>

          <div className="flex flex-wrap gap-2 sm:col-span-2">
            <button type="button" onClick={() => setForm((current) => ({ ...current, allow_photo: !current.allow_photo }))} className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold ${form.allow_photo ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-200" : "border-white/8 text-mist-500"}`}>
              <Check size={13} /> Ответ фото
            </button>
            <button type="button" onClick={() => setForm((current) => ({ ...current, allow_text: !current.allow_text }))} className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-xs font-semibold ${form.allow_text ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-200" : "border-white/8 text-mist-500"}`}>
              <Check size={13} /> Ответ текстом
            </button>
          </div>
        </div>
      </Modal>

      <Modal
        open={Boolean(resultsFor)}
        onClose={() => { setResultsFor(null); setResults(null); }}
        title={resultsFor?.title || "Итоги работы"}
        description={resultsFor ? `${resultsFor.grade || ""} «${resultsFor.letter || ""}» · ${resultsFor.subject_name || ""}` : ""}
        size="lg"
        footer={<Button onClick={() => { setResultsFor(null); setResults(null); }}>Закрыть</Button>}
      >
        {resultsLoading ? (
          <div className="space-y-2">{Array.from({ length: 3 }).map((_, index) => <Skeleton key={index} className="h-16" />)}</div>
        ) : (results?.results || []).length === 0 ? (
          <EmptyState icon="⏳" title="Пока никто не сдал" text="Результаты появятся здесь сразу после сдачи работы." />
        ) : (
          <div className="space-y-2">
            {(results?.results || []).map((item) => {
              const student = item.student || {};
              return (
                <div key={student.id} className="flex items-center gap-3 rounded-xl border border-white/7 bg-white/[0.02] px-3.5 py-3">
                  <Avatar emoji={student.avatar || "🦊"} size={36} seed={student.login} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-bold text-white">{student.first_name} {student.last_name}</p>
                    <p className="text-[10px] text-mist-600">{item.result?.completed_at ? formatDateTime(item.result.completed_at) : "без даты"}</p>
                    {item.ai_feedback && <p className="mt-1 text-[10px] leading-relaxed text-amber-200/80">{item.ai_feedback}</p>}
                  </div>
                  <Badge tone={scoreTone(item.percent)}>{item.result?.score ?? 0} / {item.result?.max_score ?? 0} · {item.percent ?? 0}%</Badge>
                </div>
              );
            })}
          </div>
        )}
      </Modal>
    </div>
  );
}

/* ------------------------------------------------------------------ schedule */
export function TeacherSchedule() {
  const [searchParams] = useSearchParams();
  const { data: classesData } = useApi("/teacher/classes");
  const { data: meta } = useApi("/meta", { ttl: 120_000 });
  const [classId, setClassId] = useState(searchParams.get("class") || "");
  const classes = classesData?.classes || [];
  const activeId = classId || classes[0]?.id || "";
  const activeClass = classes.find((item) => Number(item.id) === Number(activeId));
  const { data, loading, error, refresh } = useApi(`/teacher/schedule?class_id=${activeId}`, { enabled: Boolean(activeId) });
  const { data: topicData } = useApi(`/topics?grade=${activeClass?.grade || 3}&subject_id=${meta?.subjects?.[0]?.id || 1}`, { enabled: Boolean(activeClass) });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ weekday: TODAY, lesson_no: 1, subject_id: "", time_start: "09:00", time_end: "09:45", topic_slug: "", note: "" });
  const { pending, run } = useAction();

  const subjects = meta?.subjects || [];
  const topics = topicData?.topics || [];
  const lessons = data?.schedule || [];

  useEffect(() => {
    if (subjects.length && !form.subject_id) {
      setForm((current) => ({ ...current, subject_id: String(subjects[0].id) }));
    }
  }, [subjects, form.subject_id]);

  const byDay = useMemo(() => {
    const map = {};
    lessons.forEach((lesson) => {
      map[lesson.weekday] = map[lesson.weekday] || [];
      map[lesson.weekday].push(lesson);
    });
    Object.values(map).forEach((items) => items.sort((a, b) => (a.lesson_no || 0) - (b.lesson_no || 0)));
    return map;
  }, [lessons]);

  const save = async () => {
    try {
      await run(() => api.post("/teacher/schedule", {
        class_id: Number(activeId),
        weekday: Number(form.weekday),
        lesson_no: Number(form.lesson_no),
        subject_id: Number(form.subject_id) || null,
        time_start: form.time_start,
        time_end: form.time_end,
        topic_slug: form.topic_slug,
        note: form.note,
      }));
      invalidate("/teacher");
      await refresh();
      setOpen(false);
      toast("Урок сохранён", "success");
    } catch (err) {
      toast(err.message || "Не удалось сохранить урок", "error");
    }
  };

  const remove = async (item) => {
    if (!window.confirm("Удалить урок из расписания?")) return;
    try {
      await run(() => api.del(`/teacher/schedule/${item.id}`));
      invalidate("/teacher");
      await refresh();
      toast("Урок удалён", "success");
    } catch (err) {
      toast(err.message || "Не удалось удалить урок", "error");
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Расписание"
        subtitle="Уроки класса на неделю. Можно менять тему и время — дети увидят изменения сразу."
        actions={<Button icon={Plus} disabled={!activeId} onClick={() => setOpen(true)}>Добавить урок</Button>}
      />

      {classes.length > 0 && (
        <div className="no-scrollbar flex gap-1 overflow-x-auto rounded-2xl border border-white/8 bg-white/[0.025] p-1">
          {classes.map((klass) => (
            <button key={klass.id} onClick={() => setClassId(String(klass.id))} className={`shrink-0 rounded-xl px-3.5 py-2 text-sm font-semibold transition ${Number(klass.id) === Number(activeId) ? "bg-white/10 text-white" : "text-mist-500 hover:text-white"}`}>
              {klass.title || `${klass.grade} «${klass.letter}»`}
            </button>
          ))}
        </div>
      )}

      {error && <ErrorState error={error} onRetry={refresh} />}
      {!activeId && <Card><EmptyState icon="🏫" title="Нет классов" text="Расписание появится после назначения класса." /></Card>}
      {loading && !data ? <Skeleton className="h-72 w-full" /> : activeId && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {WEEKDAYS.map((label, index) => {
            const day = index + 1;
            const dayLessons = byDay[day] || [];
            return (
              <Card key={label} className={`p-4 ${day === TODAY ? "border-iris-400/25 bg-iris-500/[0.035]" : ""}`}>
                <div className="flex items-center justify-between">
                  <p className="text-xs font-bold text-white">{label}</p>
                  <div className="flex items-center gap-1.5">
                    {day === TODAY && <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" />}
                    <span className="text-[10px] text-mist-600">{dayLessons.length}</span>
                  </div>
                </div>
                <div className="mt-3 space-y-2">
                  {dayLessons.length === 0 && <p className="rounded-lg border border-dashed border-white/8 py-4 text-center text-[10px] text-mist-600">Свободно</p>}
                  {dayLessons.map((lesson) => (
                    <div key={lesson.id} className="group rounded-xl border border-white/7 bg-white/[0.025] px-2.5 py-2">
                      <div className="flex items-center justify-between gap-1">
                        <p className="text-[10px] font-bold text-iris-300">{lesson.time_start || "—"}–{lesson.time_end || ""}</p>
                        <button onClick={() => remove(lesson)} className="text-mist-600 opacity-0 transition hover:text-rose-300 group-hover:opacity-100" aria-label="Удалить урок">
                          <X size={12} />
                        </button>
                      </div>
                      <p className="mt-0.5 truncate text-[11px] font-semibold text-white">{lesson.subject_name || "Урок"}</p>
                      {lesson.topic_title && <p className="truncate text-[10px] text-mist-500">{lesson.topic_title}</p>}
                      {lesson.note && !lesson.topic_title && <p className="truncate text-[10px] text-mist-500">{lesson.note}</p>}
                    </div>
                  ))}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Новый урок"
        description={`${activeClass?.title || "Класс"} · ${WEEKDAYS[(Number(form.weekday) || 1) - 1]}`}
        footer={<><Button variant="ghost" onClick={() => setOpen(false)}>Отмена</Button><Button icon={Check} loading={pending} onClick={save}>Сохранить</Button></>}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="День недели">
            <Select value={form.weekday} onChange={(event) => setForm((current) => ({ ...current, weekday: Number(event.target.value) }))}>
              {WEEKDAYS.map((label, index) => <option key={label} value={index + 1}>{label}</option>)}
            </Select>
          </Field>
          <Field label="Номер урока">
            <Input type="number" min={1} max={12} value={form.lesson_no} onChange={(event) => setForm((current) => ({ ...current, lesson_no: event.target.value }))} />
          </Field>
          <Field label="Начало"><Input type="time" value={form.time_start} onChange={(event) => setForm((current) => ({ ...current, time_start: event.target.value }))} /></Field>
          <Field label="Конец"><Input type="time" value={form.time_end} onChange={(event) => setForm((current) => ({ ...current, time_end: event.target.value }))} /></Field>
          <Field label="Предмет" className="sm:col-span-2">
            <Select value={form.subject_id} onChange={(event) => setForm((current) => ({ ...current, subject_id: event.target.value, topic_slug: "" }))}>
              {subjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.icon} {subject.name}</option>)}
            </Select>
          </Field>
          <Field label="Тема урока" className="sm:col-span-2">
            <Select value={form.topic_slug} onChange={(event) => setForm((current) => ({ ...current, topic_slug: event.target.value }))}>
              <option value="">Без темы</option>
              {topics.map((topic) => <option key={topic.slug} value={topic.slug}>{topic.title}</option>)}
            </Select>
          </Field>
          <Field label="Заметка" className="sm:col-span-2">
            <Input value={form.note} onChange={(event) => setForm((current) => ({ ...current, note: event.target.value }))} placeholder="Что взять на урок…" />
          </Field>
        </div>
      </Modal>
    </div>
  );
}

/* ------------------------------------------------------------------ library */
export function TeacherLibrary() {
  const { data, loading, error, refresh } = useApi("/teacher/library");
  const { data: textbooksData } = useApi("/teacher/textbooks");
  const { data: meta } = useApi("/meta", { ttl: 120_000 });
  const [tab, setTab] = useState("books");
  const [search, setSearch] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [recommendFor, setRecommendFor] = useState(null);
  const [upload, setUpload] = useState({ file: null, subject_id: "", grade: 3, title: "", author: "", description: "", class_ids: [] });
  const [addForm, setAddForm] = useState({ textbook_id: "", title: "", class_ids: [] });
  const [recommend, setRecommend] = useState({ class_ids: [], student_ids: [], note: "" });
  const [openClass, setOpenClass] = useState(null);
  const { pending, run } = useAction();

  const books = data?.books || [];
  const classes = data?.classes || [];
  const students = data?.students || [];
  const stats = data?.stats || {};
  const subjects = meta?.subjects || [];
  const textbooks = textbooksData?.textbooks || [];

  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return books;
    return books.filter((book) => `${book.title} ${book.author} ${book.subject_name}`.toLowerCase().includes(query));
  }, [books, search]);

  const uploadBook = async () => {
    if (!upload.file) {
      toast("Выберите PDF-файл", "info");
      return;
    }
    const formData = new FormData();
    formData.append("file", upload.file);
    formData.append("subject_id", upload.subject_id);
    formData.append("grade", upload.grade);
    formData.append("title", upload.title);
    formData.append("author", upload.author);
    formData.append("description", upload.description);
    upload.class_ids.forEach((id) => formData.append("class_ids", id));
    try {
      const payload = await run(() => api.form("/teacher/textbooks", formData));
      invalidate("/teacher");
      await refresh();
      setUploadOpen(false);
      setUpload({ file: null, subject_id: "", grade: 3, title: "", author: "", description: "", class_ids: [] });
      toast(`Книга загружена: ${payload.pages || 0} стр., ${payload.topics_linked || 0} тем`, "success");
    } catch (err) {
      toast(err.message || "Не удалось загрузить книгу", "error");
    }
  };

  const addBook = async () => {
    if (!addForm.textbook_id) {
      toast("Выберите пособие", "info");
      return;
    }
    try {
      await run(() => api.post("/teacher/library", {
        textbook_id: Number(addForm.textbook_id),
        title: addForm.title,
        class_ids: addForm.class_ids,
      }));
      invalidate("/teacher");
      await refresh();
      setAddOpen(false);
      setAddForm({ textbook_id: "", title: "", class_ids: [] });
      toast("Книга добавлена в библиотеку", "success");
    } catch (err) {
      toast(err.message || "Не удалось добавить книгу", "error");
    }
  };

  const removeBook = async (book) => {
    if (!window.confirm(`Удалить «${book.title}» из библиотеки?`)) return;
    try {
      await run(() => api.del(`/teacher/library/${book.id}`));
      invalidate("/teacher");
      await refresh();
      toast("Книга удалена", "success");
    } catch (err) {
      toast(err.message || "Не удалось удалить книгу", "error");
    }
  };

  const sendRecommendation = async () => {
    if (!recommendFor) return;
    if (!recommend.class_ids.length && !recommend.student_ids.length) {
      toast("Выберите класс или ученика", "info");
      return;
    }
    try {
      await run(() => api.post("/teacher/recommend", {
        textbook_id: recommendFor.textbook_id,
        class_ids: recommend.class_ids,
        student_ids: recommend.student_ids,
        note: recommend.note,
      }));
      invalidate("/teacher");
      await refresh();
      setRecommendFor(null);
      setRecommend({ class_ids: [], student_ids: [], note: "" });
      toast("Рекомендация отправлена", "success");
    } catch (err) {
      toast(err.message || "Не удалось отправить рекомендацию", "error");
    }
  };

  const toggle = (key, id, setter) => {
    setter((current) => ({
      ...current,
      [key]: current[key].includes(id) ? current[key].filter((item) => item !== id) : [...current[key], id],
    }));
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Библиотека учителя"
        subtitle="Пособия для классов, загрузка PDF и рекомендации ученикам."
        actions={
          <>
            <Button variant="ghost" icon={BookOpen} onClick={() => setAddOpen(true)}>Из пособия</Button>
            <Button icon={Upload} onClick={() => setUploadOpen(true)}>Загрузить PDF</Button>
          </>
        }
      />

      {error && <ErrorState error={error} onRetry={refresh} />}

      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard icon={BookOpen} label="Книг" value={stats.books || books.length} tone="iris" />
        <StatCard icon={Users} label="Классов" value={classes.length} tone="cyan" />
        <StatCard icon={Sparkles} label="Рекомендаций" value={stats.recommendations || 0} tone="gold" />
      </div>

      <Card className="p-5">
        <SectionTitle
          eyebrow="Учебники"
          title="Мои классы"
          subtitle="Нажмите на класс, чтобы увидеть своих учеников этого класса."
          action={<Badge tone="cyan"><Users size={12} /> {classes.length}</Badge>}
        />
        {classes.length === 0 ? (
          <p className="mt-4 rounded-xl border border-white/8 bg-white/[0.02] p-4 text-xs text-mist-500">
            Классы пока не выбраны. Укажите город, школу и классы в профиле — после этого здесь появятся ваши ученики.
          </p>
        ) : (
          <>
            <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {classes.map((klass) => {
                const open = Number(openClass) === Number(klass.id);
                const count = students.filter((student) => Number(student.class_id) === Number(klass.id)).length;
                return (
                  <button
                    key={klass.id}
                    type="button"
                    onClick={() => setOpenClass(open ? null : klass.id)}
                    className={`rounded-2xl border p-3.5 text-left transition ${
                      open
                        ? "border-iris-400/40 bg-iris-500/[0.08]"
                        : "border-white/8 bg-white/[0.02] hover:border-white/20"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-display text-sm font-semibold text-white">
                        {klass.title || `${klass.grade} «${klass.letter}»`}
                      </span>
                      <Badge tone={open ? "iris" : ""}><Users size={11} /> {count}</Badge>
                    </div>
                    <p className="mt-1.5 flex items-center gap-1.5 text-[11px] text-mist-500">
                      <MapPin size={11} /> {klass.school_name || "Школа не указана"}
                    </p>
                  </button>
                );
              })}
            </div>

            {openClass && (
              <div className="mt-3 rounded-2xl border border-iris-400/25 bg-iris-500/[0.05] p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <GraduationCap size={15} className="text-iris-300" />
                    <span className="text-xs font-bold text-white">
                      Ученики класса {classes.find((item) => Number(item.id) === Number(openClass))?.title || ""}
                    </span>
                  </div>
                  <Button size="sm" variant="ghost" icon={X} onClick={() => setOpenClass(null)}>Свернуть</Button>
                </div>
                {students.filter((student) => Number(student.class_id) === Number(openClass)).length === 0 ? (
                  <p className="mt-3 text-[11px] text-mist-500">В этом классе пока нет учеников.</p>
                ) : (
                  <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {students
                      .filter((student) => Number(student.class_id) === Number(openClass))
                      .map((student) => (
                        <Link
                          key={student.id}
                          to={`/app/teacher/students/${student.id}`}
                          className="flex items-center gap-2.5 rounded-xl border border-white/8 bg-ink-950/30 p-2.5 transition hover:border-iris-400/30"
                        >
                          <Avatar emoji={student.avatar || "🎒"} size={30} seed={student.login} />
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-xs font-semibold text-white">
                              {student.first_name} {student.last_name}
                            </p>
                            <p className="truncate text-[10px] text-mist-500">@{student.login}</p>
                          </div>
                          <ArrowRight size={13} className="text-mist-600" />
                        </Link>
                      ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </Card>

      <Card className="p-4">
        <div className="relative">
          <Search size={15} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-mist-500" />
          <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Найти книгу…" className="pl-9" />
        </div>
      </Card>

      {loading && !data ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-48" />)}</div>
      ) : visible.length === 0 ? (
        <Card><EmptyState icon="📚" title={books.length ? "Ничего не нашлось" : "Библиотека пуста"} text={books.length ? "Попробуйте другой запрос." : "Добавьте пособие из общего каталога или загрузите свой PDF."} action={<Button icon={Upload} onClick={() => setUploadOpen(true)}>Загрузить PDF</Button>} /></Card>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {visible.map((book) => (
            <Card key={book.id} className="flex flex-col p-5">
              <div className="flex items-start justify-between gap-3">
                <span className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-2xl">{book.subject_icon || "📘"}</span>
                <div className="flex flex-col items-end gap-1">
                  {book.grade ? <Badge>{book.grade} класс</Badge> : null}
                  {book.pages ? <span className="text-[10px] text-mist-600">{book.pages} стр.</span> : null}
                </div>
              </div>
              <h3 className="mt-4 font-display text-sm font-semibold leading-snug text-white">{book.title}</h3>
              <p className="mt-1 text-[11px] text-mist-500">{book.author || "Автор не указан"}</p>
              <p className="mt-2 line-clamp-2 flex-1 text-[11px] leading-relaxed text-mist-600">{book.description}</p>
              <div className="mt-3 text-[10px] text-mist-600">{book.class_ids?.length ? `классов: ${book.class_ids.length}` : "без классов"}</div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                <Link to={`/app/library/${book.id}`}><Button size="sm" variant="ghost" icon={BookOpen}>Открыть</Button></Link>
                {book.textbook_id && (
                  <Button size="sm" variant="ghost" icon={Sparkles} onClick={() => { setRecommendFor(book); setRecommend({ class_ids: book.class_ids || [], student_ids: [], note: "" }); }}>Рекомендовать</Button>
                )}
                <Button size="sm" variant="plain" icon={Trash2} onClick={() => removeBook(book)} />
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        title="Загрузить PDF-пособие"
        description="Файл сохранится на сервере, страницы будут доступны для чтения."
        footer={<><Button variant="ghost" onClick={() => setUploadOpen(false)}>Отмена</Button><Button icon={Upload} loading={pending} onClick={uploadBook}>Загрузить</Button></>}
      >
        <div className="space-y-4">
          <Field label="PDF-файл">
            <input
              type="file"
              accept="application/pdf,.pdf"
              onChange={(event) => setUpload((current) => ({ ...current, file: event.target.files?.[0] || null }))}
              className="field file:mr-3 file:rounded-lg file:border-0 file:bg-iris-500/20 file:px-3 file:py-1.5 file:text-xs file:font-bold file:text-iris-200"
            />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Предмет">
              <Select value={upload.subject_id} onChange={(event) => setUpload((current) => ({ ...current, subject_id: event.target.value }))}>
                <option value="">Выберите</option>
                {subjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.icon} {subject.name}</option>)}
              </Select>
            </Field>
            <Field label="Класс">
              <Select value={upload.grade} onChange={(event) => setUpload((current) => ({ ...current, grade: Number(event.target.value) }))}>
                {Array.from({ length: 11 }).map((_, index) => <option key={index + 1} value={index + 1}>{index + 1} класс</option>)}
              </Select>
            </Field>
          </div>
          <Field label="Название" hint="Если пусто — возьмём имя файла.">
            <Input value={upload.title} onChange={(event) => setUpload((current) => ({ ...current, title: event.target.value }))} />
          </Field>
          <Field label="Автор"><Input value={upload.author} onChange={(event) => setUpload((current) => ({ ...current, author: event.target.value }))} /></Field>
          <Field label="Описание"><Textarea value={upload.description} onChange={(event) => setUpload((current) => ({ ...current, description: event.target.value }))} /></Field>
          <Field label="Кому доступно">
            <div className="flex flex-wrap gap-1.5">
              {classes.map((klass) => (
                <button key={klass.id} type="button" onClick={() => toggle("class_ids", klass.id, setUpload)} className={`rounded-lg border px-2.5 py-1.5 text-[11px] font-semibold ${upload.class_ids.includes(klass.id) ? "border-iris-400/40 bg-iris-500/15 text-white" : "border-white/8 text-mist-500"}`}>
                  {klass.title || `${klass.grade} «${klass.letter}»`}
                </button>
              ))}
            </div>
          </Field>
        </div>
      </Modal>

      <Modal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="Добавить из каталога"
        description="Выберите готовое пособие и классы, которые увидят его в библиотеке."
        footer={<><Button variant="ghost" onClick={() => setAddOpen(false)}>Отмена</Button><Button icon={Plus} loading={pending} onClick={addBook}>Добавить</Button></>}
      >
        <div className="space-y-4">
          <Field label="Пособие">
            <Select value={addForm.textbook_id} onChange={(event) => {
              const textbook = textbooks.find((item) => Number(item.id) === Number(event.target.value));
              setAddForm((current) => ({ ...current, textbook_id: event.target.value, title: textbook?.title || "" }));
            }}>
              <option value="">Выберите пособие</option>
              {textbooks.map((textbook) => <option key={textbook.id} value={textbook.id}>{textbook.icon || "📘"} {textbook.title} · {textbook.grade} кл.</option>)}
            </Select>
          </Field>
          {textbooks.length === 0 && <p className="text-[11px] text-mist-500">Общий каталог пуст. Загрузите PDF — он появится здесь.</p>}
          <Field label="Название в библиотеке"><Input value={addForm.title} onChange={(event) => setAddForm((current) => ({ ...current, title: event.target.value }))} /></Field>
          <Field label="Классы">
            <div className="flex flex-wrap gap-1.5">
              {classes.map((klass) => (
                <button key={klass.id} type="button" onClick={() => toggle("class_ids", klass.id, setAddForm)} className={`rounded-lg border px-2.5 py-1.5 text-[11px] font-semibold ${addForm.class_ids.includes(klass.id) ? "border-iris-400/40 bg-iris-500/15 text-white" : "border-white/8 text-mist-500"}`}>
                  {klass.title || `${klass.grade} «${klass.letter}»`}
                </button>
              ))}
            </div>
          </Field>
        </div>
      </Modal>

      <Modal
        open={Boolean(recommendFor)}
        onClose={() => setRecommendFor(null)}
        title="Рекомендовать книгу"
        description={recommendFor?.title || ""}
        footer={<><Button variant="ghost" onClick={() => setRecommendFor(null)}>Отмена</Button><Button icon={Send} loading={pending} onClick={sendRecommendation}>Отправить</Button></>}
      >
        <div className="space-y-4">
          <Field label="Классы">
            <div className="flex flex-wrap gap-1.5">
              {classes.map((klass) => (
                <button key={klass.id} type="button" onClick={() => toggle("class_ids", klass.id, setRecommend)} className={`rounded-lg border px-2.5 py-1.5 text-[11px] font-semibold ${recommend.class_ids.includes(klass.id) ? "border-iris-400/40 bg-iris-500/15 text-white" : "border-white/8 text-mist-500"}`}>
                  {klass.title || `${klass.grade} «${klass.letter}»`}
                </button>
              ))}
            </div>
          </Field>
          <Field label="Или отдельные ученики">
            <div className="max-h-40 flex flex-wrap gap-1.5 overflow-y-auto">
              {students.map((student) => (
                <button key={student.id} type="button" onClick={() => toggle("student_ids", student.id, setRecommend)} className={`rounded-lg border px-2.5 py-1.5 text-[11px] font-semibold ${recommend.student_ids.includes(student.id) ? "border-cyan-400/40 bg-cyan-500/15 text-white" : "border-white/8 text-mist-500"}`}>
                  {student.first_name} {student.last_name}
                </button>
              ))}
            </div>
          </Field>
          <Field label="Записка">
            <Textarea value={recommend.note} onChange={(event) => setRecommend((current) => ({ ...current, note: event.target.value }))} placeholder="Что прочитать и зачем…" />
          </Field>
        </div>
      </Modal>
    </div>
  );
}
