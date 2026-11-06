import { Component, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useNavigate, useParams } from "react-router-dom";
import * as THREE from "three";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Coins,
  Gamepad2,
  Lightbulb,
  MapPin,
  Play,
  RotateCcw,
  Sparkles,
  Star,
  Target,
  Timer,
  Trophy,
  X,
} from "lucide-react";
import {
  Badge,
  Button,
  Card,
  ErrorState,
  PageHeader,
  Progress,
  Skeleton,
} from "../components/ui";
import { useApi, useSession, toast } from "../lib/hooks";
import { api, invalidate } from "../lib/api";

/* ==================================================================== LIST */
export function QuestsPage() {
  const { data, loading, error, refresh } = useApi("/quests");

  if (loading && !data) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-36 w-full" />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-52 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (error) return <ErrorState error={error} onRetry={refresh} />;

  const quests = data?.quests || [];
  const book = data?.book;
  const done = data?.completed || 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="3D-квесты"
        subtitle="Пять станций, пять заданий и десять минут приключения по каждой теме учебника. Управляйте героем с клавиатуры или джойстиком."
        badge={<Badge tone="iris"><Gamepad2 size={12} /> интерактив</Badge>}
      />

      <Card className="relative overflow-hidden p-5 sm:p-6">
        <div className="pointer-events-none absolute -right-24 -top-20 h-64 w-64 rounded-full bg-iris-500/20 blur-3xl" />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-start gap-4">
            <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-white/12 bg-ink-900/60 text-2xl">
              {data?.subject?.icon || "🔢"}
            </span>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="cyan">{data?.subject?.name || "Математика"}</Badge>
                <Badge>{data?.grade || 3} класс</Badge>
                {book ? <Badge tone="green"><BookOpen size={11} /> {book.title}</Badge> : null}
              </div>
              <h2 className="mt-2 font-display text-xl font-semibold text-white">
                {book ? `Приключения по книге «${book.title}»` : "Приключения по темам курса"}
              </h2>
              <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-mist-500">
                Каждый квест собирается из заданий темы автоматически. Ответы проверяет сервер,
                а опыт и монеты сразу попадают в профиль.
              </p>
            </div>
          </div>
          <div className="flex gap-3">
            <div className="rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3 text-center">
              <p className="font-display text-2xl font-semibold text-white">{done}/{quests.length}</p>
              <p className="text-[10px] font-bold uppercase tracking-wider text-mist-500">пройдено</p>
            </div>
            <div className="rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3 text-center">
              <p className="font-display text-2xl font-semibold text-white">{quests.length * 5}</p>
              <p className="text-[10px] font-bold uppercase tracking-wider text-mist-500">заданий</p>
            </div>
          </div>
        </div>
      </Card>

      {quests.length === 0 ? (
        <Card className="p-8 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-white/5 text-2xl">🗺️</div>
          <h3 className="mt-3 font-display text-lg font-semibold text-white">Квесты ещё собираются</h3>
          <p className="mx-auto mt-1.5 max-w-md text-sm text-mist-500">
            Для этого класса пока нет тем с заданиями. Загрузите пособие или включите темы в курсе — квесты появятся автоматически.
          </p>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {quests.map((quest) => <QuestCard key={quest.slug} quest={quest} />)}
        </div>
      )}
    </div>
  );
}

function QuestCard({ quest }) {
  const pages = quest.page_start
    ? `стр. ${quest.page_start}${quest.page_end && quest.page_end !== quest.page_start ? `–${quest.page_end}` : ""}`
    : "";
  return (
    <Card hover className="group relative flex flex-col overflow-hidden p-5">
      <div className="pointer-events-none absolute -right-12 -top-12 h-32 w-32 rounded-full bg-iris-500/10 blur-2xl transition group-hover:bg-iris-500/20" />
      <div className="relative flex items-start justify-between gap-3">
        <span className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04] text-2xl">
          {quest.icon || "🗺️"}
        </span>
        <div className="flex items-center gap-1">
          {[1, 2, 3].map((star) => (
            <Star
              key={star}
              size={14}
              className={star <= quest.stars ? "fill-amber-300 text-amber-300" : "text-white/15"}
            />
          ))}
        </div>
      </div>
      <h3 className="relative mt-3 font-display text-lg font-semibold text-white">{quest.title}</h3>
      <p className="relative mt-1 line-clamp-2 text-xs leading-relaxed text-mist-500">{quest.description}</p>

      <div className="relative mt-3 flex flex-wrap gap-2 text-[10px] font-bold">
        <span className="inline-flex items-center gap-1 rounded-lg bg-white/[0.04] px-2 py-1 text-mist-400"><Timer size={11} /> {quest.minutes} мин</span>
        <span className="inline-flex items-center gap-1 rounded-lg bg-white/[0.04] px-2 py-1 text-mist-400"><Target size={11} /> 5 станций</span>
        {quest.book ? <span className="inline-flex items-center gap-1 rounded-lg bg-white/[0.04] px-2 py-1 text-mist-400"><BookOpen size={11} /> {pages}</span> : null}
      </div>

      {quest.attempts > 0 && (
        <div className="relative mt-3">
          <div className="mb-1 flex justify-between text-[10px] font-semibold text-mist-500">
            <span>Лучший результат</span>
            <span>{quest.best_correct}/5</span>
          </div>
          <Progress value={(quest.best_correct / 5) * 100} />
        </div>
      )}

      <div className="relative mt-4 flex items-center justify-between gap-2">
        <span className="text-[10px] font-bold uppercase tracking-wider text-mist-600">
          {quest.completed ? "пройден" : quest.active_run_id ? "есть сохранение" : "не начат"}
        </span>
        <Link
          to={`/app/quests/${quest.slug}`}
          className={`btn btn-sm ${quest.completed ? "btn-ghost" : "btn-primary"}`}
        >
          {quest.completed ? <RotateCcw size={14} /> : <Play size={14} />}
          {quest.completed ? "Ещё раз" : quest.active_run_id ? "Продолжить" : "Играть"}
        </Link>
      </div>
    </Card>
  );
}

