import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Clock,
  FileText,
  Info,
  Lightbulb,
  Mic,
  Play,
  Send,
  Sparkles,
  Timer,
  Trophy,
  Volume2,
  X,
} from "lucide-react";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  Progress,
  SectionTitle,
  Skeleton,
  StatCard,
  Tabs,
} from "../components/ui";
import { useAction, useApi, toast } from "../lib/hooks";
import { api, invalidate } from "../lib/api";
import { formatDate, formatDateTime, pct, plural, scoreTone, taskTypeLabel } from "../lib/format";

function speak(text) {
  if (!text || typeof window === "undefined" || !window.speechSynthesis) return;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "ru-RU";
  utterance.rate = 0.92;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

export function AssignmentsPage() {
  const { data, loading, error, refresh } = useApi("/assignments");
  const [tab, setTab] = useState("active");

  const assignments = data?.assignments || [];
  const active = assignments.filter((item) => !item.result);
  const done = assignments.filter((item) => item.result);
  const shown = tab === "active" ? active : tab === "done" ? done : assignments;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Задания"
        subtitle="Работы от учителя: проверочные, чтение, диктанты и проекты. Сроки и результаты — в одном месте."
        actions={<Badge tone="iris">{active.length} активных</Badge>}
      />

      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard icon={ClipboardList} label="Всего работ" value={assignments.length} tone="iris" />
        <StatCard icon={Clock} label="Активные" value={active.length} hint={active[0]?.due_date ? `Ближайший срок — ${formatDate(active[0].due_date)}` : "Без срочных сроков"} tone="gold" />
        <StatCard icon={Trophy} label="Выполнено" value={done.length} hint={done.length ? `Средний результат — ${Math.round(done.reduce((sum, item) => sum + (item.result?.percent || 0), 0) / done.length)}%` : "Пока нет результатов"} tone="green" />
      </div>

      <Tabs
        tabs={[
          { key: "active", label: "Активные", count: active.length },
          { key: "done", label: "Выполненные", count: done.length },
          { key: "all", label: "Все", count: assignments.length },
        ]}
        value={tab}
        onChange={setTab}
      />

      {error && <ErrorState error={error} onRetry={refresh} />}

      {loading && !data && (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, index) => <Skeleton key={index} className="h-28" />)}
        </div>
      )}

      {!loading && shown.length === 0 && (
        <Card>
          <EmptyState
            icon={tab === "done" ? "🎯" : "✅"}
            title={tab === "done" ? "Пока нет выполненных работ" : "Нет активных заданий"}
            text={tab === "done" ? "Сданные работы и результаты появятся здесь." : "Когда учитель опубликует работу, вы получите уведомление."}
          />
        </Card>
      )}

      <div className="space-y-3">
        {shown.map((item) => {
          const result = item.result;
          return (
            <Link
              key={item.id}
              to={`/app/assignments/${item.id}`}
              className="card card-hover block overflow-hidden p-5"
            >
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
                <span className="flex h-13 w-13 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-2xl" style={{ width: 52, height: 52 }}>
                  {item.subject_icon || "📘"}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={item.task_type === "dictation" ? "gold" : item.task_type === "read" ? "cyan" : "iris"}>
                      {taskTypeLabel(item.task_type)}
                    </Badge>
                    {item.overdue && !result && <Badge tone="rose">срок истёк</Badge>}
                    {result && <Badge tone={scoreTone(result.percent)}>{result.grade}</Badge>}
                  </div>
                  <h3 className="mt-2 font-display text-base font-semibold text-white">{item.title}</h3>
                  <p className="mt-1 line-clamp-1 text-xs text-mist-500">
                    {item.subject_name} · {item.author_name} · {item.questions_count} {plural(item.questions_count, ["задание", "задания", "заданий"])}
                    {item.due_date ? ` · до ${formatDate(item.due_date)}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-4 sm:flex-col sm:items-end">
                  {result ? (
                    <div className="text-right">
                      <p className="font-display text-xl font-semibold text-white">{result.score}/{result.max_score}</p>
                      <p className="text-[10px] font-bold uppercase tracking-wider text-mist-600">{result.percent}%</p>
                    </div>
                  ) : (
                    <Badge tone={item.overdue ? "rose" : "green"}>
                      {item.overdue ? "не сдано" : "к сдаче"}
                    </Badge>
                  )}
                  <span className="inline-flex items-center gap-1 text-xs font-bold text-iris-300">
                    {result ? "Результат" : "Открыть"} <ArrowRight size={13} />
                  </span>
                </div>
              </div>
              {result && (
                <div className="mt-4">
                  <Progress value={result.percent} />
                </div>
              )}
            </Link>
          );
        })}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- detail */
function ResultView({ payload }) {
  const result = payload.result;
  const details = payload.details || [];
  return (
    <div className="space-y-5">
      <Card className="relative overflow-hidden p-6 sm:p-8">
        <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-emerald-400/10 blur-3xl" />
        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <Badge tone={scoreTone(result.percent)}>Работа проверена</Badge>
            <h2 className="mt-3 font-display text-2xl font-semibold text-white">{result.grade}</h2>
            <p className="mt-1 text-sm text-mist-400">
              {result.score} из {result.max_score} баллов · {result.percent}%
              {result.completed_at ? ` · ${formatDateTime(result.completed_at)}` : ""}
            </p>
            {result.ai_feedback && (
              <div className="mt-4 rounded-xl border border-iris-400/20 bg-iris-500/[0.06] px-3.5 py-3 text-xs leading-relaxed text-mist-300">
                <p className="mb-1 font-bold text-iris-300">Комментарий ИИ</p>
                {result.ai_feedback}
              </div>
            )}
          </div>
          <div className="flex h-28 w-28 shrink-0 items-center justify-center rounded-full border-4 border-white/8" style={{
            background: `conic-gradient(#8b7bff ${result.percent * 3.6}deg, rgba(255,255,255,.06) 0deg)`,
          }}>
            <div className="flex h-24 w-24 flex-col items-center justify-center rounded-full bg-ink-900">
              <span className="font-display text-2xl font-semibold text-white">{result.percent}%</span>
              <span className="text-[9px] font-bold uppercase tracking-wider text-mist-500">результат</span>
            </div>
          </div>
        </div>
      </Card>

      <Card className="p-5 sm:p-6">
        <SectionTitle eyebrow="Разбор" title="Ответы по заданиям" subtitle="Проверьте, где потеряли баллы." />
        <div className="mt-5 space-y-2.5">
          {details.length === 0 && <EmptyState icon="📄" title="Разбор недоступен" text="Учитель увидит результат, а подробности появятся позже." />}
          {details.map((item, index) => (
            <div key={index} className={`rounded-2xl border px-4 py-3.5 ${item.correct ? "border-emerald-400/20 bg-emerald-500/[0.04]" : "border-rose-400/20 bg-rose-500/[0.04]"}`}>
              <div className="flex items-start gap-3">
                <span className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg ${item.correct ? "bg-emerald-400/15 text-emerald-300" : "bg-rose-400/15 text-rose-300"}`}>
                  {item.correct ? <CheckCircle2 size={14} /> : <X size={14} />}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold leading-relaxed text-white">{item.question || item.title || `Задание ${index + 1}`}</p>
                  <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
                    <span className="text-mist-500">Ваш ответ: <span className={item.correct ? "font-bold text-emerald-300" : "font-bold text-rose-300"}>{item.given || "—"}</span></span>
                    {!item.correct && <span className="text-mist-500">Верно: <span className="font-bold text-emerald-300">{item.expected || item.answer || "—"}</span></span>}
                  </div>
                  {item.solution && <p className="mt-1.5 text-[11px] leading-relaxed text-mist-600">{item.solution}</p>}
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

export function AssignmentPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, loading, error, refresh } = useApi(`/assignments/${id}`, { ttl: 0 });
  const [answers, setAnswers] = useState({});
  const [index, setIndex] = useState(0);
  const [started, setStarted] = useState(false);
  const [startedAt, setStartedAt] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [confirm, setConfirm] = useState(false);
  const { pending, run } = useAction();

  const assignment = data?.assignment;
  const questions = data?.questions || [];
  const submitted = data?.submitted;
  const current = questions[index];

  useEffect(() => {
    if (!started || !startedAt) return undefined;
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - startedAt) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [started, startedAt]);

  const answeredCount = useMemo(
    () => questions.filter((question) => (answers[question.index] ?? "").trim()).length,
    [questions, answers],
  );

  const begin = () => {
    setStarted(true);
    setStartedAt(Date.now());
  };

  const submit = async () => {
    try {
      const payload = await run(() =>
        api.post(`/assignments/${id}/submit`, {
          answers: questions.map((question) => answers[question.index] || ""),
          duration_sec: elapsed,
        }),
      );
      invalidate("/assignments");
      invalidate("/map");
      toast(payload.result ? `Работа сдана: ${payload.result.percent}%` : "Работа отправлена", "success");
      setConfirm(false);
      await refresh();
    } catch (err) {
      toast(err.message || "Не удалось отправить работу", "error");
    }
  };

  if (loading && !data) {
    return <div className="mx-auto max-w-4xl"><Skeleton className="h-96 w-full" /></div>;
  }
  if (error || !data) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <Link to="/app/assignments" className="inline-flex items-center gap-1.5 text-sm font-semibold text-mist-500 hover:text-white"><ArrowLeft size={15} /> К заданиям</Link>
        <ErrorState error={error} onRetry={refresh} />
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="mx-auto max-w-4xl space-y-5">
        <Link to="/app/assignments" className="inline-flex items-center gap-1.5 text-sm font-semibold text-mist-500 hover:text-white"><ArrowLeft size={15} /> К заданиям</Link>
        <div>
          <h1 className="font-display text-2xl font-semibold text-white">{assignment.title}</h1>
          <p className="mt-1 text-sm text-mist-500">{assignment.subject_name} · {assignment.author_name}</p>
        </div>
        <ResultView payload={data} />
      </div>
    );
  }

  if (!started) {
    return (
      <div className="mx-auto max-w-3xl space-y-5">
        <Link to="/app/assignments" className="inline-flex items-center gap-1.5 text-sm font-semibold text-mist-500 hover:text-white"><ArrowLeft size={15} /> К заданиям</Link>
        <Card className="relative overflow-hidden p-6 sm:p-8">
          <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-iris-500/15 blur-3xl" />
          <div className="relative">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="iris">{taskTypeLabel(assignment.task_type)}</Badge>
              <Badge>{assignment.subject_name}</Badge>
              {assignment.due_date && <Badge tone={assignment.overdue ? "rose" : "gold"}><Clock size={11} /> до {formatDate(assignment.due_date)}</Badge>}
            </div>
            <h1 className="mt-4 font-display text-2xl font-semibold text-white sm:text-3xl">{assignment.title}</h1>
            <p className="mt-2 text-sm leading-relaxed text-mist-400">{assignment.description || "Прочитайте условия и приступайте к выполнению."}</p>

            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              {[
                [ClipboardList, "Заданий", questions.length],
                [Timer, "Время", assignment.time_limit ? `${assignment.time_limit} мин` : "не ограничено"],
                [Trophy, "Баллы", questions.reduce((sum, question) => sum + (question.points || 1), 0)],
              ].map(([Icon, label, value]) => (
                <div key={label} className="rounded-2xl border border-white/8 bg-white/[0.025] p-3.5">
                  <Icon size={16} className="text-iris-300" />
                  <p className="mt-2 text-sm font-bold text-white">{value}</p>
                  <p className="text-[10px] font-bold uppercase tracking-wider text-mist-600">{label}</p>
                </div>
              ))}
            </div>

            <div className="mt-6 rounded-2xl border border-amber-400/20 bg-amber-400/[0.05] px-4 py-3 text-xs leading-relaxed text-amber-100/80">
              <span className="font-bold text-amber-300">Важно: </span>
              ответы сохранятся только после отправки. Проверьте их перед сдачей.
              {assignment.allow_photo ? " Можно приложить фото решения." : ""}
            </div>

            <div className="mt-6 flex flex-wrap gap-2">
              {questions.length > 0 ? (
                <Button size="lg" icon={Play} onClick={begin}>Начать выполнение</Button>
              ) : (
                <Badge tone="rose">В работе нет вопросов</Badge>
              )}
              <Link to="/app/assignments"><Button size="lg" variant="ghost">Позже</Button></Link>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button onClick={() => setStarted(false)} className="inline-flex items-center gap-1.5 text-sm font-semibold text-mist-500 hover:text-white">
          <ArrowLeft size={15} /> К описанию
        </button>
        <div className="flex items-center gap-2">
          <Badge tone="iris">Вопрос {index + 1} из {questions.length}</Badge>
          <Badge tone="gold"><Timer size={11} /> {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")}</Badge>
        </div>
      </div>

      <div className="progress h-2"><span style={{ width: `${pct(index, questions.length)}%` }} /></div>

      <div className="grid gap-4 lg:grid-cols-[1fr_240px]">
        <Card className="p-5 sm:p-7">
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-mist-600">
            {current?.task_type === "read" ? "Прочитайте и ответьте" : current?.task_type === "dictation" ? "Диктант" : "Задание"}
          </p>
          <p className="mt-2 whitespace-pre-line font-display text-lg font-medium leading-relaxed text-white">
            {current?.question}
          </p>

          {current?.content_text && (
            <div className="mt-4 rounded-2xl border border-cyan-400/20 bg-cyan-400/[0.04] p-4 text-sm leading-relaxed text-mist-300">
              {current.content_text}
            </div>
          )}

          {current?.audio_text && (
            <Button variant="ghost" size="sm" icon={Volume2} className="mt-4" onClick={() => speak(current.audio_text)}>
              Прослушать текст
            </Button>
          )}

          <div className="mt-5">
            {current?.answer_type === "choice" && current.choices?.length > 0 ? (
              <div className="space-y-2.5">
                {current.choices.map((choice, choiceIndex) => {
                  const active = answers[current.index] === choice;
                  return (
                    <button
                      key={`${choice}-${choiceIndex}`}
                      type="button"
                      onClick={() => setAnswers((values) => ({ ...values, [current.index]: choice }))}
                      className={`w-full rounded-2xl border px-4 py-3 text-left text-sm font-semibold transition ${
                        active ? "border-iris-400/60 bg-iris-500/15 text-white" : "border-white/9 bg-white/[0.025] text-mist-300 hover:border-white/20"
                      }`}
                    >
                      <span className="mr-2.5 inline-flex h-6 w-6 items-center justify-center rounded-lg border border-white/10 text-[11px]">
                        {String.fromCharCode(65 + choiceIndex)}
                      </span>
                      {choice}
                    </button>
                  );
                })}
              </div>
            ) : (
              <textarea
                value={answers[current?.index] || ""}
                onChange={(event) => setAnswers((values) => ({ ...values, [current.index]: event.target.value }))}
                placeholder="Запишите ответ или решение…"
                className="field min-h-[120px] resize-y"
              />
            )}
          </div>

          <div className="mt-6 flex items-center justify-between gap-2">
            <Button variant="ghost" icon={ChevronLeft} disabled={index === 0} onClick={() => setIndex((value) => Math.max(0, value - 1))}>
              Назад
            </Button>
            {index < questions.length - 1 ? (
              <Button icon={ChevronRight} onClick={() => setIndex((value) => Math.min(questions.length - 1, value + 1))}>
                Следующий
              </Button>
            ) : (
              <Button icon={Send} onClick={() => setConfirm(true)}>Сдать работу</Button>
            )}
          </div>
        </Card>

        <div className="space-y-4">
          <Card className="p-4">
            <p className="text-[10px] font-bold uppercase tracking-wider text-mist-600">Навигация</p>
            <div className="mt-3 grid grid-cols-5 gap-1.5">
              {questions.map((question, questionIndex) => {
                const done = (answers[question.index] ?? "").trim();
                return (
                  <button
                    key={question.index}
                    onClick={() => setIndex(questionIndex)}
                    className={`flex h-9 items-center justify-center rounded-lg text-xs font-bold transition ${
                      questionIndex === index
                        ? "bg-iris-500 text-white"
                        : done
                          ? "bg-emerald-500/15 text-emerald-300"
                          : "bg-white/5 text-mist-500 hover:bg-white/10"
                    }`}
                  >
                    {questionIndex + 1}
                  </button>
                );
              })}
            </div>
            <div className="mt-4">
              <div className="mb-1.5 flex justify-between text-[10px] font-semibold text-mist-500">
                <span>Заполнено</span>
                <span>{answeredCount}/{questions.length}</span>
              </div>
              <Progress value={pct(answeredCount, questions.length)} />
            </div>
          </Card>

          <Button variant="ghost" icon={Send} className="w-full" onClick={() => setConfirm(true)}>
            Завершить и сдать
          </Button>

          <Card className="p-4">
            <div className="flex items-start gap-2 text-[11px] leading-relaxed text-mist-500">
              <Info size={14} className="mt-0.5 shrink-0 text-iris-300" />
              Можно вернуться к любому вопросу до отправки. После сдачи изменить ответы нельзя.
            </div>
          </Card>
        </div>
      </div>

      {confirm && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center p-5">
          <div className="absolute inset-0 bg-ink-950/75 backdrop-blur-sm" onClick={() => setConfirm(false)} />
          <Card className="glass-strong fade-up relative w-full max-w-md p-6">
            <h3 className="font-display text-lg font-semibold text-white">Сдать работу?</h3>
            <p className="mt-2 text-sm leading-relaxed text-mist-400">
              Заполнено {answeredCount} из {questions.length} вопросов.
              {answeredCount < questions.length ? " Незаполненные будут засчитаны как ошибки." : " Все ответы на месте."}
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setConfirm(false)}>Вернуться</Button>
              <Button icon={Send} loading={pending} onClick={submit}>Сдать</Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
