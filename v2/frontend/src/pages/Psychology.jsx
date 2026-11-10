import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  Brain,
  CheckCircle2,
  Clock,
  Compass,
  Heart,
  HeartHandshake,
  Lightbulb,
  ListChecks,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Users,
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
} from "../components/ui";
import { useAction, useApi, toast } from "../lib/hooks";
import { api, invalidate } from "../lib/api";
import { formatDate, formatDateTime } from "../lib/format";

const CATEGORY_ORDER = ["abilities", "activities", "problems", "development"];

const KIND = {
  attention: { label: "Обратите внимание", tone: "rose", icon: HeartHandshake },
  growth: { label: "Зона роста", tone: "gold", icon: Lightbulb },
  interest: { label: "Интерес", tone: "cyan", icon: Compass },
  strength: { label: "Сильная сторона", tone: "green", icon: Sparkles },
};

function scaleTone(scale) {
  if (scale.level === "high") return scale.good_high ? "green" : "rose";
  if (scale.level === "mid") return scale.good_high ? "cyan" : "gold";
  return scale.good_high ? "rose" : "green";
}

function KindBadge({ kind }) {
  const meta = KIND[kind] || KIND.attention;
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}

/* ------------------------------------------------------------------ список */
export function PsychologyStudent() {
  const { data, loading, error, refresh } = useApi("/psychology/tests", { ttl: 10_000 });
  const tests = data?.tests || [];
  const history = data?.history || [];
  const grade = data?.grade || 3;
  const band = data?.band || {};

  const grouped = useMemo(() => {
    const map = new Map();
    for (const test of tests) {
      if (!map.has(test.category)) map.set(test.category, []);
      map.get(test.category).push(test);
    }
    return CATEGORY_ORDER.filter((key) => map.has(key)).map((key) => ({
      key,
      title: map.get(key)[0].category_title,
      icon: map.get(key)[0].category_icon,
      items: map.get(key),
    }));
  }, [tests]);

  const done = tests.filter((test) => test.completed).length;
  const last = history[0];

  if (loading && !data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-36 w-full" />
        <div className="grid gap-4 sm:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => <Skeleton key={index} className="h-28" />)}
        </div>
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Школьная психология"
        subtitle={`Тесты для ${band.title || "школы"} · ${grade} класс. Это не экзамен: нет правильных ответов, а результат помогает лучше понять себя.`}
        badge={<Badge tone="iris"><Brain size={12} /> {band.age || "по возрасту"}</Badge>}
      />

      {error && <ErrorState error={error} onRetry={refresh} />}

      <Card className="relative overflow-hidden p-5 sm:p-6">
        <div className="pointer-events-none absolute -right-20 -top-24 h-56 w-56 rounded-full bg-iris-500/15 blur-3xl" />
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="max-w-2xl">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="cyan"><ShieldCheck size={12} /> Конфиденциально</Badge>
              <Badge tone="gold"><Sparkles size={12} /> С ИИ-заключением</Badge>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-mist-300">
              {data?.disclaimer || "Результат — не диагноз. При выраженных трудностях обратитесь к школьному психологу."}
            </p>
            <p className="mt-2 text-[11px] leading-relaxed text-mist-600">{data?.source}</p>
          </div>
          <div className="grid shrink-0 grid-cols-3 gap-2 sm:grid-cols-1">
            {[
              ["Тестов", tests.length],
              ["Пройдено", done],
              ["Осталось", Math.max(0, tests.length - done)],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl border border-white/7 bg-white/[0.025] px-3 py-2 text-center">
                <p className="font-display text-base font-semibold text-white">{value}</p>
                <p className="text-[10px] font-bold uppercase tracking-wider text-mist-600">{label}</p>
              </div>
            ))}
          </div>
        </div>
      </Card>

      {grouped.map((group) => (
        <section key={group.key} className="space-y-3">
          <SectionTitle
            title={`${group.icon} ${group.title}`}
            subtitle={tests.find((test) => test.category === group.key)?.description}
          />
          <div className="grid gap-3 lg:grid-cols-2">
            {group.items.map((test) => (
              <Card key={test.slug} className="flex h-full flex-col p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-display text-base font-semibold text-white">{test.title}</h3>
                      {test.completed && <Badge tone="green"><CheckCircle2 size={11} /> пройден</Badge>}
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-mist-500">{test.subtitle}</p>
                  </div>
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-white/8 bg-white/[0.04] text-xl">
                    {test.category_icon}
                  </span>
                </div>

                {test.completed && test.latest && (
                  <div className="mt-3 rounded-xl border border-emerald-400/15 bg-emerald-500/[0.05] px-3 py-2.5">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-300/80">Последний результат</p>
                    <p className="mt-1 text-xs font-semibold leading-relaxed text-mist-200">{test.latest.headline}</p>
                    <p className="mt-1 text-[10px] text-mist-600">
                      {formatDate(test.latest.created_at)} · {test.attempts} {test.attempts === 1 ? "прохождение" : "прохождений"}
                    </p>
                  </div>
                )}

                <div className="mt-3 flex flex-wrap items-center gap-3 text-[11px] text-mist-600">
                  <span className="inline-flex items-center gap-1"><Clock size={12} /> {test.duration}</span>
                  <span className="inline-flex items-center gap-1"><ListChecks size={12} /> {test.questions} вопросов</span>
                </div>

                <div className="mt-auto flex flex-wrap gap-2 pt-4">
                  <Link to={`/app/psychology/test/${test.slug}`} className="flex-1">
                    <Button className="w-full" icon={test.completed ? RotateCcw : ArrowRight}>
                      {test.completed ? "Пройти снова" : "Начать тест"}
                    </Button>
                  </Link>
                  {test.completed && test.latest && (
                    <Link to={`/app/psychology/result/${test.latest.id}`}>
                      <Button variant="ghost" icon={Sparkles}>Результат</Button>
                    </Link>
                  )}
                </div>
              </Card>
            ))}
          </div>
        </section>
      ))}

      {history.length > 0 && (
        <section className="space-y-3">
          <SectionTitle title="История прохождений" subtitle="Можно вернуться к любому результату и сравнить, что меняется." />
          <Card className="divide-y divide-white/7 p-0">
            {history.map((item) => (
              <Link
                key={item.id}
                to={`/app/psychology/result/${item.id}`}
                className="flex items-center gap-3 px-5 py-3.5 transition hover:bg-white/[0.03]"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/8 bg-white/[0.04] text-base">🧠</span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-white">{item.test_title}</p>
                  <p className="truncate text-[11px] text-mist-500">{item.headline}</p>
                </div>
                <span className="shrink-0 text-[10px] text-mist-600">{formatDate(item.created_at)}</span>
                <ArrowRight size={14} className="shrink-0 text-mist-600" />
              </Link>
            ))}
          </Card>
        </section>
      )}

      {tests.length === 0 && (
        <Card>
          <EmptyState icon="🧠" title="Тесты скоро появятся" text="Для вашего класса набор ещё не сформирован." />
        </Card>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ тест */
export function PsychologyTest() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { data, loading, error, refresh } = useApi(`/psychology/tests/${slug}`);
  const { pending, run } = useAction();
  const [answers, setAnswers] = useState({});
  const [index, setIndex] = useState(0);

  const questions = data?.questions || [];
  const test = data?.test;
  const question = questions[index];
  const answered = Object.keys(answers).length;
  const current = question ? answers[question.id] : undefined;
  const last = index >= questions.length - 1;

  const choose = (optionIndex) => {
    setAnswers((prev) => ({ ...prev, [question.id]: optionIndex }));
  };

  const submit = async () => {
    if (answered < questions.length) {
      toast("Ответьте на все вопросы", "info");
      return;
    }
    try {
      const result = await run(() =>
        api.post(`/psychology/tests/${slug}`, { answers }),
      );
      invalidate("/psychology");
      toast("Результат готов", "success");
      navigate(`/app/psychology/result/${result.result.id}`, { replace: true });
    } catch (err) {
      toast(err.message || "Не удалось сохранить ответы", "error");
    }
  };

  if (loading && !data) {
    return <div className="space-y-4"><Skeleton className="h-24 w-full" /><Skeleton className="h-96 w-full" /></div>;
  }
  if (error) return <ErrorState error={error} onRetry={refresh} />;
  if (!test || !question) return <ErrorState error={new Error("Тест не найден")} />;

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <button
        type="button"
        onClick={() => navigate("/app/psychology")}
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-mist-500 transition hover:text-mist-200"
      >
        <ArrowLeft size={14} /> К тестам
      </button>

      <PageHeader
        title={test.title}
        subtitle={`${test.subtitle} · ${test.duration}`}
        badge={<Badge tone="iris">{test.category_icon} {test.category_title}</Badge>}
      />

      <Card className="p-5">
        <div className="mb-2 flex items-center justify-between text-[11px] font-bold text-mist-500">
          <span>Вопрос {index + 1} из {questions.length}</span>
          <span>Отвечено {answered} из {questions.length}</span>
        </div>
        <Progress value={Math.round(((index + 1) / questions.length) * 100)} />
        <div className="mt-6">
          <h3 className="font-display text-lg font-semibold leading-relaxed text-white">{question.text}</h3>
          <div className="mt-4 space-y-2">
            {question.options.map((option, optionIndex) => {
              const selected = current === optionIndex;
              return (
                <button
                  key={option}
                  type="button"
                  onClick={() => choose(optionIndex)}
                  className={`flex w-full items-center gap-3 rounded-2xl border px-4 py-3.5 text-left text-sm transition ${
                    selected
                      ? "border-iris-400/50 bg-iris-500/15 text-white"
                      : "border-white/8 bg-white/[0.025] text-mist-300 hover:border-white/15 hover:bg-white/[0.05]"
                  }`}
                >
                  <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-[11px] font-bold ${
                    selected ? "border-iris-300/60 bg-iris-400/20 text-iris-100" : "border-white/10 bg-white/5 text-mist-500"
                  }`}>
                    {selected ? <CheckCircle2 size={14} /> : String.fromCharCode(1040 + optionIndex)}
                  </span>
                  {option}
                </button>
              );
            })}
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
          <Button variant="ghost" icon={ArrowLeft} disabled={index === 0} onClick={() => setIndex((value) => Math.max(0, value - 1))}>
            Назад
          </Button>
          {last ? (
            <Button icon={Sparkles} loading={pending} onClick={submit}>
              {pending ? "ИИ готовит заключение…" : "Завершить и получить результат"}
            </Button>
          ) : (
            <Button
              icon={ArrowRight}
              disabled={current === undefined}
              onClick={() => setIndex((value) => Math.min(questions.length - 1, value + 1))}
            >
              Далее
            </Button>
          )}
        </div>
      </Card>

      {data?.latest_result_id && (
        <p className="text-center text-xs text-mist-600">
          Предыдущий результат:{" "}
          <Link to={`/app/psychology/result/${data.latest_result_id}`} className="font-semibold text-iris-300 hover:underline">
            открыть
          </Link>
        </p>
      )}
      <p className="px-2 text-center text-[11px] leading-relaxed text-mist-600">{data?.disclaimer}</p>
    </div>
  );
}

/* ------------------------------------------------------------------ результат */
function AiText({ text }) {
  if (!text) return null;
  const lines = String(text).split(/\r?\n/);
  return (
    <div className="space-y-2 text-sm leading-relaxed text-mist-300">
      {lines.map((line, index) => {
        const clean = line.replace(/\*\*(.+?)\*\*/g, "$1").trim();
        if (!clean) return null;
        if (clean.startsWith("## ")) {
          return <h4 key={index} className="pt-2 font-display text-sm font-bold text-white">{clean.slice(3)}</h4>;
        }
        if (clean.startsWith("- ")) {
          return (
            <p key={index} className="flex gap-2">
              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-iris-300" />
              <span>{clean.slice(2)}</span>
            </p>
          );
        }
        return <p key={index}>{clean}</p>;
      })}
    </div>
  );
}

export function PsychologyResult({ audience = "student" }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const parent = audience === "parent";
  const path = parent ? `/psychology/parent/results/${id}` : `/psychology/results/${id}`;
  const { data, loading, error, refresh } = useApi(path);
  const result = data?.result;
  const back = parent ? "/app/parent/psychology" : "/app/psychology";

  if (loading && !data) {
    return <div className="space-y-4"><Skeleton className="h-32 w-full" /><Skeleton className="h-96 w-full" /></div>;
  }
  if (error) return <ErrorState error={error} onRetry={refresh} />;
  if (!result) return <ErrorState error={new Error("Результат не найден")} />;

  const recommendations = result.recommendations || [];
  const scales = result.scales || [];
  const learner = result.learner;

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <button
        type="button"
        onClick={() => navigate(back)}
        className="inline-flex items-center gap-1.5 text-xs font-semibold text-mist-500 transition hover:text-mist-200"
      >
        <ArrowLeft size={14} /> {parent ? "К результатам детей" : "К тестам"}
      </button>

      <PageHeader
        title={result.test_title}
        subtitle={`${parent && learner ? `${learner.name} · ` : ""}${result.grade} класс · ${formatDateTime(result.created_at)}`}
        badge={<Badge tone="iris">{result.category_icon} {result.category_title}</Badge>}
        actions={
          !parent && (
            <Link to={`/app/psychology/test/${result.test_slug}`}>
              <Button variant="ghost" icon={RotateCcw}>Пройти снова</Button>
            </Link>
          )
        }
      />

      <Card className="relative overflow-hidden p-6">
        <div className="pointer-events-none absolute -right-20 -top-24 h-56 w-56 rounded-full bg-iris-500/20 blur-3xl" />
        <div className="relative">
          <p className="text-[10px] font-bold uppercase tracking-wider text-iris-300">
            {parent ? "Что важно знать родителю" : "Твой результат"}
          </p>
          <h2 className="mt-2 font-display text-xl font-semibold leading-snug text-white sm:text-2xl">{result.headline}</h2>
          <p className="mt-3 max-w-3xl text-sm leading-relaxed text-mist-300">{result.summary}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {recommendations.slice(0, 3).map((item, index) => (
              <Badge key={`${item.scale}-${index}`} tone={(KIND[item.kind] || KIND.attention).tone}>
                {(KIND[item.kind] || KIND.attention).label}
              </Badge>
            ))}
          </div>
        </div>
      </Card>

      <Card className="p-5 sm:p-6">
        <div className="flex items-center gap-2">
          <Sparkles size={18} className="text-iris-300" />
          <h3 className="font-display text-base font-semibold text-white">Заключение ИИ</h3>
          <Badge tone="iris">персонально</Badge>
        </div>
        {result.ai?.text ? (
          <div className="mt-3"><AiText text={result.ai.text} /></div>
        ) : (
          <p className="mt-3 text-sm leading-relaxed text-mist-500">
            ИИ сейчас недоступен, поэтому показано заключение по профессиональным шкалам.
            Оно уже содержит главное: сильные стороны, зоны поддержки и конкретные шаги.
          </p>
        )}
        {result.ai?.text && (
          <p className="mt-3 text-[10px] text-mist-600">
            Сгенерировано ИИ по результатам теста и проверенным психологическим шкалам. Не является диагнозом.
          </p>
        )}
      </Card>

      <section className="space-y-3">
        <SectionTitle title="По шкалам" subtitle="Проценты показывают выраженность качества, а не оценку «хорошо/плохо»." />
        <div className="grid gap-3 sm:grid-cols-2">
          {scales.map((scale) => (
            <Card key={scale.key} className="p-4">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-lg">{scale.icon}</span>
                  <p className="text-sm font-semibold text-white">{scale.label}</p>
                </div>
                <Badge tone={scaleTone(scale)}>{scale.level_label}</Badge>
              </div>
              <div className="mt-3 flex items-center gap-3">
                <Progress value={scale.percent} className="flex-1" />
                <span className="w-10 text-right text-xs font-bold text-mist-300">{scale.percent}%</span>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-mist-500">{scale.text}</p>
              {scale.advice?.length > 0 && (
                <ul className="mt-3 space-y-1.5 border-t border-white/7 pt-3 text-[11px] leading-relaxed text-mist-500">
                  {scale.advice.slice(0, 3).map((item, index) => (
                    <li key={index} className="flex gap-2">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-iris-300/70" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          ))}
        </div>
      </section>

      {recommendations.length > 0 && (
        <section className="space-y-3">
          <SectionTitle
            title={parent ? "Рекомендации для родителей" : "Что можно сделать"}
            subtitle={parent ? "Конкретные шаги, которые можно обсудить с ребёнком." : "Небольшие шаги, которые реально сделать."}
          />
          <div className="space-y-3">
            {recommendations.map((item, index) => {
              const meta = KIND[item.kind] || KIND.attention;
              const Icon = meta.icon;
              return (
                <Card key={`${item.scale}-${index}`} className="p-5">
                  <div className="flex items-start gap-3">
                    <span className={`mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/5 ${
                      meta.tone === "rose" ? "text-rose-300" : meta.tone === "gold" ? "text-amber-300" : meta.tone === "cyan" ? "text-cyan-300" : "text-emerald-300"
                    }`}>
                      <Icon size={18} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="font-display text-sm font-semibold text-white">{item.title}</h3>
                        <Badge tone={meta.tone}>{meta.label}</Badge>
                      </div>
                      <p className="mt-1.5 text-sm leading-relaxed text-mist-400">{item.text}</p>
                      {item.advice?.length > 0 && (
                        <ul className="mt-3 space-y-1.5">
                          {item.advice.map((advice, adviceIndex) => (
                            <li key={adviceIndex} className="flex gap-2 text-xs leading-relaxed text-mist-500">
                              <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-emerald-300/80" />
                              <span>{advice}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        </section>
      )}

      <Card className="border-amber-400/15 bg-amber-500/[0.04] p-5">
        <div className="flex items-start gap-3">
          <ShieldCheck size={18} className="mt-0.5 shrink-0 text-amber-300" />
          <div>
            <p className="text-sm font-semibold text-white">Важно помнить</p>
            <p className="mt-1 text-xs leading-relaxed text-mist-400">{result.disclaimer}</p>
            <p className="mt-2 text-[11px] leading-relaxed text-mist-600">{result.source}</p>
          </div>
        </div>
      </Card>
    </div>
  );
}

/* ------------------------------------------------------------------ родитель */
function ChildTabs({ children, value, onChange }) {
  if (!children?.length) return null;
  return (
    <div className="no-scrollbar flex gap-1 overflow-x-auto rounded-2xl border border-white/8 bg-white/[0.025] p-1">
      {children.map((child) => {
        const active = Number(value) === Number(child.learner.id);
        return (
          <button
            key={child.learner.id}
            type="button"
            onClick={() => onChange(child.learner.id)}
            className={`flex shrink-0 items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold transition ${
              active ? "bg-white/10 text-white" : "text-mist-500 hover:text-mist-100"
            }`}
          >
            <span className="text-base">{child.learner.avatar || "🦊"}</span>
            {child.learner.name || child.user?.first_name || "Ребёнок"}
            <span className="text-[10px] text-mist-600">{child.grade} класс</span>
          </button>
        );
      })}
    </div>
  );
}

export function ParentPsychology() {
  const { data, loading, error, refresh } = useApi("/psychology/parent/overview", { ttl: 10_000 });
  const children = data?.children || [];
  const [selected, setSelected] = useState(null);
  const active = children.find((child) => Number(child.learner.id) === Number(selected)) || children[0];

  if (loading && !data) {
    return <div className="space-y-4"><Skeleton className="h-36 w-full" /><Skeleton className="h-28 w-full" /><Skeleton className="h-96 w-full" /></div>;
  }

  if (!loading && children.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Школьная психология"
          subtitle="Результаты тестов детей и рекомендации для родителей."
          badge={<Badge tone="iris"><Brain size={12} /> по возрасту</Badge>}
        />
        <Card>
          <EmptyState
            icon="🧠"
            title="Пока нет результатов"
            text="Когда ребёнок пройдёт тесты в своём кабинете, здесь появятся результаты, сильные стороны и рекомендации. Ребёнка можно привязать в разделе «Обзор семьи»."
            action={<Link to="/app/parent"><Button icon={Users}>К детям</Button></Link>}
          />
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Школьная психология"
        subtitle="Результаты тестов детей, сильные стороны и конкретные рекомендации. Уведомления приходят после каждого теста."
        badge={<Badge tone="iris"><Brain size={12} /> {children.length} {children.length === 1 ? "ребёнок" : "детей"}</Badge>}
      />

      {error && <ErrorState error={error} onRetry={refresh} />}

      <ChildTabs children={children} value={active?.learner.id} onChange={setSelected} />

      {active && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <StatCard icon={ListChecks} label="Пройдено тестов" value={active.stats.tests || 0} hint="по возрасту и классу" tone="iris" />
            <StatCard icon={Sparkles} label="Сильных сторон" value={active.stats.strengths || 0} hint="на что можно опереться" tone="green" />
            <StatCard icon={HeartHandshake} label="Зон внимания" value={active.stats.attention || 0} hint="что стоит поддержать" tone="rose" />
          </div>

          <Card className="p-5">
            <div className="flex items-start gap-3">
              <ShieldCheck size={18} className="mt-0.5 shrink-0 text-iris-300" />
              <div>
                <p className="text-sm font-semibold text-white">Как читать результаты</p>
                <p className="mt-1 text-xs leading-relaxed text-mist-400">
                  Это мягкий скрининг, а не диагноз. Смотрите на динамику и на то, совпадает ли
                  результат с вашими наблюдениями. Если что-то тревожит — обсудите со школьным психологом.
                </p>
                <p className="mt-2 text-[11px] leading-relaxed text-mist-600">{data?.source}</p>
              </div>
            </div>
          </Card>

          {active.recommendations.length > 0 && (
            <section className="space-y-3">
              <SectionTitle
                title="Рекомендации родителям"
                subtitle="Сначала — то, что просит внимания, затем сильные стороны и интересы."
              />
              <div className="space-y-3">
                {active.recommendations.map((item, index) => {
                  const meta = KIND[item.kind] || KIND.attention;
                  const Icon = meta.icon;
                  return (
                    <Card key={`${item.result_id}-${item.scale}-${index}`} className="p-5">
                      <div className="flex items-start gap-3">
                        <span className={`mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/5 ${
                          meta.tone === "rose" ? "text-rose-300" : meta.tone === "gold" ? "text-amber-300" : meta.tone === "cyan" ? "text-cyan-300" : "text-emerald-300"
                        }`}>
                          <Icon size={18} />
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="font-display text-sm font-semibold text-white">{item.title}</h3>
                            <Badge tone={meta.tone}>{meta.label}</Badge>
                          </div>
                          <p className="mt-1.5 text-sm leading-relaxed text-mist-400">{item.text}</p>
                          {item.advice?.length > 0 && (
                            <ul className="mt-3 space-y-1.5">
                              {item.advice.map((advice, adviceIndex) => (
                                <li key={adviceIndex} className="flex gap-2 text-xs leading-relaxed text-mist-500">
                                  <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-emerald-300/80" />
                                  <span>{advice}</span>
                                </li>
                              ))}
                            </ul>
                          )}
                          <div className="mt-3 flex flex-wrap items-center gap-3 text-[10px] text-mist-600">
                            <span>{item.test_title}</span>
                            <span>{formatDate(item.created_at)}</span>
                            <Link to={`/app/parent/psychology/result/${item.result_id}`} className="inline-flex items-center gap-1 font-bold text-iris-300 hover:underline">
                              Весь результат <ArrowRight size={11} />
                            </Link>
                          </div>
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </section>
          )}

          <section className="space-y-3">
            <SectionTitle title="Пройденные тесты" subtitle={`Последние результаты по каждому тесту для ${active.learner.name}.`} />
            {active.results.length === 0 ? (
              <Card>
                <EmptyState
                  icon="📝"
                  title="Ребёнок ещё не проходил тесты"
                  text="Тесты находятся в кабинете ученика: раздел «Школьная психология». После прохождения результат появится здесь автоматически."
                />
              </Card>
            ) : (
              <div className="grid gap-3 lg:grid-cols-2">
                {active.results.map((item) => (
                  <Link key={item.id} to={`/app/parent/psychology/result/${item.id}`}>
                    <Card hover className="h-full p-5">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="font-display text-sm font-semibold text-white">{item.test_title}</h3>
                            <Badge tone="cyan">{item.category_title}</Badge>
                            {item.has_ai && <Badge tone="iris"><Sparkles size={10} /> ИИ</Badge>}
                          </div>
                          <p className="mt-1.5 text-xs leading-relaxed text-mist-400">{item.headline}</p>
                        </div>
                        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/8 bg-white/[0.04] text-lg">🧠</span>
                      </div>
                      <div className="mt-3 flex items-center justify-between text-[10px] text-mist-600">
                        <span>{formatDate(item.created_at)}</span>
                        <span className="inline-flex items-center gap-1 font-bold text-iris-300">Открыть <ArrowRight size={11} /></span>
                      </div>
                    </Card>
                  </Link>
                ))}
              </div>
            )}
          </section>
        </>
      )}

      <Card className="p-5">
        <div className="flex items-start gap-3">
          <Heart size={18} className="mt-0.5 shrink-0 text-rose-300" />
          <div>
            <p className="text-sm font-semibold text-white">Оповещения</p>
            <p className="mt-1 text-xs leading-relaxed text-mist-400">
              После каждого теста приходит уведомление о результате и о новых рекомендациях.
              Их можно посмотреть в разделе «Уведомления» на сайте и в приложении.
            </p>
            <Link to="/app/notifications" className="mt-2 inline-flex items-center gap-1 text-[11px] font-bold text-iris-300 hover:underline">
              Открыть уведомления <ArrowRight size={11} />
            </Link>
          </div>
        </div>
      </Card>
    </div>
  );
}