/* ================================================================== PLAYER */
export function QuestPlayerPage() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { refreshSession } = useSession();
  const sceneRef = useRef(null);

  const [run, setRun] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(null);
  const [paused, setPaused] = useState(false);
  const [result, setResult] = useState(null);
  const [starting, setStarting] = useState(false);
  const closingTimer = useRef(null);
  // В WebView на некоторых устройствах WebGL недоступен. Тогда показываем
  // те же станции списком, чтобы задания всё равно открывались.
  const [webglReady] = useState(() => {
    if (typeof document === "undefined") return false;
    try {
      const canvas = document.createElement("canvas");
      return Boolean(
        canvas.getContext("webgl2") ||
        canvas.getContext("webgl") ||
        canvas.getContext("experimental-webgl"),
      );
    } catch {
      return false;
    }
  });

  const load = useCallback(async ({ restart = false } = {}) => {
    setLoading(true);
    setError(null);
    try {
      const detail = await api.get(`/quests/${slug}`);
      if (!restart && detail.quest?.active_run_id) {
        const saved = await api.get(`/quests/runs/${detail.quest.active_run_id}`);
        setRun(saved);
      } else {
        const next = await api.post(`/quests/${slug}/start`, {});
        setRun(next);
      }
      setResult(null);
      setPaused(false);
      setModal(null);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [slug]);

  const loadedRef = useRef(false);
  useEffect(() => {
    if (!loadedRef.current) {
      loadedRef.current = true;
      load();
    }
    return () => {
      if (closingTimer.current) clearTimeout(closingTimer.current);
    };
  }, [load]);

  const tasks = run?.tasks || [];
  const stations = useMemo(
    () => tasks.map((task, index) => ({ ...task.station, ...(run?.stations?.[index] || {}) })),
    [tasks, run?.stations],
  );
  const answered = stations.filter((station) => station.done).length;
  const total = tasks.length || 5;
  const allDone = total > 0 && answered >= total;

  const openStation = useCallback((index) => {
    if (index == null || index < 0) return;
    const station = run?.stations?.[index];
    if (station?.done) return;
    if (!run?.tasks?.[index]) return;
    setPaused(true);
    setModal(index);
  }, [run]);

  const submitAnswer = async (answer) => {
    if (modal == null || !run) return { ok: false };
    try {
      const response = await api.post(`/quests/runs/${run.run_id}/check`, {
        station: modal,
        answer,
      });
      setRun((current) => {
        if (!current) return current;
        const nextStations = current.stations.map((station, index) =>
          index === modal
            ? {
                ...station,
                done: response.done,
                correct: response.correct,
                attempts: response.attempts,
              }
            : station,
        );
        return {
          ...current,
          stations: nextStations,
          correct: response.correct_total,
          xp: current.xp + (response.xp || 0),
          coins: current.coins + (response.coins || 0),
          finished: nextStations.every((station) => station.done),
        };
      });
      return response;
    } catch (err) {
      toast(err.message || "Не удалось проверить ответ", "error");
      return { ok: false, error: err };
    }
  };

  const closeModal = () => {
    setModal(null);
    setPaused(false);
  };

  const finish = async () => {
    if (!run) return;
    try {
      const response = await api.post(`/quests/runs/${run.run_id}/finish`, {});
      setResult(response);
      setPaused(true);
      invalidate("/quests");
      try {
        await refreshSession();
      } catch {
        /* профиль обновится при следующем входе */
      }
    } catch (err) {
      toast(err.message || "Не удалось завершить квест", "error");
    }
  };

  const nextStation = () => {
    const index = stations.findIndex((station) => !station.done);
    if (index === -1) {
      closeModal();
      finish();
      return;
    }
    closeModal();
    sceneRef.current?.goTo(index);
  };

  const restart = async () => {
    setStarting(true);
    try {
      await load({ restart: true });
    } finally {
      setStarting(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-12 w-64" />
        <Skeleton className="h-[60vh] w-full" />
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="space-y-4">
        <Link to="/app/quests" className="inline-flex items-center gap-1.5 text-sm font-semibold text-mist-500 hover:text-white">
          <ArrowLeft size={15} /> Ко всем квестам
        </Link>
        <ErrorState error={error || { message: "Квест не найден" }} onRetry={() => load()} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link to="/app/quests" className="icon-btn" aria-label="Ко всем квестам">
            <ArrowLeft size={18} />
          </Link>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-mist-500">
              3D-квест · {run.quest.grade} класс
            </p>
            <h1 className="font-display text-xl font-semibold text-white sm:text-2xl">
              {run.quest.icon} {run.quest.title}
            </h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-xl border border-white/8 bg-white/[0.04] px-3 py-1.5 text-xs font-bold text-iris-300">
            <Sparkles size={13} /> {run.xp} XP
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-xl border border-white/8 bg-white/[0.04] px-3 py-1.5 text-xs font-bold text-amber-300">
            <Coins size={13} /> {run.coins}
          </span>
          <Button size="sm" variant="ghost" icon={RotateCcw} onClick={restart} loading={starting}>
            Заново
          </Button>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_300px]">
        <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-[#0a1024]">
          {webglReady ? (
            <QuestSceneBoundary
              fallback={<StationFallback stations={stations} tasks={tasks} onOpen={openStation} />}
            >
              <QuestScene
                sceneApiRef={sceneRef}
                stations={stations}
                paused={paused || Boolean(result)}
                onNear={openStation}
              />
            </QuestSceneBoundary>
          ) : (
            <StationFallback stations={stations} tasks={tasks} onOpen={openStation} />
          )}

          <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between gap-3 p-4">
            <div className="pointer-events-auto rounded-2xl border border-white/10 bg-ink-950/70 px-3.5 py-2.5 backdrop-blur">
              <div className="mb-1.5 flex items-center justify-between gap-4 text-[10px] font-bold uppercase tracking-wider text-mist-400">
                <span>Станции</span>
                <span>{answered}/{total}</span>
              </div>
              <Progress value={(answered / total) * 100} />
            </div>
            <div className="pointer-events-auto hidden rounded-2xl border border-white/10 bg-ink-950/70 px-3.5 py-2 text-[11px] font-semibold text-mist-300 backdrop-blur sm:block">
              WASD / стрелки · или джойстик
            </div>
          </div>

          <div className="absolute inset-x-0 bottom-4 flex justify-center px-4">
            <div className="flex max-w-full gap-1.5 overflow-x-auto rounded-2xl border border-white/10 bg-ink-950/70 p-1.5 backdrop-blur">
              {stations.map((station, index) => (
                <button
                  key={station.key || index}
                  type="button"
                  onClick={() => openStation(index)}
                  disabled={station.done}
                  className={`flex shrink-0 items-center gap-1.5 rounded-xl px-2.5 py-2 text-[10px] font-bold transition ${
                    station.done
                      ? "bg-emerald-400/10 text-emerald-300"
                      : "text-mist-300 hover:bg-white/10 hover:text-white"
                  }`}
                  title={station.title}
                >
                  <span className="text-sm">{station.done ? "✓" : station.icon}</span>
                  <span className="hidden sm:inline">{station.title}</span>
                </button>
              ))}
            </div>
          </div>

          {allDone && !result && (
            <div className="absolute inset-0 flex items-center justify-center bg-ink-950/55 p-5 backdrop-blur-sm">
              <Card className="w-full max-w-sm p-6 text-center">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-400/15 text-3xl">🏁</div>
                <h2 className="mt-3 font-display text-xl font-semibold text-white">Все станции пройдены!</h2>
                <p className="mt-1 text-sm text-mist-400">Заберите награду за приключение.</p>
                <Button className="mt-4 w-full" icon={Trophy} onClick={finish}>Получить награду</Button>
              </Card>
            </div>
          )}
        </div>

        <div className="space-y-3">
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-mist-500">Карта квеста</p>
              <Badge tone={allDone ? "green" : "iris"}>{allDone ? "финиш" : `этап ${Math.min(answered + 1, total)}`}</Badge>
            </div>
            <div className="mt-3 space-y-2">
              {stations.map((station, index) => (
                <button
                  key={station.key || index}
                  type="button"
                  onClick={() => openStation(index)}
                  disabled={station.done || Boolean(result)}
                  className={`flex w-full items-center gap-3 rounded-2xl border px-3 py-2.5 text-left transition ${
                    station.done
                      ? "border-emerald-400/20 bg-emerald-400/[0.06]"
                      : "border-white/8 bg-white/[0.02] hover:border-iris-400/30 hover:bg-white/[0.05]"
                  }`}
                >
                  <span
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-base"
                    style={{ background: station.done ? "rgba(52,211,153,.16)" : `${station.color}22` }}
                  >
                    {station.done ? (station.correct ? "✓" : "•") : station.icon}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-bold text-white">{station.title}</p>
                    <p className="truncate text-[10px] text-mist-500">
                      {station.done
                        ? (station.correct ? "пройдена" : "засчитана")
                        : (tasks[index]?.question || station.prompt)}
                    </p>
                  </div>
                  {station.done ? (
                    station.correct ? <CheckCircle2 size={15} className="text-emerald-300" /> : <X size={15} className="text-mist-500" />
                  ) : (
                    <MapPin size={14} className="text-mist-600" />
                  )}
                </button>
              ))}
            </div>
          </Card>

          <Card className="p-4">
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-mist-500">Подсказка</p>
            <p className="mt-2 text-xs leading-relaxed text-mist-400">
              Подойдите к станции или нажмите на неё на карте — задание откроется сразу.
              На ответ даётся две попытки.
            </p>
            {run.quest.page_start ? (
              <Link to={`/app/learn/${run.quest.slug}`} className="mt-3 inline-flex items-center gap-1.5 text-[11px] font-bold text-iris-300 hover:text-white">
                <BookOpen size={13} /> Повторить тему · стр. {run.quest.page_start}
              </Link>
            ) : null}
          </Card>
        </div>
      </div>

      {modal != null && createPortal(
        <TaskModal
          task={tasks[modal]}
          index={modal}
          total={total}
          onClose={() => {
            if (stations[modal]?.done) nextStation();
            else closeModal();
          }}
          onSubmit={submitAnswer}
          onNext={nextStation}
        />,
        document.body,
      )}

      {result && createPortal(
        <ResultOverlay
          result={result}
          onRestart={restart}
          restarting={starting}
          onExit={() => navigate("/app/quests")}
        />,
        document.body,
      )}
    </div>
  );
}

/* =================================================================== TASK */
function TaskModal({ task, index, total, onClose, onSubmit, onNext }) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState(null);
  if (!task) return null;
  const station = task.station || {};
  const choices = task.choices || [];

  const send = async (answer) => {
    if (busy) return;
    const clean = String(answer ?? "").trim();
    if (!clean) return;
    setBusy(true);
    const response = await onSubmit(clean);
    setBusy(false);
    if (response?.ok === false) return;
    setFeedback(response);
    if (response.correct) setValue("");
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink-950/70 p-3 backdrop-blur-sm sm:items-center sm:p-6">
      <div
        className="relative w-full max-w-lg overflow-hidden rounded-3xl border border-white/12 bg-ink-900 shadow-2xl"
        style={{ background: "linear-gradient(160deg, rgba(28,34,64,.98), rgba(13,17,34,.99))" }}
      >
        <div className="h-1 w-full" style={{ background: station.color || "#8b5cf6" }} />
        <div className="flex items-start justify-between gap-3 p-5 pb-0">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl text-xl" style={{ background: `${station.color || "#8b5cf6"}22` }}>
              {station.icon}
            </span>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-mist-500">
                Станция {index + 1} из {total}
              </p>
              <h2 className="font-display text-lg font-semibold text-white">{station.title}</h2>
            </div>
          </div>
          <button onClick={onClose} className="icon-btn" aria-label="Закрыть">
            <X size={18} />
          </button>
        </div>

        <div className="max-h-[70vh] overflow-y-auto p-5">
          <p className="text-[15px] font-semibold leading-relaxed text-white">{task.question}</p>

          {!feedback?.done && (
            <>
              {choices.length > 0 ? (
                <div className="mt-4 grid gap-2">
                  {choices.map((choice) => (
                    <button
                      key={choice}
                      type="button"
                      disabled={busy}
                      onClick={() => send(choice)}
                      className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-left text-sm font-semibold text-mist-200 transition hover:border-iris-400/40 hover:bg-iris-500/10 hover:text-white disabled:opacity-60"
                    >
                      {choice}
                    </button>
                  ))}
                </div>
              ) : (
                <form
                  className="mt-4 flex gap-2"
                  onSubmit={(event) => {
                    event.preventDefault();
                    send(value);
                  }}
                >
                  <input
                    autoFocus
                    value={value}
                    onChange={(event) => setValue(event.target.value)}
                    inputMode={task.answer_type === "number" ? "decimal" : "text"}
                    placeholder={task.answer_type === "time" ? "например, 9:45" : "Введи ответ"}
                    className="input flex-1"
                    disabled={busy}
                  />
                  <Button type="submit" loading={busy} disabled={!value.trim()}>Ответить</Button>
                </form>
              )}
            </>
          )}

          {feedback && (
            <div className="mt-4 space-y-3">
              {feedback.correct ? (
                <div className="rounded-2xl border border-emerald-400/25 bg-emerald-400/[0.08] p-4">
                  <div className="flex items-center gap-2 text-sm font-bold text-emerald-300">
                    <CheckCircle2 size={17} /> Верно!
                  </div>
                  <p className="mt-1 text-xs text-emerald-200/80">
                    +{feedback.xp} XP и +{feedback.coins} монет. Станция зажглась.
                  </p>
                </div>
              ) : feedback.done ? (
                <div className="rounded-2xl border border-amber-400/25 bg-amber-400/[0.08] p-4">
                  <div className="flex items-center gap-2 text-sm font-bold text-amber-300">
                    <Lightbulb size={17} /> Правильный ответ: {feedback.expected}
                  </div>
                  <p className="mt-1 text-xs text-amber-100/70">
                    Станция засчитана. Разберите решение в теме и попробуйте квест ещё раз.
                  </p>
                </div>
              ) : (
                <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <div className="flex items-center gap-2 text-sm font-bold text-amber-300">
                    <Lightbulb size={17} /> Пока не то
                  </div>
                  {feedback.hint ? <p className="mt-1 text-xs leading-relaxed text-mist-300">{feedback.hint}</p> : null}
                  <p className="mt-1 text-[11px] text-mist-500">Осталась ещё {feedback.attempts_left} попытка.</p>
                </div>
              )}

              <div className="flex justify-end gap-2">
                {feedback.correct || feedback.done ? (
                  <Button onClick={onNext} icon={ArrowRight}>
                    {feedback.all_done ? "К награде" : "Дальше"}
                  </Button>
                ) : (
                  <Button variant="ghost" onClick={() => setFeedback(null)}>
                    Попробовать снова
                  </Button>
                )}
              </div>
            </div>
          )}

          {!feedback && task.hint && choices.length === 0 ? (
            <p className="mt-3 flex items-start gap-1.5 text-[11px] text-mist-500">
              <Lightbulb size={12} className="mt-0.5 shrink-0 text-amber-300" /> {task.hint}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

/* ================================================================= RESULT */
function ResultOverlay({ result, onRestart, onExit, restarting }) {
  const stars = result.stars || 0;
  const seconds = Math.max(1, Math.round((result.elapsed_ms || 0) / 1000));
  const minutes = Math.floor(seconds / 60);
  const time = minutes ? `${minutes} мин ${seconds % 60} с` : `${seconds} с`;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/80 p-4 backdrop-blur">
      <div
        className="w-full max-w-md overflow-hidden rounded-3xl border border-white/12 shadow-2xl"
        style={{ background: "linear-gradient(165deg, rgba(34,25,64,.99), rgba(10,14,28,.99))" }}
      >
        <div className="relative p-6 text-center">
          <div className="pointer-events-none absolute inset-x-0 -top-20 mx-auto h-48 w-48 rounded-full bg-iris-500/25 blur-3xl" />
          <div className="relative mx-auto flex h-16 w-16 items-center justify-center rounded-3xl border border-white/12 bg-white/[0.06] text-3xl">
            🏆
          </div>
          <h2 className="relative mt-3 font-display text-2xl font-semibold text-white">Квест пройден!</h2>
          <p className="relative mt-1 text-sm text-mist-400">
            {result.quest?.icon} {result.quest?.title}
          </p>

          <div className="relative mt-4 flex items-center justify-center gap-2">
            {[1, 2, 3].map((star) => (
              <Star
                key={star}
                size={38}
                className={star <= stars ? "fill-amber-300 text-amber-300 drop-shadow-[0_0_12px_rgba(252,211,77,.55)]" : "text-white/10"}
              />
            ))}
          </div>

          <div className="relative mt-5 grid grid-cols-3 gap-2 text-center">
            <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-3">
              <p className="font-display text-lg font-semibold text-white">{result.correct}/{result.total}</p>
              <p className="text-[9px] font-bold uppercase tracking-wider text-mist-500">верно</p>
            </div>
            <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-3">
              <p className="font-display text-lg font-semibold text-iris-300">+{result.xp + (result.bonus_xp || 0)}</p>
              <p className="text-[9px] font-bold uppercase tracking-wider text-mist-500">XP</p>
            </div>
            <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-3">
              <p className="font-display text-lg font-semibold text-amber-300">+{result.coins + (result.bonus_coins || 0)}</p>
              <p className="text-[9px] font-bold uppercase tracking-wider text-mist-500">монет</p>
            </div>
          </div>

          <p className="relative mt-3 inline-flex items-center gap-1.5 text-[11px] text-mist-500">
            <Timer size={12} /> Время в квесте: {time}
            {result.first_time ? <span className="ml-1 rounded-md bg-emerald-400/10 px-1.5 py-0.5 font-bold text-emerald-300">бонус за первое прохождение</span> : null}
          </p>

          <div className="relative mt-5 flex gap-2">
            <Button variant="ghost" className="flex-1" icon={Gamepad2} onClick={onExit}>К квестам</Button>
            <Button className="flex-1" icon={RotateCcw} loading={restarting} onClick={onRestart}>Ещё раз</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ================================================================== SCENE */
const THEMES = {
  gate: "#a78bfa",
  bridge: "#22d3ee",
  forest: "#34d399",
  tower: "#fbbf24",
  crystal: "#f472b6",
};

function makeLabelSprite(text, color) {
  const size = 256;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, size, size);
  context.beginPath();
  context.arc(size / 2, size / 2, size * 0.36, 0, Math.PI * 2);
  context.fillStyle = "rgba(8,12,28,.82)";
  context.fill();
  context.lineWidth = 10;
  context.strokeStyle = color;
  context.stroke();
  context.font = `${size * 0.36}px "Segoe UI Emoji", "Apple Color Emoji", sans-serif`;
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillText(text, size / 2, size / 2 + 6);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(1.25, 1.25, 1);
  return sprite;
}

function buildStation(theme, index) {
  const color = THEMES[theme] || "#a78bfa";
  const group = new THREE.Group();
  const base = new THREE.Mesh(
    new THREE.CylinderGeometry(2.05, 2.25, 0.38, 32),
    new THREE.MeshStandardMaterial({ color: 0x1b2547, roughness: 0.75, metalness: 0.25 }),
  );
  base.position.y = 0.19;
  base.receiveShadow = true;
  group.add(base);

  const ringMaterial = new THREE.MeshStandardMaterial({
    color,
    emissive: color,
    emissiveIntensity: 0.85,
    roughness: 0.4,
  });
  const ring = new THREE.Mesh(new THREE.TorusGeometry(1.82, 0.055, 8, 48), ringMaterial);
  ring.rotation.x = -Math.PI / 2;
  ring.position.y = 0.4;
  group.add(ring);

  const inner = new THREE.Mesh(
    new THREE.CircleGeometry(1.6, 32),
    new THREE.MeshStandardMaterial({ color, transparent: true, opacity: 0.09, emissive: color, emissiveIntensity: 0.35 }),
  );
  inner.rotation.x = -Math.PI / 2;
  inner.position.y = 0.39;
  group.add(inner);

  const pedestalMaterial = new THREE.MeshStandardMaterial({ color: 0x27324f, roughness: 0.6, metalness: 0.35 });
  const ornament = new THREE.Group();
  ornament.position.y = 0.5;
  group.add(ornament);

  if (theme === "gate") {
    for (const x of [-1.05, 1.05]) {
      const pillar = new THREE.Mesh(new THREE.BoxGeometry(0.42, 3.1, 0.42), pedestalMaterial);
      pillar.position.set(x, 1.55, 0);
      pillar.castShadow = true;
      ornament.add(pillar);
      const cap = new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.22, 0.62), ringMaterial);
      cap.position.set(x, 3.16, 0);
      ornament.add(cap);
    }
    const top = new THREE.Mesh(new THREE.BoxGeometry(2.55, 0.32, 0.5), pedestalMaterial);
    top.position.y = 3.28;
    ornament.add(top);
    const rune = new THREE.Mesh(new THREE.OctahedronGeometry(0.36), ringMaterial);
    rune.position.y = 2.45;
    rune.userData.spin = true;
    ornament.add(rune);
  } else if (theme === "bridge") {
    const arch = new THREE.Mesh(
      new THREE.TorusGeometry(1.5, 0.14, 10, 26, Math.PI),
      pedestalMaterial,
    );
    arch.position.y = 0.5;
    arch.castShadow = true;
    ornament.add(arch);
    for (let n = 0; n < 5; n += 1) {
      const plank = new THREE.Mesh(
        new THREE.BoxGeometry(0.38, 0.12, 1.25),
        new THREE.MeshStandardMaterial({ color: 0x8b5a2b, roughness: 0.9 }),
      );
      const angle = Math.PI * (n + 0.5) / 5;
      plank.position.set(Math.cos(angle) * 1.5, 0.5 + Math.sin(angle) * 1.5, 0);
      plank.rotation.z = angle - Math.PI / 2;
      ornament.add(plank);
    }
    const beacon = new THREE.Mesh(new THREE.SphereGeometry(0.28, 16, 16), ringMaterial);
    beacon.position.y = 2.5;
    ornament.add(beacon);
  } else if (theme === "forest") {
    for (const [x, z, h] of [[-0.85, 0.2, 1.5], [0.75, 0.45, 1.2], [0.25, -0.7, 1.9]]) {
      const trunk = new THREE.Mesh(
        new THREE.CylinderGeometry(0.11, 0.16, 0.7, 7),
        new THREE.MeshStandardMaterial({ color: 0x6b4423, roughness: 1 }),
      );
      trunk.position.set(x, 0.85, z);
      trunk.castShadow = true;
      ornament.add(trunk);
      const crown = new THREE.Mesh(
        new THREE.ConeGeometry(0.62, h, 8),
        new THREE.MeshStandardMaterial({ color: 0x2f8f66, roughness: 0.85, emissive: 0x0b3b2a, emissiveIntensity: 0.5 }),
      );
      crown.position.set(x, 1.2 + h / 2, z);
      crown.castShadow = true;
      ornament.add(crown);
    }
    const firefly = new THREE.Mesh(new THREE.IcosahedronGeometry(0.18, 0), ringMaterial);
    firefly.position.set(0, 2.4, 0);
    firefly.userData.spin = true;
    ornament.add(firefly);
  } else if (theme === "tower") {
    let level = 0;
    for (const [radius, height] of [[1.0, 0.9], [0.78, 0.85], [0.55, 0.8]]) {
      const block = new THREE.Mesh(
        new THREE.CylinderGeometry(radius * 0.86, radius, height, 10),
        pedestalMaterial,
      );
      block.position.y = 0.5 + level + height / 2;
      block.castShadow = true;
      ornament.add(block);
      level += height;
    }
    const crystal = new THREE.Mesh(new THREE.ConeGeometry(0.3, 0.7, 6), ringMaterial);
    crystal.position.y = level + 0.85;
    crystal.userData.spin = true;
    ornament.add(crystal);
  } else {
    const crystal = new THREE.Mesh(new THREE.OctahedronGeometry(0.95, 0), ringMaterial);
    crystal.position.y = 1.7;
    crystal.castShadow = true;
    crystal.userData.spin = true;
    ornament.add(crystal);
    for (let n = 0; n < 4; n += 1) {
      const shard = new THREE.Mesh(new THREE.ConeGeometry(0.18, 0.7, 5), ringMaterial);
      const angle = (Math.PI * 2 * n) / 4;
      shard.position.set(Math.cos(angle) * 1.25, 0.85, Math.sin(angle) * 1.25);
      shard.rotation.z = Math.cos(angle) * 0.35;
      shard.rotation.x = Math.sin(angle) * 0.35;
      ornament.add(shard);
    }
  }

  const label = makeLabelSprite(String(index + 1), color);
  label.position.y = 4.4;
  group.add(label);

  const light = new THREE.PointLight(color, 8, 9, 2);
  light.position.y = 2.2;
  group.add(light);

  return { group, ring, ringMaterial, inner, light, label, ornament, baseColor: new THREE.Color(color) };
}

function StationFallback({ stations, tasks, onOpen }) {
  return (
    <div className="flex h-[62vh] min-h-[430px] w-full flex-col gap-2 overflow-y-auto bg-[#0a1024] p-4">
      <p className="mb-1 text-xs leading-relaxed text-mist-400">
        3D-сцена недоступна на этом устройстве. Откройте задание станции:
      </p>
      {stations.map((station, index) => (
        <button
          key={station.key || index}
          type="button"
          disabled={station.done}
          onClick={() => onOpen(index)}
          className={`flex items-center gap-3 rounded-2xl border px-3 py-3 text-left transition ${
            station.done
              ? "border-emerald-400/20 bg-emerald-400/[0.06]"
              : "border-white/10 bg-white/[0.03] hover:border-iris-400/40 hover:bg-iris-500/10"
          }`}
        >
          <span
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-base"
            style={{ background: `${station.color || "#8b5cf6"}22` }}
          >
            {station.done ? (station.correct ? "✓" : "•") : station.icon}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-bold text-white">{station.title}</p>
            <p className="line-clamp-2 text-[11px] leading-snug text-mist-400">
              {station.done
                ? (station.correct ? "Пройдена" : "Засчитана")
                : (tasks[index]?.question || station.prompt)}
            </p>
          </div>
          {!station.done ? (
            <span className="shrink-0 text-[10px] font-bold text-iris-300">Открыть</span>
          ) : null}
        </button>
      ))}
    </div>
  );
}

class QuestSceneBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error) {
    console.error("3D-сцена квеста недоступна", error);
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

function QuestScene({ stations, paused, onNear, sceneApiRef }) {
  const hostRef = useRef(null);
  const propsRef = useRef({ stations, paused, onNear });
  propsRef.current = { stations, paused, onNear };
  const joystickRef = useRef({ x: 0, y: 0, active: false });

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a1024);
    scene.fog = new THREE.Fog(0x0a1024, 30, 58);

    const camera = new THREE.PerspectiveCamera(52, 1, 0.1, 200);
    const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    renderer.domElement.style.display = "block";
    host.appendChild(renderer.domElement);

    scene.add(new THREE.HemisphereLight(0x9bb4ff, 0x160f2b, 1.35));
    const sun = new THREE.DirectionalLight(0xfff4e6, 2.1);
    sun.position.set(12, 22, 10);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    sun.shadow.camera.left = -22;
    sun.shadow.camera.right = 22;
    sun.shadow.camera.top = 22;
    sun.shadow.camera.bottom = -22;
    scene.add(sun);

    const ground = new THREE.Mesh(
      new THREE.CircleGeometry(26, 72),
      new THREE.MeshStandardMaterial({ color: 0x122446, roughness: 0.95, metalness: 0.05 }),
    );
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);

    const outer = new THREE.Mesh(
      new THREE.RingGeometry(10.1, 10.75, 96),
      new THREE.MeshStandardMaterial({ color: 0x2a3a63, emissive: 0x22335c, emissiveIntensity: 0.55, roughness: 0.8 }),
    );
    outer.rotation.x = -Math.PI / 2;
    outer.position.y = 0.015;
    scene.add(outer);

    const spokes = new THREE.Group();
    for (let n = 0; n < 5; n += 1) {
      const angle = -Math.PI / 2 + (Math.PI * 2 * n) / 5;
      const spoke = new THREE.Mesh(
        new THREE.PlaneGeometry(0.18, 9.7),
        new THREE.MeshBasicMaterial({ color: 0x1d2b50, transparent: true, opacity: 0.75 }),
      );
      spoke.rotation.x = -Math.PI / 2;
      spoke.rotation.z = -angle + Math.PI / 2;
      spoke.position.set(Math.cos(angle) * 5.1, 0.02, Math.sin(angle) * 5.1);
      spokes.add(spoke);
    }
    scene.add(spokes);

    // Декоративные камни и кристаллы вокруг арены.
    const rockMaterial = new THREE.MeshStandardMaterial({ color: 0x1b2a4d, roughness: 0.95 });
    const rockGeometry = new THREE.DodecahedronGeometry(0.55, 0);
    const rocks = new THREE.InstancedMesh(rockGeometry, rockMaterial, 34);
    const dummy = new THREE.Object3D();
    for (let n = 0; n < 34; n += 1) {
      const angle = (n / 34) * Math.PI * 2 + n * 0.37;
      const radius = 13 + (n % 5) * 0.8;
      const scale = 0.5 + (n % 4) * 0.28;
      dummy.position.set(Math.cos(angle) * radius, scale * 0.35, Math.sin(angle) * radius);
      dummy.rotation.set(n * 0.7, n * 1.3, n * 0.4);
      dummy.scale.set(scale, scale * 0.75, scale);
      dummy.updateMatrix();
      rocks.setMatrixAt(n, dummy.matrix);
    }
    rocks.castShadow = true;
    scene.add(rocks);

    const particleCount = 220;
    const particlePositions = new Float32Array(particleCount * 3);
    for (let n = 0; n < particleCount; n += 1) {
      const radius = 6 + Math.random() * 18;
      const angle = Math.random() * Math.PI * 2;
      particlePositions[n * 3] = Math.cos(angle) * radius;
      particlePositions[n * 3 + 1] = 1 + Math.random() * 12;
      particlePositions[n * 3 + 2] = Math.sin(angle) * radius;
    }
    const particleGeometry = new THREE.BufferGeometry();
    particleGeometry.setAttribute("position", new THREE.BufferAttribute(particlePositions, 3));
    const particles = new THREE.Points(
      particleGeometry,
      new THREE.PointsMaterial({ color: 0x8fb6ff, size: 0.09, transparent: true, opacity: 0.7, depthWrite: false }),
    );
    scene.add(particles);

    const player = new THREE.Group();
    const bodyMaterial = new THREE.MeshStandardMaterial({ color: 0x7c5cff, roughness: 0.45, metalness: 0.25 });
    const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.38, 0.66, 6, 14), bodyMaterial);
    body.position.y = 0.95;
    body.castShadow = true;
    player.add(body);
    const head = new THREE.Mesh(
      new THREE.SphereGeometry(0.36, 18, 18),
      new THREE.MeshStandardMaterial({ color: 0xe7ecff, roughness: 0.35 }),
    );
    head.position.y = 1.72;
    head.castShadow = true;
    player.add(head);
    const visor = new THREE.Mesh(
      new THREE.BoxGeometry(0.42, 0.13, 0.1),
      new THREE.MeshStandardMaterial({ color: 0x39e6ff, emissive: 0x39e6ff, emissiveIntensity: 1.8 }),
    );
    visor.position.set(0, 1.74, -0.31);
    player.add(visor);
    const backpack = new THREE.Mesh(
      new THREE.BoxGeometry(0.5, 0.55, 0.26),
      new THREE.MeshStandardMaterial({ color: 0x3b2b8f, roughness: 0.6 }),
    );
    backpack.position.set(0, 1.08, 0.36);
    player.add(backpack);
    const halo = new THREE.Mesh(
      new THREE.TorusGeometry(0.55, 0.035, 6, 30),
      new THREE.MeshBasicMaterial({ color: 0x9f8bff, transparent: true, opacity: 0.7 }),
    );
    halo.rotation.x = -Math.PI / 2;
    halo.position.y = 0.08;
    player.add(halo);
    player.position.set(0, 0, 0);
    scene.add(player);

    const built = stations.map((station, index) => {
      const angle = -Math.PI / 2 + (Math.PI * 2 * index) / 5;
      const radius = 10.4;
      const item = buildStation(station.theme || ["gate", "bridge", "forest", "tower", "crystal"][index] || "gate", index);
      item.group.position.set(Math.cos(angle) * radius, 0, Math.sin(angle) * radius);
      item.group.rotation.y = -angle + Math.PI / 2;
      item.baseY = item.group.position.y;
      item.phase = index * 1.2;
      item.done = Boolean(station.done);
      scene.add(item.group);
      return item;
    });

    const target = { index: null };
    const keys = new Set();
    const near = { index: null };

    const onKeyDown = (event) => {
      if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space"].includes(event.code)) {
        event.preventDefault();
      }
      keys.add(event.code);
    };
    const onKeyUp = (event) => keys.delete(event.code);
    window.addEventListener("keydown", onKeyDown, { passive: false });
    window.addEventListener("keyup", onKeyUp);

    // Джойстик: pointer на левой нижней зоне.
    const joystick = host.querySelector("[data-quest-joystick]");
    const knob = host.querySelector("[data-quest-knob]");
    let pointerId = null;
    const updateJoystick = (event) => {
      const rect = joystick.getBoundingClientRect();
      const radius = rect.width / 2;
      let dx = (event.clientX - (rect.left + radius)) / radius;
      let dy = (event.clientY - (rect.top + radius)) / radius;
      const length = Math.hypot(dx, dy);
      if (length > 1) {
        dx /= length;
        dy /= length;
      }
      joystickRef.current = { x: dx, y: dy, active: true };
      if (knob) knob.style.transform = `translate(${dx * radius * 0.55}px, ${dy * radius * 0.55}px)`;
    };
    const onJoystickDown = (event) => {
      pointerId = event.pointerId;
      joystick.setPointerCapture(pointerId);
      updateJoystick(event);
    };
    const onJoystickMove = (event) => {
      if (pointerId === event.pointerId) updateJoystick(event);
    };
    const onJoystickUp = (event) => {
      if (pointerId !== event.pointerId) return;
      pointerId = null;
      joystickRef.current = { x: 0, y: 0, active: false };
      if (knob) knob.style.transform = "translate(0px, 0px)";
    };
    if (joystick) {
      joystick.addEventListener("pointerdown", onJoystickDown);
      joystick.addEventListener("pointermove", onJoystickMove);
      joystick.addEventListener("pointerup", onJoystickUp);
      joystick.addEventListener("pointercancel", onJoystickUp);
    }

    const resize = () => {
      const width = host.clientWidth || 1;
      const height = host.clientHeight || 1;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(host);
    resize();

    const goTo = (index) => {
      target.index = index;
      near.index = null;
    };
    if (sceneApiRef) sceneApiRef.current = { goTo };

    const clock = new THREE.Clock();
    const velocity = new THREE.Vector3();
    let frame = 0;

    const tick = () => {
      frame = requestAnimationFrame(tick);
      const delta = Math.min(clock.getDelta(), 0.05);
      const time = clock.elapsedTime;
      const state = propsRef.current;
      const isPaused = state.paused;

      // Визуальное состояние станций.
      built.forEach((item, index) => {
        const info = state.stations?.[index];
        const done = Boolean(info?.done);
        const correct = Boolean(info?.correct);
        if (item.done !== done || item.correct !== correct) {
          item.done = done;
          item.correct = correct;
          const color = done ? (correct ? "#34d399" : "#94a3b8") : item.baseColor.getStyle();
          item.ringMaterial.color.set(color);
          item.ringMaterial.emissive.set(color);
          item.ringMaterial.emissiveIntensity = done ? 0.55 : 0.9;
          item.light.color.set(color);
          item.light.intensity = done ? 2.5 : 8;
          item.inner.material.color.set(color);
          item.inner.material.opacity = done ? 0.05 : 0.09;
          if (done) item.group.rotation.y += 0.0001;
        }
        item.ornament.position.y = 0.5 + Math.sin(time * 1.5 + item.phase) * 0.09;
        item.label.position.y = 4.4 + Math.sin(time * 1.8 + item.phase) * 0.12;
        item.ornament.traverse((child) => {
          if (child.userData?.spin) {
            child.rotation.y += delta * 0.9;
            child.rotation.x += delta * 0.35;
          }
        });
      });
      particles.rotation.y += delta * 0.012;

      if (!isPaused) {
        let inputX = 0;
        let inputZ = 0;
        if (keys.has("KeyA") || keys.has("ArrowLeft")) inputX -= 1;
        if (keys.has("KeyD") || keys.has("ArrowRight")) inputX += 1;
        if (keys.has("KeyW") || keys.has("ArrowUp")) inputZ -= 1;
        if (keys.has("KeyS") || keys.has("ArrowDown")) inputZ += 1;

        const stick = joystickRef.current;
        if (stick.active) {
          inputX = stick.x;
          inputZ = stick.y;
        }

        if (inputX || inputZ) target.index = null;

        velocity.set(inputX, 0, inputZ);
        const inputLength = velocity.length();
        if (inputLength > 1) velocity.normalize();

        if (target.index != null) {
          const goal = built[target.index]?.group.position;
          if (goal) {
            velocity.set(goal.x - player.position.x, 0, goal.z - player.position.z);
            const distance = velocity.length();
            if (distance < 2.5) {
              target.index = null;
              velocity.set(0, 0, 0);
            } else {
              velocity.normalize().multiplyScalar(1);
            }
          }
        }

        if (velocity.lengthSq() > 0.0001) {
          const speed = target.index != null ? 6.2 : 5.4;
          player.position.addScaledVector(velocity, speed * delta * Math.min(1, inputLength || 1));
          const limit = 23.5;
          const distanceFromCenter = Math.hypot(player.position.x, player.position.z);
          if (distanceFromCenter > limit) {
            player.position.x *= limit / distanceFromCenter;
            player.position.z *= limit / distanceFromCenter;
          }
          player.rotation.y = Math.atan2(velocity.x, velocity.z);
          player.position.y = Math.abs(Math.sin(time * 8)) * 0.055;
        }

        // Автозапуск задания рядом со станцией. Пока герой идёт к выбранной
        // станции, соседние не перехватывают управление.
        if (target.index == null) {
          let nearIndex = null;
          built.forEach((item, index) => {
            if (item.done) return;
            const distance = Math.hypot(
              item.group.position.x - player.position.x,
              item.group.position.z - player.position.z,
            );
            if (distance < 2.75) nearIndex = index;
          });
          if (nearIndex !== near.index) {
            near.index = nearIndex;
            if (nearIndex != null) state.onNear?.(nearIndex);
          }
        }
      }

      const desiredCamera = new THREE.Vector3(
        player.position.x,
        player.position.y + 7.4,
        player.position.z + 9.2,
      );
      camera.position.lerp(desiredCamera, 1 - Math.pow(0.001, delta));
      camera.lookAt(player.position.x, player.position.y + 1.25, player.position.z);

      halo.rotation.z += delta;
      renderer.render(scene, camera);
    };
    tick();

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      if (joystick) {
        joystick.removeEventListener("pointerdown", onJoystickDown);
        joystick.removeEventListener("pointermove", onJoystickMove);
        joystick.removeEventListener("pointerup", onJoystickUp);
        joystick.removeEventListener("pointercancel", onJoystickUp);
      }
      scene.traverse((object) => {
        if (object.geometry) object.geometry.dispose();
        if (object.material) {
          const materials = Array.isArray(object.material) ? object.material : [object.material];
          materials.forEach((material) => {
            if (material.map) material.map.dispose();
            material.dispose();
          });
        }
      });
      renderer.dispose();
      if (renderer.domElement.parentNode === host) host.removeChild(renderer.domElement);
      if (sceneApiRef) sceneApiRef.current = null;
    };
    // Сцена создаётся один раз: станции обновляются через propsRef.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div ref={hostRef} className="relative h-[62vh] min-h-[430px] w-full select-none touch-none">
      <div
        data-quest-joystick
        className="absolute bottom-20 left-4 z-10 h-24 w-24 touch-none rounded-full border border-white/15 bg-white/[0.06] backdrop-blur md:hidden"
        aria-hidden="true"
      >
        <div
          data-quest-knob
          className="absolute left-1/2 top-1/2 h-10 w-10 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/25 bg-white/20"
        />
      </div>
    </div>
  );
}

export default QuestsPage;
