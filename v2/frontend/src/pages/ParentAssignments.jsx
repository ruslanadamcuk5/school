import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, CheckCircle2, Clock, Play, Send, Sparkles, Trophy } from "lucide-react";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Input,
  PageHeader,
  Progress,
  SectionTitle,
  Select,
  Skeleton,
  StatCard,
  Textarea,
} from "../components/ui";
import { useAction, useApi, toast } from "../lib/hooks";
import { api, objectUrl } from "../lib/api";
import { formatDateTime, scoreTone } from "../lib/format";

const TASK_TYPES = [
  { value: "test", label: "Тест", icon: "🧠", hint: "Вопросы с вариантами или кратким ответом" },
  { value: "read", label: "Чтение темы", icon: "📖", hint: "Прочитать выбранную тему в учебнике" },
  {
    value: "dictation",
    label: "Диктант",
    icon: "✍️",
    hint: "Написать под диктовку — текст читает синтезатор речи",
  },
  { value: "other", label: "Иное задание", icon: "📝", hint: "Свободное описание задания" },
];

function speak(text) {
  if (!text || typeof window === "undefined" || !window.speechSynthesis) return;
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "ru-RU";
  utterance.rate = 0.92;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
}

function AnswerPhotos({ urls = [] }) {
  const [sources, setSources] = useState([]);
  const key = urls.join("|");
  useEffect(() => {
    if (!urls.length) {
      setSources([]);
      return undefined;
    }
    let alive = true;
    const created = [];
    Promise.all(
      urls.map((url) =>
        objectUrl(url)
          .then((src) => {
            created.push(src);
            return src;
          })
          .catch(() => null),
      ),
    ).then((list) => {
      if (alive) setSources(list.filter(Boolean));
    });
    return () => {
      alive = false;
      created.forEach((src) => URL.revokeObjectURL(src));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  if (!urls.length) return null;
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
      {sources.map((src, index) => (
        <a
          key={src}
          href={src}
          target="_blank"
          rel="noreferrer"
          className="overflow-hidden rounded-xl border border-white/8 bg-ink-950"
        >
          <img src={src} alt={`Фото решения ${index + 1}`} className="h-44 w-full object-cover" />
        </a>
      ))}
    </div>
  );
}

export function ParentAssignmentsPage() {
  const { run } = useAction();

  const { data: childrenData, loading: childrenLoading } = useApi("/parent/children");
  const { data: meta, loading: metaLoading } = useApi("/meta", { ttl: 120_000 });
  const {
    data: assignmentsData,
    loading: assignmentsLoading,
    refresh: refreshAssignments,
  } = useApi("/parent/assignments", { ttl: 0 });

  const children = childrenData?.children || [];
  const subjects = meta?.subjects || [];
  const assignments = assignmentsData?.assignments || [];

  const [formOpen, setFormOpen] = useState(false);
  const [selectedChildIds, setSelectedChildIds] = useState(new Set());
  const [subjectId, setSubjectId] = useState("");
  const [taskType, setTaskType] = useState("test");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [referenceText, setReferenceText] = useState("");
  const [audioText, setAudioText] = useState("");
  const [allowPhoto, setAllowPhoto] = useState(true);
  const [allowText, setAllowText] = useState(true);
  const [dueDate, setDueDate] = useState("");
  const [timeLimit, setTimeLimit] = useState("");
  const [questionsCount, setQuestionsCount] = useState("10");

  const [topics, setTopics] = useState([]);
  const [topicsLoading, setTopicsLoading] = useState(false);
  const [topicError, setTopicError] = useState("");
  const [selectedTopicSlugs, setSelectedTopicSlugs] = useState(new Set());

  const selectedChildren = useMemo(
    () => children.filter((child) => selectedChildIds.has(String(child.user.id))),
    [children, selectedChildIds],
  );

  const effectiveGrade = useMemo(() => {
    if (selectedChildren.length === 0) return "";
    return String(selectedChildren[0].grade || "");
  }, [selectedChildren]);

  const topicsBySubject = useMemo(() => {
    const groups = {};
    for (const topic of topics) {
      const key = topic.subject_name || "Другое";
      if (!groups[key]) groups[key] = { icon: topic.subject_icon || "📚", topics: [] };
      groups[key].topics.push(topic);
    }
    return groups;
  }, [topics]);

  useEffect(() => {
    if (children.length === 1 && selectedChildIds.size === 0) {
      setSelectedChildIds(new Set([String(children[0].user.id)]));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [children, selectedChildIds.size]);

  useEffect(() => {
    if (!subjectId || !effectiveGrade) {
      setTopics([]);
      setTopicError("");
      return;
    }
    setTopicsLoading(true);
    setTopicError("");
    api
      .get(`/topics?grade=${effectiveGrade}&subject_id=${subjectId}`)
      .then((data) => {
        setTopics(data.topics || []);
      })
      .catch((err) => {
        setTopicError(err.message || "Не удалось загрузить темы");
        setTopics([]);
      })
      .finally(() => {
        setTopicsLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subjectId, effectiveGrade]);

  const toggleChild = (id) => {
    setSelectedChildIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleTopic = (slug) => {
    setSelectedTopicSlugs((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  };

  const createAssignment = async () => {
    if (selectedChildren.length === 0) {
      toast("Выберите хотя бы одного ребёнка", "error");
      return;
    }
    if (!subjectId) {
      toast("Выберите предмет", "error");
      return;
    }
    const topicSlugs = Array.from(selectedTopicSlugs);
    if ((taskType === "test" || taskType === "read") && topicSlugs.length === 0) {
      toast("Выберите хотя бы одну тему", "error");
      return;
    }
    if (taskType === "dictation" && !referenceText && topicSlugs.length === 0) {
      toast("Введите текст диктанта или выберите тему", "error");
      return;
    }
    if (taskType === "other" && !description) {
      toast("Опишите задание", "error");
      return;
    }
    if (!allowPhoto && !allowText) {
      toast("Разрешите ответ текстом или фото", "error");
      return;
    }

    try {
      await run(() =>
        api.post("/parent/assignments", {
          child_ids: selectedChildren.map((c) => String(c.user.id)),
          subject_id: subjectId,
          task_type: taskType,
          topic_slugs: topicSlugs,
          title,
          description,
          reference_text: referenceText,
          audio_text: audioText,
          allow_photo: allowPhoto,
          allow_text: allowText,
          due_date: dueDate || undefined,
          time_limit: parseInt(timeLimit || "0", 10) || 0,
          questions_count: parseInt(questionsCount || "10", 10) || 10,
          kind: "домашняя",
        }),
      );
      toast("Задание создано и отправлено детям", "success");
      setFormOpen(false);
      resetForm();
      refreshAssignments();
    } catch (err) {
      toast(err.message || "Не удалось создать задание", "error");
    }
  };

  const resetForm = () => {
    setSelectedChildIds(new Set());
    setSubjectId("");
    setTaskType("test");
    setTitle("");
    setDescription("");
    setReferenceText("");
    setAudioText("");
    setAllowPhoto(true);
    setAllowText(true);
    setDueDate("");
    setTimeLimit("");
    setQuestionsCount("10");
    setSelectedTopicSlugs(new Set());
    setTopics([]);
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader
        title="Задания детям"
        subtitle="Назначайте тесты, диктанты и чтение своим детям — как учитель в классе."
        actions={
          <Button icon={Play} onClick={() => setFormOpen(true)}>
            Новое задание
          </Button>
        }
      />

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        <StatCard icon={Trophy} label="Детей" value={children.length} />
        <StatCard icon={CheckCircle2} label="Заданий" value={assignments.length} />
        <StatCard
          icon={Clock}
          label="Выбрано детей"
          value={selectedChildren.length}
          tone={selectedChildren.length ? "iris" : "mist"}
        />
        <StatCard
          icon={Sparkles}
          label="С проверкой фото"
          value={assignments.filter((a) => a.allow_photo).length}
          hint="ИИ проверит рукописные ответы"
        />
      </div>

      {formOpen ? (
        <AssignmentForm
          children={children}
          subjects={subjects}
          selectedChildIds={selectedChildIds}
          onToggleChild={toggleChild}
          subjectId={subjectId}
          onSetSubjectId={setSubjectId}
          taskType={taskType}
          onSetTaskType={setTaskType}
          title={title}
          onSetTitle={setTitle}
          description={description}
          onSetDescription={setDescription}
          referenceText={referenceText}
          onSetReferenceText={setReferenceText}
          audioText={audioText}
          onSetAudioText={setAudioText}
          allowPhoto={allowPhoto}
          onSetAllowPhoto={setAllowPhoto}
          allowText={allowText}
          onSetAllowText={setAllowText}
          dueDate={dueDate}
          onSetDueDate={setDueDate}
          timeLimit={timeLimit}
          onSetTimeLimit={setTimeLimit}
          questionsCount={questionsCount}
          onSetQuestionsCount={setQuestionsCount}
          topics={topics}
          topicsBySubject={topicsBySubject}
          topicsLoading={topicsLoading}
          topicError={topicError}
          selectedTopicSlugs={selectedTopicSlugs}
          onToggleTopic={toggleTopic}
          onCreate={createAssignment}
          onClose={() => setFormOpen(false)}
          onReset={resetForm}
        />
      ) : (
        <AssignmentList
          assignments={assignments}
          loading={assignmentsLoading}
          refresh={refreshAssignments}
        />
      )}
    </div>
  );
}

function AssignmentForm({
  children,
  subjects,
  selectedChildIds,
  onToggleChild,
  subjectId,
  onSetSubjectId,
  taskType,
  onSetTaskType,
  title,
  onSetTitle,
  description,
  onSetDescription,
  referenceText,
  onSetReferenceText,
  audioText,
  onSetAudioText,
  allowPhoto,
  onSetAllowPhoto,
  allowText,
  onSetAllowText,
  dueDate,
  onSetDueDate,
  timeLimit,
  onSetTimeLimit,
  questionsCount,
  onSetQuestionsCount,
  topics,
  topicsBySubject,
  topicsLoading,
  topicError,
  selectedTopicSlugs,
  onToggleTopic,
  onCreate,
  onClose,
  onReset,
}) {
  const selectedChildren = children.filter((child) => selectedChildIds.has(String(child.user.id)));
  const noChildSelected = selectedChildren.length === 0;

  return (
    <Card className="p-5 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div>
          <h3 className="font-display text-lg font-semibold text-white">
            Новое задание для детей
          </h3>
          <p className="mt-1 text-sm text-mist-500">
            Выберите детей, предмет, тему и тип задания. Диктант и чтение можно озвучить.
          </p>
        </div>
        <Button variant="ghost" icon={ArrowLeft} onClick={onClose}>
          Назад к списку
        </Button>
      </div>

      <div className="space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Дети" hint="Кто получит задание">
            <div className="mt-2 grid gap-2 sm:grid-cols-3">
              {children.map((child) => {
                const active = selectedChildIds.has(String(child.user.id));
                return (
                  <button
                    key={child.user.id}
                    type="button"
                    onClick={() => onToggleChild(child.user.id)}
                    className={`flex flex-col items-center gap-2 rounded-xl border px-3 py-3 text-left transition ${
                      active
                        ? "border-iris-400/60 bg-iris-500/15"
                        : "border-white/8 bg-white/[0.02] hover:border-white/20"
                    }`}
                  >
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/[0.03] text-sm font-bold">
                      {(child.user.first_name || "?")[0]}{(child.user.last_name || "?")[0]}
                    </div>
                    <p className="text-sm font-semibold text-white truncate w-full">
                      {child.user.first_name} {child.user.last_name}
                    </p>
                    <p className="text-[10px] text-mist-500">{child.grade} класс</p>
                  </button>
                );
              })}
            </div>
          </Field>

          <Field label="Предмет">
            <Select
              value={subjectId}
              onChange={(event) => onSetSubjectId(event.target.value)}
              className="w-full"
            >
              <option value="">Выберите предмет</option>
              {subjects.map((subject) => (
                <option key={subject.id} value={subject.id}>
                  {subject.icon} {subject.name}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        <Field label="Тип задания">
          <div className="mt-2 grid gap-2 sm:grid-cols-4">
            {TASK_TYPES.map((type) => {
              const active = taskType === type.value;
              return (
                <button
                  key={type.value}
                  type="button"
                  onClick={() => onSetTaskType(type.value)}
                  className={`flex flex-col items-center gap-2 rounded-xl border px-3 py-3 text-left transition ${
                    active
                      ? "border-iris-400/60 bg-iris-500/15"
                      : "border-white/8 bg-white/[0.02] hover:border-white/20"
                  }`}
                >
                  <span className="text-2xl">{type.icon}</span>
                  <p className="text-sm font-semibold text-white">{type.label}</p>
                  <p className="text-[10px] text-mist-500 leading-relaxed text-center">{type.hint}</p>
                </button>
              );
            })}
          </div>
        </Field>

        <Field label="Название задания">
          <Input
            value={title}
            onChange={(event) => onSetTitle(event.target.value)}
            placeholder="Например: Диктант по правилам письма"
          />
        </Field>

        {taskType === "dictation" && (
          <>
            <Field label="Текст диктанта" hint="Ученик прослушает текст и напишет его">
              <Textarea
                value={referenceText}
                onChange={(event) => onSetReferenceText(event.target.value)}
                rows={4}
                placeholder="Текст, который нужно написать под диктовку…"
              />
            </Field>
            <Field label="Озвучка (вслух)" hint="Если пусто, используется текст диктанта">
              <Textarea
                value={audioText}
                onChange={(event) => onSetAudioText(event.target.value)}
                rows={2}
                placeholder="Что именно прочитает синтезатор речи…"
              />
            </Field>
          </>
        )}

        {taskType === "other" && (
          <Field label="Описание задания" hint="Что именно нужно сделать ребёнку">
            <Textarea
              value={description}
              onChange={(event) => onSetDescription(event.target.value)}
              rows={3}
              placeholder="Свободное описание задания…"
            />
          </Field>
        )}

        {(taskType === "test" || taskType === "read") && (
          <Field label="Темы" hint="Темы из выбранного предмета и класса">
            <div className="mt-2">
              {noChildSelected && (
                <p className="mt-2 text-xs text-mist-500">
                  Сначала выберите ребёнка, чтобы определить класс и подгрузить темы.
                </p>
              )}
              {!noChildSelected && topicsLoading && (
                <div className="flex items-center gap-2 text-xs text-mist-500">
                  <Skeleton className="h-4 w-24" /> Загрузка тем…
                </div>
              )}
              {!noChildSelected && !topicsLoading && topicError && (
                <p className="mt-2 text-xs text-rose-400">{topicError}</p>
              )}
              {!noChildSelected && !topicsLoading && !topicError && topics.length === 0 && (
                <p className="mt-2 text-xs text-mist-500">
                  Тем не найдено для выбранного предмета и класса
                  {effectiveGrade ? ` (${effectiveGrade} класс)` : ""}.
                  Выберите другой предмет или класс ребёнка.
                </p>
              )}
              {!noChildSelected && !topicsLoading && topics.length > 0 && (
                <div className="mt-3 grid gap-2 sm:grid-cols-4">
                  {Object.entries(topicsBySubject).map(([groupName, group]) => (
                    <div key={groupName} className="col-span-full">
                      <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-mist-500">
                        {groupName}
                      </p>
                      <div className="grid gap-2 sm:grid-cols-3">
                        {group.topics.map((topic) => {
                          const active = selectedTopicSlugs.has(topic.slug);
                          return (
                            <button
                              key={topic.slug}
                              type="button"
                              onClick={() => onToggleTopic(topic.slug)}
                              className={`flex flex-col items-center gap-1.5 rounded-xl border px-2.5 py-2 text-left transition ${
                                active
                                  ? "border-iris-400/60 bg-iris-500/15"
                                  : "border-white/8 bg-white/[0.02] hover:border-white/20"
                              }`}
                            >
                              <p className="text-xs font-semibold text-white leading-snug">{topic.title}</p>
                              {topic.page && (
                                <p className="text-[10px] text-mist-500">стр. {topic.page}</p>
                              )}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Field>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Field label="Фото ответов" hint="Разрешить присылать фото решения (ИИ проверит)">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={allowPhoto}
                onChange={(event) => onSetAllowPhoto(event.target.checked)}
                className="rounded border-white/8 bg-ink-950 text-iris-500 focus:ring-iris-400"
              />
              <span className="text-sm text-white">{allowPhoto ? "Разрешено" : "Запрещено"}</span>
            </label>
          </Field>
          <Field label="Текст ответов" hint="Разрешить отвечать текстом в приложении">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={allowText}
                onChange={(event) => onSetAllowText(event.target.checked)}
                className="rounded border-white/8 bg-ink-950 text-iris-500 focus:ring-iris-400"
              />
              <span className="text-sm text-white">{allowText ? "Разрешено" : "Запрещено"}</span>
            </label>
          </Field>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Field label="Срок сдачи">
            <Input type="date" value={dueDate} onChange={(event) => onSetDueDate(event.target.value)} />
          </Field>
          <Field label="Лимит времени (мин)">
            <Input
              type="number"
              value={timeLimit}
              onChange={(event) => onSetTimeLimit(event.target.value)}
              placeholder="0 = без лимита"
            />
          </Field>
          <Field label="Вопросов (для теста)">
            <Input
              type="number"
              value={questionsCount}
              onChange={(event) => onSetQuestionsCount(event.target.value)}
              placeholder="10"
            />
          </Field>
        </div>

        <div className="rounded-xl border border-white/8 bg-white/[0.02] p-4">
          <p className="text-[11px] leading-relaxed text-mist-500">
            Задание будет создано отдельно для каждого выбранного ребёнка. Дети увидят его в разделе
            «Задания» и смогут ответить текстом, фото или прочитать тему.
          </p>
        </div>
      </div>
    </Card>
  );
}

function AssignmentList({ assignments, loading, refresh }) {
  if (loading) return <Skeleton className="h-96 w-full" />;
  if (assignments.length === 0) {
    return (
      <EmptyState
        icon="📭"
        title="Заданий пока нет"
        text="Создайте первое задание — выберите детей, предмет и тему."
      />
    );
  }

  return (
    <div className="space-y-4">
      {assignments.map((assignment) => (
        <Card key={assignment.id} className="p-5 sm:p-6 hover:border-white/10 transition">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
            <div>
              <p className="text-sm font-bold text-white">{assignment.title}</p>
              <p className="text-[11px] text-mist-500">
                {assignment.task_type} · {assignment.author_name || "Родитель"}
                {assignment.due_date ? ` · до ${formatDateTime(assignment.due_date)}` : ""}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge tone={assignment.allow_photo ? "iris" : "mist"} size="sm">
                {assignment.allow_photo ? "Фото" : "Текст"}
              </Badge>
              <Badge tone={scoreTone(assignment.results?.[0]?.percent || 0)} size="sm">
                {assignment.results.length} работ
              </Badge>
            </div>
          </div>

          <div className="space-y-3">
            {assignment.results.length === 0 ? (
              <EmptyState icon="⏳" title="Ещё нет отправленных работ" text="Дети ещё не прислали ответы." />
            ) : (
              assignment.results.map((result) => (
                <div key={`${result.student_id}-${assignment.id}`} className="rounded-xl border border-white/8 bg-white/[0.02] p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/[0.03] text-xs font-bold">
                        {initials(result.student_name)}
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-white">{result.student_name}</p>
                        <p className="text-[11px] text-mist-500">
                          {result.completed_at ? formatDateTime(result.completed_at) : "не сдано"}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-display text-lg font-semibold text-white">
                        {result.score}/{result.max_score}
                      </p>
                      <p className="text-[11px] font-bold uppercase tracking-wider text-mist-500">
                        {result.percent}%
                      </p>
                    </div>
                  </div>

                  <Progress value={result.percent} />

                  {result.ai_status === "checked" && (
                    <div className="mt-3 rounded-xl border border-iris-400/20 bg-iris-500/[0.06] p-3">
                      <p className="mb-1 text-xs font-semibold text-iris-300">Разбор ИИ</p>
                      <p className="text-[11px] leading-relaxed text-mist-300">{result.ai_feedback || ""}</p>
                    </div>
                  )}

                  {(result.photo_urls || []).length > 0 && (
                    <div className="mt-3">
                      <AnswerPhotos urls={result.photo_urls} />
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </Card>
      ))}
    </div>
  );
}

function initials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0][0];
  return parts[0][0] + parts[parts.length - 1][0];
}


