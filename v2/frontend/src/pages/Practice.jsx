import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  Crown,
  Flame,
  Lightbulb,
  RefreshCw,
  RotateCcw,
  Sparkles,
  Star,
  Target,
  Trophy,
  X,
  Zap,
} from "lucide-react";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Progress,
  Ring,
  SectionTitle,
  Skeleton,
} from "../components/ui";
import { useAction, useApi, useSession, toast } from "../lib/hooks";
import { api, invalidate } from "../lib/api";
import { plural } from "../lib/format";

function Widget({ task }) {
  const widget = task?.widget;
  if (!widget) return null;
  if (widget.type === "balance") {
    return (
      <div className="mt-5 rounded-2xl border border-cyan-400/20 bg-cyan-400/[0.05] p-4">
        <div className="flex items-center justify-center gap-6 sm:gap-10">
          <div className="text-center">
            <div className="flex h-16 min-w-[80px] items-center justify-center rounded-2xl border border-cyan-300/30 bg-ink-900/50 px-4 font-display text-2xl font-semibold text-white">
              {widget.left}
            </div>
            <p className="mt-1.5 text-[10px] font-bold uppercase tracking-wider text-mist-600">слева</p>
          </div>
          <div className="relative h-10 w-24">
            <span className="absolute left-1/2 top-0 h-10 w-px -translate-x-1/2 bg-cyan-300/40" />
            <span className="absolute left-0 top-0 h-px w-full bg-cyan-300/40" />
            <span className="absolute left-1/2 top-0 h-10 w-10 -translate-x-1/2 rounded-full border border-cyan-300/40" />
          </div>
          <div className="text-center">
            <div className="flex h-16 min-w-[80px] items-center justify-center rounded-2xl border border-iris-400/30 bg-ink-900/50 px-4 font-display text-2xl font-semibold text-white">
              {widget.right}
            </div>
            <p className="mt-1.5 text-[10px] font-bold uppercase tracking-wider text-mist-600">справа</p>
          </div>
        </div>
        {widget.unknown && (
          <p className="mt-3 text-center text-[11px] text-mist-500">Неизвестное: <span className="font-bold text-iris-300">{widget.unknown}</span></p>
        )}
      </div>
    );
  }
  return null;
}

