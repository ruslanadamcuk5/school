import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Bookmark,
  Check,
  CheckCircle2,
  CircleHelp,
  Clock,
  Crown,
  Eye,
  Gamepad2,
  GraduationCap,
  Lightbulb,
  Lock,
  Play,
  Search,
  Sparkles,
  Star,
  Target,
  Trophy,
  Video,
  X,
  Zap,
} from "lucide-react";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Modal,
  PageHeader,
  Progress,
  SectionTitle,
  Skeleton,
  Tabs,
} from "../components/ui";
import { useAction, useApi, useSession, toast } from "../lib/hooks";
import { api, invalidate } from "../lib/api";
import { plural, subjectColor } from "../lib/format";

/* ==================================================================== LIST */
export function LearnPage() {
  const { session } = useSession();
  const learner = session?.learner;
  const { data, loading, error, refresh } = useApi("/topics");
  const { data: map } = useApi("/map");
  const [search, setSearch] = useState("");
  const [subject, setSubject] = useState("all");
  const [scope, setScope] = useState("my");
  const grade = map?.grade || learner?.grade || 3;

  const subjects = data?.subjects || [];
  const allTopics = data?.topics || [];

  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    return allTopics.filter((topic) => {
      if (scope === "my" && Number(topic.grade) !== Number(grade)) return false;
      if (subject !== "all" && Number(topic.subject_id) !== Number(subject)) return false;
      if (query && !`${topic.title} ${topic.description} ${topic.subject_name}`.toLowerCase().includes(query)) return false;
      return true;
    });
  }, [allTopics, scope, subject, grade, search]);

  const grouped = useMemo(() => {
    const map = new Map();
    visible.forEach((topic) => {
      const key = topic.subject_slug || String(topic.subject_id);
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(topic);
    });
    return [...map.entries()];
  }, [visible]);

  const myTopics = allTopics.filter((topic) => Number(topic.grade) === Number(grade));
  const readingCount = myTopics.filter((topic) => topic.kind === "reading").length;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Карта знаний"
        subtitle={`Программа ${grade} класса: ${myTopics.length} ${plural(myTopics.length, ["тема", "темы", "тем"])} по ${subjects.length} предметам. Выбирайте тему и тренируйтесь.`}
        actions={<Button variant="ghost" icon={BookOpen} onClick={() => setScope(scope === "my" ? "all" : "my")}>
          {scope === "my" ? "Показать все классы" : `Только ${grade} класс`}
        </Button>}
      />

      <div className="grid gap-3 sm:grid-cols-3">
        {[
          [GraduationCap, "Тем в программе", myTopics.length, "iris"],
          [BookOpen, "Для чтения", readingCount, "cyan"],
          [Gamepad2, "Для тренировки", myTopics.length - readingCount, "green"],
        ].map(([Icon, label, value, tone]) => (
          <Card key={label} className="flex items-center gap-4 p-5">
            <span className={`flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 ${
              tone === "cyan" ? "bg-cyan-400/10 text-cyan-300" : tone === "green" ? "bg-emerald-400/10 text-emerald-300" : "bg-iris-500/12 text-iris-300"
            }`}>
              <Icon size={20} />
            </span>
            <div>
              <p className="font-display text-2xl font-semibold text-white">{value}</p>
              <p className="text-[11px] font-bold uppercase tracking-wider text-mist-500">{label}</p>
            </div>
          </Card>
        ))}
      </div>

      <Card className="p-4 sm:p-5">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="relative flex-1">
            <Search size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-mist-500" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Найти тему: дроби, умножение, части речи…"
              className="field pl-10"
            />
          </div>
          <div className="no-scrollbar flex gap-1.5 overflow-x-auto">
            <button
              onClick={() => setSubject("all")}
              className={`shrink-0 rounded-xl border px-3 py-2 text-xs font-bold transition ${
                subject === "all" ? "border-iris-400/40 bg-iris-500/15 text-white" : "border-white/8 bg-white/[0.025] text-mist-500 hover:text-white"
              }`}
            >
              Все предметы
            </button>
            {subjects.map((item) => (
              <button
                key={item.id}
                onClick={() => setSubject(String(item.id))}
                className={`shrink-0 rounded-xl border px-3 py-2 text-xs font-bold transition ${
                  String(subject) === String(item.id)
                    ? "border-iris-400/40 bg-iris-500/15 text-white"
                    : "border-white/8 bg-white/[0.025] text-mist-500 hover:text-white"
                }`}
              >
                <span className="mr-1.5">{item.icon}</span>
                {item.name}
              </button>
            ))}
          </div>
        </div>
      </Card>

      {error && <ErrorState error={error} onRetry={refresh} />}

      {loading && !data && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-40" />)}
        </div>
      )}

      {!loading && visible.length === 0 && (
        <Card>
          <EmptyState
            icon="🔍"
            title="Ничего не нашлось"
            text="Попробуйте другой запрос или сбросьте фильтры по предметам."
            action={(
              <Button variant="ghost" onClick={() => { setSearch(""); setSubject("all"); setScope("my"); }}>
                Сбросить фильтры
              </Button>
            )}
          />
        </Card>
      )}

      <div className="space-y-8">
        {grouped.map(([slug, items]) => {
          const sample = items[0];
          const tone = subjectColor(sample.color);
          return (
            <section key={slug}>
              <div className="mb-3 flex items-center gap-2.5">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl text-base" style={{ background: tone.soft }}>
                  {sample.subject_icon || "📘"}
                </span>
                <h2 className="font-display text-lg font-semibold text-white">{sample.subject_name}</h2>
                <span className="text-xs text-mist-600">{items.length}</span>
                <div className="h-px flex-1 bg-white/6" />
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {items.map((topic) => {
                  const locked = Number(topic.grade) !== Number(grade);
                  return (
                    <Link
                      key={topic.slug}
                      to={locked ? "#" : `/app/learn/${topic.slug}`}
                      onClick={(event) => {
                        if (locked) {
                          event.preventDefault();
                          toast(`Тема для ${topic.grade} класса. Ваш класс — ${grade}.`, "info");
                        }
                      }}
                      className={`card card-hover group relative overflow-hidden p-5 ${locked ? "opacity-60" : ""}`}
                      style={{ background: `linear-gradient(150deg, ${tone.soft}, rgba(255,255,255,.016))` }}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-ink-900/40 text-xl">
                          {topic.icon || "📖"}
                        </span>
                        <div className="flex items-center gap-1.5">
                          {locked && <Badge><Lock size={11} /> {topic.grade} кл.</Badge>}
                          <Badge tone={topic.kind === "reading" ? "cyan" : "iris"}>
                            {topic.kind === "reading" ? "чтение" : "практика"}
                          </Badge>
                        </div>
                      </div>
                      <h3 className="mt-4 font-display text-[0.98rem] font-semibold leading-snug text-white">{topic.title}</h3>
                      <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-mist-500">{topic.description}</p>
                      <div className="mt-4 flex items-center justify-between text-[11px] font-semibold text-mist-600">
                        <span>{topic.subject_name} · {topic.grade} класс</span>
                        <span className="inline-flex items-center gap-1 text-iris-300 opacity-0 transition group-hover:opacity-100">
                          Открыть <ArrowRight size={12} />
                        </span>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}

/* =================================================================== TOPIC */
function QuizModal({ open, slug, onClose, onDone }) {
  const [stage, setStage] = useState("intro");
  const [quiz, setQuiz] = useState(null);
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const { pending, run } = useAction();

  const reset = () => {
    setStage("intro");
    setQuiz(null);
    setAnswers({});
    setResult(null);
    setError("");
  };

  const start = async () => {
    setError("");
    try {
      const data = await run(() => api.get(`/topics/${slug}/quiz`));
      setQuiz(data);
      setAnswers({});
      setStage("quiz");
    } catch (err) {
      setError(err.message || "Не удалось подготовить вопросы");
    }
  };

  const submit = async () => {
    setError("");
    try {
      const data = await run(() =>
        api.post(`/topics/${slug}/quiz`, {
          quiz_id: quiz.quiz_id,
          answers: quiz.questions.map((question) => answers[question.index] || ""),
        }),
      );
      setResult(data);
      setStage("result");
      invalidate(`/topics/${slug}`);
      invalidate("/map");
      onDone?.();
    } catch (err) {
      setError(err.message || "Не удалось проверить ответы");
    }
  };

  const close = () => {
    onClose();
    setTimeout(reset, 150);
  };

  return (
    <Modal
      open={open}
      onClose={close}
      title={stage === "result" ? "Результат теста" : "Проверка понимания"}
      description={stage === "result" ? "Каждый ответ разобран — можно вернуться к тексту." : "Вопросы по прочитанному. Без спешки: можно вернуться к тексту."}
      size="lg"
      footer={
        stage === "intro" ? (
          <>
            <Button variant="ghost" onClick={close}>Позже</Button>
            <Button icon={Sparkles} loading={pending} onClick={start}>Начать тест</Button>
          </>
        ) : stage === "quiz" ? (
          <>
            <Button variant="ghost" onClick={close}>Закрыть</Button>
            <Button icon={Check} loading={pending} onClick={submit}>Проверить ответы</Button>
          </>
        ) : (
          <Button onClick={close}>Готово</Button>
        )
      }
    >
      {error && (
        <div className="mb-4 rounded-xl border border-rose-400/25 bg-rose-500/10 px-3.5 py-3 text-xs font-semibold text-rose-200">
          {error}
        </div>
      )}

      {stage === "intro" && (
        <div className="py-4 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl border border-iris-400/25 bg-iris-500/10 text-3xl">🧠</div>
          <h4 className="mt-4 font-display text-lg font-semibold text-white">Проверим, как усвоена тема</h4>
          <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-mist-500">
            Несколько вопросов по теме — с вариантами ответов или коротким ответом.
            Это не оценка, а способ заметить, что стоит перечитать.
          </p>
        </div>
      )}

      {stage === "quiz" && quiz && (
        <div className="space-y-4">
          {quiz.questions.map((question) => (
            <div key={question.index} className="rounded-2xl border border-white/8 bg-white/[0.025] p-4">
              <p className="text-sm font-semibold leading-relaxed text-white">
                <span className="mr-2 text-iris-300">{question.index + 1}.</span>
                {question.question}
              </p>
              {(question.choices || []).length > 0 ? (
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  {question.choices.map((choice, choiceIndex) => {
                    const active = answers[question.index] === choice;
                    return (
                      <button
                        key={`${question.index}-${choiceIndex}`}
                        type="button"
                        onClick={() => setAnswers((current) => ({ ...current, [question.index]: choice }))}
                        className={`rounded-xl border px-3 py-2.5 text-left text-xs font-semibold transition ${
                          active
                            ? "border-iris-400/50 bg-iris-500/15 text-white"
                            : "border-white/8 bg-white/[0.02] text-mist-300 hover:border-white/20"
                        }`}
                      >
                        <span className="mr-2 text-mist-600">{String.fromCharCode(65 + choiceIndex)}</span>
                        {choice}
                      </button>
                    );
                  })}
                </div>
              ) : (
                <input
                  value={answers[question.index] || ""}
                  onChange={(event) => setAnswers((current) => ({ ...current, [question.index]: event.target.value }))}
                  placeholder={question.answer_type === "fraction" ? "Например, 3/4" : "Введите ответ"}
                  inputMode={question.answer_type === "number" || question.answer_type === "fraction" ? "decimal" : "text"}
                  className="mt-3 w-full rounded-xl border border-white/10 bg-ink-950/50 px-3.5 py-2.5 text-sm font-semibold text-white outline-none transition placeholder:text-mist-600 focus:border-iris-400/50"
                />
              )}
            </div>
          ))}
        </div>
      )}

      {stage === "result" && result && (
        <div>
          <div className="flex items-center gap-5 rounded-2xl border border-white/8 bg-white/[0.03] p-5">
            <div className="text-center">
              <p className="font-display text-3xl font-semibold text-white">{result.correct}/{result.total}</p>
              <p className="text-[10px] font-bold uppercase tracking-wider text-mist-500">верно</p>
            </div>
            <div className="h-10 w-px bg-white/10" />
            <div className="flex items-center gap-1">
              {[1, 2, 3].map((star) => (
                <Star key={star} size={22} className={star <= result.stars ? "fill-amber-300 text-amber-300" : "text-white/15"} />
              ))}
            </div>
            <div className="ml-auto">
              <Badge tone={result.correct === result.total ? "green" : "iris"}>
                {result.correct === result.total ? "Отлично!" : "Можно улучшить"}
              </Badge>
            </div>
          </div>
          <div className="mt-4 space-y-2">
            {result.results.map((item) => (
              <div key={item.index} className={`rounded-xl border px-3.5 py-3 ${item.correct ? "border-emerald-400/20 bg-emerald-500/[0.04]" : "border-rose-400/20 bg-rose-500/[0.04]"}`}>
                <div className="flex items-start gap-2">
                  {item.correct ? <CheckCircle2 size={15} className="mt-0.5 shrink-0 text-emerald-300" /> : <X size={15} className="mt-0.5 shrink-0 text-rose-300" />}
                  <div>
                    <p className="text-xs font-semibold text-white">{item.question}</p>
                    <p className="mt-1 text-[11px] text-mist-500">
                      Ваш ответ: <span className={item.correct ? "text-emerald-300" : "text-rose-300"}>{item.given || "—"}</span>
                      {!item.correct && <> · верно: <span className="text-emerald-300">{item.expected}</span></>}
                    </p>
                    {item.solution && <p className="mt-1 text-[11px] leading-relaxed text-mist-600">{item.solution}</p>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </Modal>
  );
}

function ExplainModal({ open, slug, onClose }) {
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return undefined;
    let alive = true;
    setContent(null);
    setError("");
    setLoading(true);
    api.get(`/ai/explain/${slug}`)
      .then((data) => { if (alive) setContent(data); })
      .catch((err) => { if (alive) setError(err.message || "Не удалось получить объяснение"); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [open, slug]);

  const refresh = async () => {
    setRefreshing(true);
    setError("");
    try {
      const data = await api.post(`/ai/explain/${slug}/refresh`, {});
      setContent(data);
    } catch (err) {
      setError(err.message || "Не удалось обновить объяснение");
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Объяснение темы"
      description="ИИ разберёт тему простыми словами, с примерами и вопросами для самопроверки."
      size="lg"
      footer={
        <>
          {content && !loading && (
            <Button variant="ghost" icon={Sparkles} loading={refreshing} onClick={refresh}>
              Обновить
            </Button>
          )}
          <Button onClick={onClose}>Готово</Button>
        </>
      }
    >
      {loading && (
        <div className="space-y-3 py-4">
          <Skeleton className="h-5 w-2/3" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-11/12" />
          <Skeleton className="h-4 w-4/5" />
        </div>
      )}

      {!loading && error && (
        <div className="rounded-xl border border-rose-400/25 bg-rose-500/10 px-3.5 py-3 text-xs font-semibold text-rose-200">
          <p>{error}</p>
          <p className="mt-1 font-normal text-rose-200/70">
            Проверьте настройки ИИ в админ-панели или попробуйте позже.
            Учебные материалы темы остаются доступны.
          </p>
        </div>
      )}

      {!loading && content && (
        <div>
          <div
            className="text-sm leading-relaxed text-mist-300 [&_code]:rounded [&_code]:bg-white/10 [&_code]:px-1 [&_h3]:mt-5 [&_h3]:font-display [&_h3]:text-lg [&_h3]:font-semibold [&_h3]:text-white [&_h4]:mt-4 [&_h4]:font-bold [&_h4]:text-white [&_li]:mt-1.5 [&_ol]:mt-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:mt-3 [&_strong]:text-white [&_ul]:mt-3 [&_ul]:list-disc [&_ul]:pl-5"
            dangerouslySetInnerHTML={{ __html: content.html || "" }}
          />
          <p className="mt-5 border-t border-white/8 pt-3 text-[11px] leading-relaxed text-mist-600">
            Объяснение сгенерировано моделью{content.model ? ` «${content.model}»` : ""}.
            ИИ может ошибаться — сверяйтесь с учебником.
          </p>
        </div>
      )}
    </Modal>
  );
}

export function TopicPage() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { session } = useSession();
  const { data, loading, error, refresh } = useApi(`/topics/${slug}`);
  const [tab, setTab] = useState("overview");
  const [quizOpen, setQuizOpen] = useState(false);
  const [explainOpen, setExplainOpen] = useState(false);
  const [readText, setReadText] = useState(null);
  const [textLoading, setTextLoading] = useState(false);
  const [videos, setVideos] = useState(null);
  const [videoLoading, setVideoLoading] = useState(false);
  const [readMarked, setReadMarked] = useState(false);
  const { pending, run } = useAction();

  const topic = data?.topic;
  const tone = subjectColor(topic?.color);
  const methods = data?.methods || [];
  const primaryBook = (data?.books || [])[0];
  const readHref = primaryBook
    ? `/app/library/-${primaryBook.id}?page=${primaryBook.page || 1}`
    : "/app/library";

  const openTab = async (key) => {
    setTab(key);
    if (key === "text" && !readText && !textLoading) {
      setTextLoading(true);
      try {
        const payload = await api.get(`/topics/${slug}/text`);
        setReadText(payload);
      } catch (err) {
        toast(err.message || "Текст недоступен", "error");
      } finally {
        setTextLoading(false);
      }
    }
    if (key === "videos" && !videos && !videoLoading) {
      setVideoLoading(true);
      try {
        const payload = await api.get(`/topics/${slug}/videos`);
        setVideos(payload);
      } catch (err) {
        toast(err.message || "Видео недоступны", "error");
      } finally {
        setVideoLoading(false);
      }
    }
  };

  const start = async (mode = "practice") => {
    try {
      const payload = await run(() => api.post("/play/start", { topic_slug: slug, mode }));
      try { window.sessionStorage.setItem("school.lastTopic", slug); } catch { /* ignore */ }
      invalidate("/map");
      navigate(`/app/play/${payload.round_id}`);
    } catch (err) {
      toast(err.message || "Не удалось начать тренировку", "error");
    }
  };

  const markRead = async () => {
    try {
      const payload = await run(() => api.post(`/topics/${slug}/read`, {}));
      setReadMarked(true);
      invalidate("/map");
      invalidate(`/topics/${slug}`);
      await refresh();
      if (payload.xp) toast(`Прочитано! +${payload.xp} XP и +${payload.coins} монет`, "success");
      else toast("Тема уже отмечена как прочитанная", "info");
    } catch (err) {
      toast(err.message || "Не удалось отметить тему", "error");
    }
  };

  if (loading && !data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-52 w-full" />
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }

  if (error || !topic) {
    return (
      <div className="space-y-4">
        <Link to="/app/learn" className="inline-flex items-center gap-1.5 text-sm font-semibold text-mist-500 hover:text-white">
          <ArrowLeft size={15} /> К карте знаний
        </Link>
        <ErrorState error={error} onRetry={refresh} />
      </div>
    );
  }

  const tabs = [
    { key: "overview", label: "Обзор" },
    ...(data.can_read ? [{ key: "text", label: "Текст темы" }] : []),
    { key: "videos", label: "Видео" },
    ...(data.can_quiz ? [{ key: "quiz", label: "Тест" }] : []),
  ];

  return (
    <div className="space-y-5">
      <Link to="/app/learn" className="inline-flex items-center gap-1.5 text-sm font-semibold text-mist-500 hover:text-white">
        <ArrowLeft size={15} /> К карте знаний
      </Link>

      <Card className="relative overflow-hidden p-6 sm:p-7" style={{ background: `linear-gradient(150deg, ${tone.soft}, rgba(255,255,255,.018))` }}>
        <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full blur-3xl" style={{ background: tone.soft }} />
        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex gap-4">
            <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-3xl border border-white/12 bg-ink-900/50 text-3xl">
              {topic.icon || "📖"}
            </span>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="iris">{topic.subject_name || "Предмет"}</Badge>
                <Badge>{topic.grade} класс</Badge>
                <Badge tone={topic.kind === "reading" ? "cyan" : "green"}>
                  {topic.kind === "reading" ? <BookOpen size={11} /> : <Gamepad2 size={11} />}
                  {topic.kind === "reading" ? "чтение" : "практика"}
                </Badge>
              </div>
              <h1 className="mt-3 font-display text-2xl font-semibold text-white sm:text-3xl">{topic.title}</h1>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-mist-400">{topic.description}</p>
              <div className="mt-4 flex flex-wrap items-center gap-4 text-xs font-semibold text-mist-500">
                <span className="inline-flex items-center gap-1.5"><Star size={13} className="text-amber-300" /> {topic.stars || 0} из 3</span>
                <span className="inline-flex items-center gap-1.5"><Target size={13} className="text-cyan-300" /> {topic.correct || 0} верных из {topic.attempts || 0}</span>
                {topic.page_start ? <span className="inline-flex items-center gap-1.5"><BookOpen size={13} /> стр. {topic.page_start}{topic.page_end && topic.page_end !== topic.page_start ? `–${topic.page_end}` : ""}</span> : null}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {primaryBook ? (
              <Link to={readHref}>
                <Button size="lg" variant="ghost" icon={BookOpen}>
                  Читать тему{primaryBook.page ? ` · с. ${primaryBook.page}` : ""}
                </Button>
              </Link>
            ) : (
              <Link to="/app/library">
                <Button size="lg" variant="ghost" icon={BookOpen}>Учебники</Button>
              </Link>
            )}
            {data.can_play && (
              <>
                <Button size="lg" icon={Play} loading={pending} onClick={() => start("practice")}>Тренировка</Button>
                <Button size="lg" variant="ghost" icon={Crown} loading={pending} onClick={() => start("boss")}>Босс</Button>
              </>
            )}
            {data.ai_available && (
              <Button size="lg" variant="ghost" icon={Sparkles} onClick={() => setExplainOpen(true)}>
                Объяснить с ИИ
              </Button>
            )}
            {data.can_quiz && (
              <Button size="lg" variant={data.can_play ? "ghost" : "primary"} icon={Sparkles} onClick={() => setQuizOpen(true)}>
                Пройти тест
              </Button>
            )}
          </div>
        </div>
      </Card>

      <Tabs tabs={tabs} value={tab} onChange={openTab} />

      {tab === "overview" && (
        <div className="grid gap-5 lg:grid-cols-[1.3fr_0.7fr]">
          <div className="min-w-0 space-y-5">
            <Card className="p-5 sm:p-6">
              <SectionTitle
                eyebrow="Способы решения"
                title="Как можно рассуждать"
                subtitle="Разные приёмы для одной темы. Выберите тот, который понятнее."
              />
              <div className="mt-5 space-y-2.5">
                {methods.length === 0 && (
                  <EmptyState icon="📘" title="Материалы готовятся" text="Для этой темы пока нет разобранных способов. Откройте текст или начните тренировку." />
                )}
                {methods.map((method, index) => (
                  <details key={method.slug} className="group rounded-2xl border border-white/8 bg-white/[0.025] px-4 py-3 open:border-iris-400/25 open:bg-white/[0.04]">
                    <summary className="flex cursor-pointer list-none items-center gap-3">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-xs font-bold text-iris-300">
                        {index + 1}
                      </span>
                      <span className="flex-1 text-sm font-bold text-white">{method.name}</span>
                      {method.mastered ? (
                        <Badge tone="green"><CheckCircle2 size={11} /> освоено</Badge>
                      ) : (
                        <span className="text-[11px] text-mist-600">{method.correct || 0}/{method.attempts || 0}</span>
                      )}
                      <Lightbulb size={15} className="text-mist-600 group-open:text-amber-300" />
                    </summary>
                    <div className="mt-3 pl-11">
                      <p className="text-xs leading-relaxed text-mist-400">{method.explanation}</p>
                      {(method.steps || []).length > 0 && (
                        <ol className="mt-3 space-y-1.5">
                          {method.steps.map((step, stepIndex) => (
                            <li key={stepIndex} className="flex gap-2 text-[11px] leading-relaxed text-mist-500">
                              <span className="text-iris-400">{stepIndex + 1}.</span>
                              {step.text}
                            </li>
                          ))}
                        </ol>
                      )}
                    </div>
                  </details>
                ))}
              </div>
            </Card>

            {(data.books || []).length > 0 && (
              <Card className="p-5 sm:p-6">
                <SectionTitle eyebrow="Учебники" title="Где почитать" />
                <div className="mt-4 space-y-2">
                  {data.books.map((book) => (
                    <Link
                      key={book.id}
                      to={`/app/library/-${book.id}?page=${book.page || 1}`}
                      className="flex items-center gap-3 rounded-xl border border-white/8 bg-white/[0.025] px-3.5 py-3 transition hover:border-iris-400/30"
                    >
                      <BookOpen size={17} className="text-iris-300" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-bold text-white">{book.title}</p>
                        <p className="text-[11px] text-mist-500">{book.author || "Учебное пособие"}{book.page ? ` · стр. ${book.page}` : ""}</p>
                      </div>
                      <ArrowRight size={14} className="text-mist-600" />
                    </Link>
                  ))}
                </div>
              </Card>
            )}
          </div>

          <div className="space-y-5">
            <Card className="p-5">
              <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-mist-500">Прогресс темы</p>
              <div className="mt-4 flex items-center gap-4">
                <div className="flex items-center gap-1">
                  {[1, 2, 3].map((star) => (
                    <Star key={star} size={26} className={star <= (topic.stars || 0) ? "fill-amber-300 text-amber-300" : "text-white/15"} />
                  ))}
                </div>
                <span className="text-sm font-bold text-white">{topic.stars || 0}/3</span>
              </div>
              <div className="mt-4 space-y-3">
                <div>
                  <div className="mb-1.5 flex justify-between text-[11px] font-semibold text-mist-500">
                    <span>Освоение способов</span>
                    <span>{methods.filter((m) => m.mastered).length}/{methods.length || 1}</span>
                  </div>
                  <Progress value={methods.length ? (methods.filter((m) => m.mastered).length / methods.length) * 100 : 0} />
                </div>
                <div>
                  <div className="mb-1.5 flex justify-between text-[11px] font-semibold text-mist-500">
                    <span>Точность</span>
                    <span>{topic.attempts ? Math.round((topic.correct / topic.attempts) * 100) : 0}%</span>
                  </div>
                  <Progress value={topic.attempts ? (topic.correct / topic.attempts) * 100 : 0} />
                </div>
              </div>
              <div className="mt-4 rounded-xl border border-white/7 bg-white/[0.02] p-3 text-[11px] leading-relaxed text-mist-500">
                <span className="font-bold text-iris-300">Совет:</span> короткая тренировка
                каждый день эффективнее, чем одна длинная раз в неделю.
              </div>
            </Card>

            <Card className="p-5">
              <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-mist-500">Дальше</p>
              <div className="mt-3 space-y-2">
                <button onClick={() => openTab("text")} className="flex w-full items-center gap-3 rounded-xl border border-white/8 bg-white/[0.025] px-3.5 py-3 text-left transition hover:border-iris-400/25">
                  <Eye size={16} className="text-cyan-300" />
                  <div className="flex-1">
                    <p className="text-xs font-bold text-white">Прочитать текст темы</p>
                    <p className="text-[10px] text-mist-500">Страницы пособия и объяснение</p>
                  </div>
                  <ArrowRight size={13} className="text-mist-600" />
                </button>
                <button onClick={() => openTab("videos")} className="flex w-full items-center gap-3 rounded-xl border border-white/8 bg-white/[0.025] px-3.5 py-3 text-left transition hover:border-iris-400/25">
                  <Video size={16} className="text-rose-300" />
                  <div className="flex-1">
                    <p className="text-xs font-bold text-white">Посмотреть видео</p>
                    <p className="text-[10px] text-mist-500">Подборка по теме</p>
                  </div>
                  <ArrowRight size={13} className="text-mist-600" />
                </button>
                {data.ai_available && (
                  <button onClick={() => setExplainOpen(true)} className="flex w-full items-center gap-3 rounded-xl border border-iris-400/20 bg-iris-500/[0.06] px-3.5 py-3 text-left transition hover:border-iris-400/35">
                    <Sparkles size={16} className="text-iris-300" />
                    <div className="flex-1">
                      <p className="text-xs font-bold text-white">Объяснить с ИИ</p>
                      <p className="text-[10px] text-mist-500">Простыми словами и с примерами</p>
                    </div>
                    <ArrowRight size={13} className="text-mist-600" />
                  </button>
                )}
              </div>
            </Card>
          </div>
        </div>
      )}

      {tab === "text" && (
        <Card className="p-6 sm:p-8">
          {textLoading && <Skeleton className="h-64 w-full" />}
          {!textLoading && readText && (
            <div>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <SectionTitle eyebrow="Чтение" title="Текст темы" subtitle="Прочитайте и отметьте — за это начисляется опыт." />
                <div className="flex flex-wrap items-center gap-2">
                  {primaryBook && (
                    <Link to={readHref}>
                      <Button size="sm" variant="ghost" icon={BookOpen}>
                        Открыть PDF{primaryBook.page ? ` · стр. ${primaryBook.page}` : ""}
                      </Button>
                    </Link>
                  )}
                  {topic.kind === "reading" && (
                    <Button size="sm" icon={CheckCircle2} loading={pending} onClick={markRead} disabled={readMarked}>
                      {readMarked ? "Прочитано" : "Отметить прочитанным"}
                    </Button>
                  )}
                </div>
              </div>

              <div className="mt-6 space-y-5">
                {(readText.pages || []).map((page, index) => (
                  <article key={index} className="rounded-2xl border border-white/8 bg-white/[0.02] p-5">
                    {page.page && (
                      <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.14em] text-mist-600">Страница {page.page}</p>
                    )}
                    <p className="whitespace-pre-line text-[15px] leading-[1.85] text-mist-300">
                      {page.text || "Текст страницы пока недоступен."}
                    </p>
                  </article>
                ))}
                {(readText.pages || []).length === 0 && (
                  <EmptyState icon="📄" title="Текст пока не загружен" text="Воспользуйтесь тренировкой или откройте учебник в библиотеке." />
                )}
              </div>

              {readText.questions?.length > 0 && (
                <div className="mt-6 rounded-2xl border border-iris-400/20 bg-iris-500/[0.06] p-5">
                  <p className="text-sm font-bold text-white">Вопросы для самопроверки</p>
                  <div className="mt-3 space-y-2">
                    {readText.questions.map((question, index) => (
                      <details key={index} className="rounded-xl border border-white/8 bg-white/[0.02] px-3.5 py-2.5">
                        <summary className="cursor-pointer text-xs font-semibold text-mist-300">{question.question}</summary>
                        <p className="mt-2 text-[11px] text-emerald-300">{question.answer}</p>
                      </details>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      {tab === "videos" && (
        <Card className="p-6 sm:p-8">
          {videoLoading && <Skeleton className="h-64 w-full" />}
          {!videoLoading && videos && (
            <>
              <SectionTitle
                eyebrow="Видео"
                title="Смотрим и разбираем"
                subtitle={videos.youtube_enabled ? "Видео подобраны под тему и проверены на доступность." : "YouTube ещё не подключён в настройках платформы."}
              />
              {videos.videos?.length > 0 ? (
                <div className="mt-6 grid gap-4 sm:grid-cols-2">
                  {videos.videos.map((video) => (
                    <div key={video.video_id || video.id} className="overflow-hidden rounded-2xl border border-white/8 bg-ink-900/40">
                      <div className="aspect-video w-full bg-ink-950">
                        <iframe
                          className="h-full w-full"
                          src={video.embed_url || `https://www.youtube-nocookie.com/embed/${video.video_id}?rel=0&modestbranding=1&playsinline=1`}
                          title={video.title || "Видео по теме"}
                          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                          allowFullScreen
                          loading="lazy"
                        />
                      </div>
                      <div className="p-4">
                        <p className="line-clamp-2 text-sm font-bold text-white">{video.title}</p>
                        <p className="mt-1 text-[11px] text-mist-500">{video.channel || "YouTube"}</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  icon="🎬"
                  title={videos.youtube_enabled ? "Видео пока не подобраны" : "YouTube не подключён"}
                  text={videos.message || "Администратор может включить подбор видео в разделе YouTube."}
                />
              )}
            </>
          )}
        </Card>
      )}

      {tab === "quiz" && (
        <Card className="p-6 sm:p-8">
          <EmptyState
            icon="🧠"
            title="Тест по теме"
            text="Несколько вопросов с вариантами ответов. Результат покажет, что стоит перечитать."
            action={<Button icon={Sparkles} onClick={() => setQuizOpen(true)}>Начать тест</Button>}
          />
        </Card>
      )}

      <QuizModal
        open={quizOpen}
        slug={slug}
        onClose={() => setQuizOpen(false)}
        onDone={() => refresh()}
      />

      <ExplainModal
        open={explainOpen}
        slug={slug}
        onClose={() => setExplainOpen(false)}
      />
    </div>
  );
}