export function PracticePage() {
  const { roundId } = useParams();
  const navigate = useNavigate();
  const { refreshSession } = useSession();
  const path = `/play/${roundId}`;
  const { data, loading, error, refresh, setData } = useApi(path, { ttl: 0 });
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState(null);
  const [hint, setHint] = useState("");
  const [switching, setSwitching] = useState(false);
  const { pending, run } = useAction();

  const task = data?.task;
  const state = data?.state || {};
  const total = task?.total || state.total || 1;
  const current = (task?.index ?? state.index ?? 0) + 1;

  useEffect(() => {
    setAnswer("");
    setFeedback(null);
    setHint("");
  }, [task?.index, task?.question]);

  const submit = async (value) => {
    const given = (value ?? answer).trim();
    if (!given) {
      toast("Введите ответ", "info");
      return;
    }
    try {
      const result = await run(() => api.post(`${path}/answer`, { answer: given }));
      setFeedback(result);
      invalidate(path);
      invalidate("/map");
      if (result.correct) {
        await refreshSession().catch(() => {});
      }
      if (result.hint) setHint(result.hint);
    } catch (err) {
      toast(err.message || "Не удалось проверить ответ", "error");
    }
  };

  const next = async () => {
    if (feedback?.done) {
      navigate(`/app/play/${roundId}/result`);
      return;
    }
    try {
      const payload = await api.get(path);
      if (payload.done) {
        navigate(`/app/play/${roundId}/result`);
        return;
      }
      setData(payload);
      setFeedback(null);
      setAnswer("");
      setHint("");
    } catch (err) {
      toast(err.message || "Не удалось загрузить следующее задание", "error");
    }
  };

  const askHint = async () => {
    try {
      const payload = await run(() => api.post(`${path}/hint`, {}));
      setHint(payload.hint);
    } catch (err) {
      toast(err.message || "Подсказки закончились", "error");
    }
  };

  const switchMethod = async () => {
    setSwitching(true);
    try {
      const payload = await run(() => api.post(`${path}/switch-method`, {}));
      toast(payload.explanation || `Другой способ: ${payload.name}`, "info", 6500);
    } catch (err) {
      toast(err.message || "Не удалось сменить способ", "error");
    } finally {
      setSwitching(false);
    }
  };

  if (loading && !data) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <ErrorState error={error} onRetry={refresh} />
        <Link to="/app/learn" className="text-sm font-semibold text-iris-300 hover:text-white">← Вернуться к темам</Link>
      </div>
    );
  }

  if (data.done) {
    return (
      <div className="mx-auto max-w-2xl">
        <Card className="p-8 text-center">
          <EmptyState
            icon="🏁"
            title="Раунд завершён"
            text="Посмотрите результат и разбор заданий."
            action={<Button icon={ArrowRight} onClick={() => navigate(`/app/play/${roundId}/result`)}>К результату</Button>}
          />
        </Card>
      </div>
    );
  }

  const answered = Boolean(feedback);
  const final = Boolean(feedback && (feedback.correct || feedback.retry === false || feedback.done));

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="flex items-center justify-between gap-4">
        <Link to={data.topic?.slug ? `/app/learn/${data.topic.slug}` : "/app/learn"} className="inline-flex items-center gap-1.5 text-sm font-semibold text-mist-500 hover:text-white">
          <ArrowLeft size={15} /> Выйти
        </Link>
        <div className="flex items-center gap-2">
          {data.state?.mode === "boss" && <Badge tone="gold"><Crown size={12} /> босс</Badge>}
          {data.state?.mode === "daily" && <Badge tone="cyan"><Zap size={12} /> план дня</Badge>}
          <Badge tone="iris">вопрос {current} из {total}</Badge>
        </div>
      </div>

      <div className="progress h-2">
        <span style={{ width: `${Math.round((state.index / Math.max(total, 1)) * 100)}%` }} />
      </div>

      <Card className="relative overflow-hidden p-6 sm:p-8">
        <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-iris-500/15 blur-3xl" />
        <div className="relative">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-mist-600">{data.topic?.title || "Тренировка"}</p>
              <h1 className="mt-1 font-display text-xl font-semibold text-white">Решите задание</h1>
            </div>
            <div className="flex items-center gap-2">
              {task?.method?.name && <Badge>{task.method.name}</Badge>}
              <Badge tone="gold"><Sparkles size={11} /> {state.combo > 0 ? `серия ${state.combo}` : "серия 0"}</Badge>
            </div>
          </div>

          <p className="mt-6 font-display text-xl font-medium leading-relaxed text-white sm:text-2xl">
            {task?.question}
          </p>

          <Widget task={task} />

          {hint && (
            <div className="mt-4 flex items-start gap-2.5 rounded-2xl border border-amber-400/25 bg-amber-400/[0.07] px-4 py-3">
              <Lightbulb size={16} className="mt-0.5 shrink-0 text-amber-300" />
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider text-amber-300">Подсказка</p>
                <p className="mt-0.5 text-xs leading-relaxed text-amber-100/80">{hint}</p>
              </div>
            </div>
          )}

          {!feedback && (
            <div className="mt-7">
              {task?.answer_type === "choice" && (task.choices || []).length > 0 ? (
                <div className="grid gap-2.5 sm:grid-cols-2">
                  {task.choices.map((choice, index) => (
                    <button
                      key={`${choice}-${index}`}
                      type="button"
                      onClick={() => setAnswer(choice)}
                      className={`rounded-2xl border px-4 py-3.5 text-left text-sm font-semibold transition ${
                        answer === choice
                          ? "border-iris-400/60 bg-iris-500/15 text-white shadow-[0_10px_30px_-18px_rgba(139,123,255,.9)]"
                          : "border-white/9 bg-white/[0.025] text-mist-300 hover:border-white/20 hover:bg-white/[0.05]"
                      }`}
                    >
                      <span className={`mr-2.5 inline-flex h-6 w-6 items-center justify-center rounded-lg border text-[11px] ${
                        answer === choice ? "border-iris-300/40 bg-iris-500/20 text-white" : "border-white/10 text-mist-500"
                      }`}>
                        {String.fromCharCode(65 + index)}
                      </span>
                      {choice}
                    </button>
                  ))}
                </div>
              ) : (
                <input
                  value={answer}
                  onChange={(event) => setAnswer(event.target.value)}
                  onKeyDown={(event) => event.key === "Enter" && submit()}
                  placeholder="Введите ответ…"
                  inputMode={task?.answer_type === "number" ? "decimal" : "text"}
                  autoFocus
                  className="field text-center font-display text-2xl tracking-wide"
                />
              )}

              <div className="mt-4 flex flex-wrap gap-2">
                <Button size="lg" icon={CheckCircle2} loading={pending} onClick={() => submit()}>Проверить</Button>
                <Button size="lg" variant="ghost" icon={Lightbulb} loading={pending} onClick={askHint}>
                  Подсказка{task?.hints_left != null ? ` (${task.hints_left})` : ""}
                </Button>
                {task?.can_switch_method && (
                  <Button size="lg" variant="plain" icon={RefreshCw} loading={switching} onClick={switchMethod}>
                    Другой способ
                  </Button>
                )}
              </div>
            </div>
          )}

          {feedback && (
            <div
              className={`mt-7 rounded-2xl border p-5 ${
                feedback.correct
                  ? "border-emerald-400/30 bg-emerald-500/[0.07]"
                  : "border-rose-400/30 bg-rose-500/[0.06]"
              }`}
            >
              <div className="flex items-start gap-3">
                <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl ${feedback.correct ? "bg-emerald-400/15 text-emerald-300" : "bg-rose-400/15 text-rose-300"}`}>
                  {feedback.correct ? <CheckCircle2 size={20} /> : <X size={20} />}
                </span>
                <div className="min-w-0 flex-1">
                  <p className={`font-display text-lg font-semibold ${feedback.correct ? "text-emerald-200" : "text-rose-200"}`}>
                    {feedback.correct ? "Верно!" : feedback.retry ? "Почти — попробуйте ещё раз" : "Правильный ответ"}
                  </p>
                  {!feedback.correct && (
                    <p className="mt-1 text-sm text-rose-100/80">
                      Верный ответ: <span className="font-bold text-white">{feedback.correct_answer}</span>
                    </p>
                  )}
                  {feedback.solution && (
                    <p className="mt-2 text-xs leading-relaxed text-mist-400">{feedback.solution}</p>
                  )}
                  {feedback.method_switched && (
                    <p className="mt-2 text-xs font-semibold text-iris-300">Мы предложили другой способ решения — попробуйте его.</p>
                  )}
                  {feedback.hint && (
                    <div className="mt-3 rounded-xl border border-amber-400/20 bg-amber-400/[0.05] px-3 py-2 text-xs leading-relaxed text-amber-100/80">
                      <span className="font-bold text-amber-300">Подсказка: </span>{feedback.hint}
                    </div>
                  )}
                  <div className="mt-3 flex flex-wrap items-center gap-2 text-xs font-bold">
                    {feedback.xp > 0 && <Badge tone="iris">+{feedback.xp} XP</Badge>}
                    {feedback.coins > 0 && <Badge tone="gold">+{feedback.coins} 🪙</Badge>}
                    {feedback.combo > 1 && <Badge tone="green"><Flame size={11} /> серия {feedback.combo}</Badge>}
                    {(feedback.badges || []).map((badge) => (
                      <Badge key={badge.code || badge.title} tone="gold"><Trophy size={11} /> {badge.title}</Badge>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-5 flex flex-wrap gap-2">
                {feedback.retry && !feedback.correct && !feedback.done ? (
                  <>
                    <Button variant="ghost" onClick={() => { setFeedback(null); setAnswer(""); }}>Попробовать снова</Button>
                    <Button icon={ArrowRight} onClick={next}>Дальше</Button>
                  </>
                ) : (
                  <Button icon={ArrowRight} onClick={next}>
                    {feedback.done ? "К результату" : "Следующее задание"}
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
      </Card>

      <div className="flex items-center justify-center gap-5 text-[11px] font-semibold text-mist-600">
        <span className="inline-flex items-center gap-1.5"><Target size={13} /> {state.correct || 0} верно</span>
        <span className="inline-flex items-center gap-1.5"><Sparkles size={13} /> {state.xp || 0} XP</span>
        <span className="inline-flex items-center gap-1.5">🪙 {state.coins || 0}</span>
      </div>
    </div>
  );
}

export function PracticeResult() {
  const { roundId } = useParams();
  const navigate = useNavigate();
  const { refreshSession } = useSession();
  const { data, loading, error, refresh } = useApi(`/play/${roundId}/result`, { ttl: 0 });
  const [replay, setReplay] = useState(false);
  const { pending, run } = useAction();

  useEffect(() => {
    refreshSession().catch(() => {});
    invalidate("/map");
    invalidate("/daily");
    invalidate("/assignments");
  }, [refreshSession]);

  const percent = data ? Math.round((data.correct / Math.max(data.total, 1)) * 100) : 0;

  const repeat = async () => {
    setReplay(true);
    try {
      const mode = window.sessionStorage.getItem("school.lastMode");
      if (data?.mode === "daily" || mode === "daily") {
        const payload = await run(() => api.post("/daily/start", {}));
        navigate(`/app/play/${payload.round_id}`);
        return;
      }
      const slug = window.sessionStorage.getItem("school.lastTopic");
      if (!slug) {
        navigate("/app/learn");
        return;
      }
      const payload = await run(() => api.post("/play/start", { topic_slug: slug }));
      navigate(`/app/play/${payload.round_id}`);
    } catch (err) {
      toast(err.message || "Не удалось начать заново", "error");
    } finally {
      setReplay(false);
    }
  };

  if (loading && !data) {
    return <div className="mx-auto max-w-3xl"><Skeleton className="h-80 w-full" /></div>;
  }
  if (error || !data) {
    return <div className="mx-auto max-w-3xl"><ErrorState error={error} onRetry={refresh} /></div>;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <Card className="relative overflow-hidden p-7 text-center sm:p-10">
        <div className="pointer-events-none absolute inset-x-0 -top-24 mx-auto h-64 w-64 rounded-full bg-iris-500/25 blur-3xl" />
        <div className="relative">
          <Badge tone={data.mode === "boss" ? "gold" : "iris"}>
            {data.mode === "boss" ? <><Crown size={12} /> испытание пройдено</> : data.mode === "daily" ? <><Zap size={12} /> план дня</> : <><Sparkles size={12} /> тренировка</>}
          </Badge>
          <h1 className="mt-4 font-display text-3xl font-semibold text-white sm:text-4xl">
            {percent >= 80 ? "Блестяще!" : percent >= 50 ? "Хороший результат" : "Есть над чем поработать"}
          </h1>
          <p className="mt-2 text-sm text-mist-400">
            {percent >= 80
              ? "Тема почти освоена. Закрепите результат ещё одной короткой тренировкой."
              : "Разберите ошибки ниже — и попробуйте снова. Каждая попытка делает вас сильнее."}
          </p>

          <div className="mx-auto mt-6 flex max-w-md items-center justify-center gap-6">
            <Ring value={percent} size={124} stroke={9}>
              <span className="font-display text-2xl font-semibold text-white">{data.correct}/{data.total}</span>
              <span className="text-[9px] font-bold uppercase tracking-wider text-mist-500">верно</span>
            </Ring>
            <div className="space-y-2 text-left">
              <div className="flex items-center gap-2 text-sm font-bold text-white"><Sparkles size={16} className="text-iris-300" /> +{data.xp} XP</div>
              <div className="flex items-center gap-2 text-sm font-bold text-white">🪙 +{data.coins} монет</div>
              <div className="flex items-center gap-2 text-sm font-bold text-white"><Flame size={16} className="text-amber-300" /> серия {data.max_combo}</div>
              <div className="flex items-center gap-1">
                {[1, 2, 3].map((star) => (
                  <Star key={star} size={18} className={star <= data.stars ? "fill-amber-300 text-amber-300" : "text-white/15"} />
                ))}
              </div>
            </div>
          </div>

          {data.badges?.length > 0 && (
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {data.badges.map((badge) => (
                <Badge key={badge.code || badge.title} tone="gold"><Trophy size={12} /> {badge.title}</Badge>
              ))}
            </div>
          )}

          <div className="mt-7 flex flex-wrap justify-center gap-2">
            <Button icon={ArrowRight} onClick={() => navigate("/app")}>На главную</Button>
            <Button variant="ghost" icon={RotateCcw} loading={replay || pending} onClick={repeat}>Ещё тренировка</Button>
            <Button variant="ghost" onClick={() => navigate("/app/learn")}>К темам</Button>
          </div>
        </div>
      </Card>

      <Card className="p-5 sm:p-6">
        <SectionTitle eyebrow="Разбор" title="Что было в раунде" subtitle="Посмотрите, где ошиблись, и запомните верный ход." />
        <div className="mt-5 space-y-2.5">
          {data.items.map((item, index) => (
            <div key={index} className={`rounded-2xl border px-4 py-3.5 ${item.correct ? "border-emerald-400/20 bg-emerald-500/[0.04]" : "border-rose-400/20 bg-rose-500/[0.04]"}`}>
              <div className="flex items-start gap-3">
                <span className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg ${item.correct ? "bg-emerald-400/15 text-emerald-300" : "bg-rose-400/15 text-rose-300"}`}>
                  {item.correct ? <CheckCircle2 size={14} /> : <X size={14} />}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold leading-relaxed text-white">{item.question}</p>
                  <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
                    <span className="text-mist-500">Ваш ответ: <span className={item.correct ? "font-bold text-emerald-300" : "font-bold text-rose-300"}>{item.given || "—"}</span></span>
                    {!item.correct && <span className="text-mist-500">Верно: <span className="font-bold text-emerald-300">{item.answer}</span></span>}
                  </div>
                  {item.solution && <p className="mt-1.5 text-[11px] leading-relaxed text-mist-600">{item.solution}</p>}
                </div>
              </div>
            </div>
          ))}
          {data.items.length === 0 && <EmptyState icon="🗂" title="Разбор пуст" text="В этом раунде не было сохранённых заданий." />}
        </div>
      </Card>
    </div>
  );
}
