import { useMemo, useState } from "react";
import {
  BookOpen,
  Check,
  Layers,
  Pencil,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  IconButton,
  Input,
  Modal,
  PageHeader,
  Select,
  Skeleton,
  StatCard,
  Textarea,
} from "../../components/ui";
import { useAction, useApi, toast } from "../../lib/hooks";
import { api, invalidate } from "../../lib/api";
import { plural } from "../../lib/format";
import { SearchBox } from "./shared";

const EMPTY_TOPIC = {
  subject_id: "",
  grade: 1,
  title: "",
  description: "",
  icon: "",
  color: "",
  order_index: 0,
};

const COLORS = ["indigo", "sky", "rose", "violet", "emerald", "teal", "amber"];

export function AdminTopics() {
  const { data, loading, error, refresh } = useApi("/admin/topics");
  const [search, setSearch] = useState("");
  const [subjectId, setSubjectId] = useState("all");
  const [grade, setGrade] = useState("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_TOPIC);
  const [editTopic, setEditTopic] = useState(null);
  const [editForm, setEditForm] = useState(null);
  const { pending, run } = useAction();

  const topics = data?.topics || [];
  const subjects = data?.subjects || [];

  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    return topics.filter((topic) => {
      if (subjectId !== "all" && Number(topic.subject_id) !== Number(subjectId)) return false;
      if (grade !== "all" && Number(topic.grade) !== Number(grade)) return false;
      if (!query) return true;
      return `${topic.title} ${topic.slug} ${topic.subject_name}`.toLowerCase().includes(query);
    });
  }, [topics, search, subjectId, grade]);

  const byKind = useMemo(() => {
    return topics.reduce((acc, topic) => {
      acc[topic.kind || "practice"] = (acc[topic.kind || "practice"] || 0) + 1;
      return acc;
    }, {});
  }, [topics]);

  const afterChange = async (message) => {
    invalidate("/admin");
    await refresh();
    toast(message, "success");
  };

  const openCreate = () => {
    setForm({ ...EMPTY_TOPIC, subject_id: subjects[0] ? String(subjects[0].id) : "" });
    setCreateOpen(true);
  };

  const submitCreate = async () => {
    if (!form.subject_id || !form.title.trim()) {
      toast("Нужны предмет и название темы", "info");
      return;
    }
    try {
      await run(() => api.post("/admin/topics", {
        ...form,
        subject_id: Number(form.subject_id),
        grade: Number(form.grade),
        order_index: Number(form.order_index) || 0,
      }));
      setCreateOpen(false);
      setForm(EMPTY_TOPIC);
      await afterChange("Тема создана");
    } catch (err) {
      toast(err.message || "Не удалось создать тему", "error");
    }
  };

  const openEdit = (topic) => {
    setEditTopic(topic);
    setEditForm({
      title: topic.title || "",
      grade: topic.grade || 1,
      description: topic.description || "",
      icon: topic.icon || "",
      color: topic.color || "",
      order_index: topic.order_index || 0,
      page_start: topic.page_start || "",
      page_end: topic.page_end || "",
    });
  };

  const submitEdit = async () => {
    if (!editTopic || !editForm) return;
    try {
      await run(() => api.patch(`/admin/topics/${editTopic.slug}`, {
        ...editForm,
        grade: Number(editForm.grade) || 1,
        order_index: Number(editForm.order_index) || 0,
        page_start: editForm.page_start === "" ? null : Number(editForm.page_start),
        page_end: editForm.page_end === "" ? null : Number(editForm.page_end),
      }));
      setEditTopic(null);
      setEditForm(null);
      await afterChange("Тема обновлена");
    } catch (err) {
      toast(err.message || "Не удалось сохранить тему", "error");
    }
  };

  const remove = async (topic) => {
    if (!window.confirm(`Удалить тему «${topic.title}»? Связанные задания могут перестать работать.`)) return;
    try {
      await run(() => api.del(`/admin/topics/${topic.slug}`));
      await afterChange("Тема удалена");
    } catch (err) {
      toast(err.message || "Не удалось удалить тему", "error");
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Темы и предметы"
        subtitle="Каталог обучения: темы по классам, порядок и оформление. Отсюда темы попадают в задания и практику."
        actions={<Button icon={Plus} onClick={openCreate}>Новая тема</Button>}
      />

      {error && <ErrorState error={error} onRetry={refresh} />}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={BookOpen} label="Тем" value={topics.length} tone="iris" />
        <StatCard icon={Layers} label="Предметов" value={subjects.length} tone="cyan" />
        <StatCard icon={BookOpen} label="Чтение" value={byKind.reading || 0} hint="Тексты и тесты" tone="gold" />
        <StatCard icon={BookOpen} label="Практика" value={(byKind.practice || 0) + (byKind.quiz || 0)} hint="Тренировки и тесты" tone="green" />
      </div>

      <Card className="space-y-3 p-4">
        <SearchBox value={search} onChange={setSearch} placeholder="Название темы, slug или предмет…" />
        <div className="grid gap-2 sm:grid-cols-2">
          <Select value={subjectId} onChange={(event) => setSubjectId(event.target.value)}>
            <option value="all">Все предметы</option>
            {subjects.map((subject) => (
              <option key={subject.id} value={subject.id}>{subject.icon} {subject.name} · {subject.topics_count}</option>
            ))}
          </Select>
          <Select value={grade} onChange={(event) => setGrade(event.target.value)}>
            <option value="all">Все классы</option>
            {Array.from({ length: 11 }).map((_, index) => (
              <option key={index + 1} value={index + 1}>{index + 1} класс</option>
            ))}
          </Select>
        </div>
      </Card>

      {loading && !data ? (
        <div className="space-y-2">{Array.from({ length: 8 }).map((_, index) => <Skeleton key={index} className="h-20" />)}</div>
      ) : visible.length === 0 ? (
        <Card>
          <EmptyState
            icon="📚"
            title={topics.length ? "Ничего не нашлось" : "Тем пока нет"}
            text={topics.length ? "Смените фильтр или запрос." : "Создайте первую тему каталога."}
            action={<Button icon={Plus} onClick={openCreate}>Новая тема</Button>}
          />
        </Card>
      ) : (
        <Card className="divide-y divide-white/6 p-2">
          {visible.map((topic) => (
            <div key={topic.slug} className="flex flex-col gap-3 rounded-xl px-3 py-3 transition hover:bg-white/[0.025] sm:flex-row sm:items-center">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-xl">
                {topic.icon || topic.subject_icon || "📘"}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="truncate text-sm font-bold text-white">{topic.title}</p>
                  <Badge tone={topic.kind === "reading" ? "gold" : "iris"}>
                    {topic.kind === "reading" ? "чтение" : "практика"}
                  </Badge>
                  <Badge>{topic.grade} класс</Badge>
                  {topic.source === "starter" && <Badge tone="green">стартовый набор</Badge>}
                </div>
                <p className="mt-0.5 truncate text-[11px] text-mist-500">
                  {topic.subject_icon} {topic.subject_name} · <span className="font-mono text-[10px]">{topic.slug}</span>
                </p>
                {topic.description && <p className="mt-0.5 line-clamp-1 text-[10px] text-mist-600">{topic.description}</p>}
              </div>
              <div className="flex shrink-0 items-center gap-1.5">
                <span className="mr-1 hidden text-[10px] text-mist-600 sm:inline">
                  #{topic.order_index} · {plural(topic.books_count || 0, ["книга", "книги", "книг"])}
                </span>
                <IconButton icon={Pencil} label="Изменить" onClick={() => openEdit(topic)} />
                <IconButton icon={Trash2} label="Удалить" className="text-rose-300" onClick={() => remove(topic)} />
              </div>
            </div>
          ))}
        </Card>
      )}

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Новая тема"
        description="Тема появится в каталоге выбранного предмета и класса."
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>Отмена</Button>
            <Button icon={Check} loading={pending} onClick={submitCreate}>Создать</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Предмет">
            <Select value={form.subject_id} onChange={(event) => setForm((current) => ({ ...current, subject_id: event.target.value }))}>
              <option value="">Выберите предмет</option>
              {subjects.map((subject) => (
                <option key={subject.id} value={subject.id}>{subject.icon} {subject.name}</option>
              ))}
            </Select>
          </Field>
          <Field label="Класс">
            <Select value={form.grade} onChange={(event) => setForm((current) => ({ ...current, grade: event.target.value }))}>
              {Array.from({ length: 11 }).map((_, index) => (
                <option key={index + 1} value={index + 1}>{index + 1} класс</option>
              ))}
            </Select>
          </Field>
          <Field label="Название" className="sm:col-span-2">
            <Input value={form.title} onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))} placeholder="Например: Числа до 1000" />
          </Field>
          <Field label="Описание" className="sm:col-span-2">
            <Textarea value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} placeholder="Чему учит тема и что важно знать…" />
          </Field>
          <Field label="Иконка" hint="Эмодзи, например 📐">
            <Input value={form.icon} onChange={(event) => setForm((current) => ({ ...current, icon: event.target.value }))} maxLength={8} placeholder="📐" />
          </Field>
          <Field label="Порядок" hint="Меньше — выше в списке.">
            <Input type="number" value={form.order_index} onChange={(event) => setForm((current) => ({ ...current, order_index: event.target.value }))} />
          </Field>
          <Field label="Цвет" className="sm:col-span-2">
            <div className="flex flex-wrap gap-1.5">
              {COLORS.map((color) => (
                <button
                  key={color}
                  type="button"
                  onClick={() => setForm((current) => ({ ...current, color }))}
                  className={`rounded-lg border px-2.5 py-1.5 text-[11px] font-semibold capitalize ${
                    form.color === color ? "border-iris-400/50 bg-iris-500/15 text-white" : "border-white/8 text-mist-500"
                  }`}
                >
                  {color}
                </button>
              ))}
            </div>
          </Field>
        </div>
      </Modal>

      <Modal
        open={Boolean(editTopic && editForm)}
        onClose={() => { setEditTopic(null); setEditForm(null); }}
        title={editTopic?.title || "Тема"}
        description={editTopic?.slug}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => { setEditTopic(null); setEditForm(null); }}>Отмена</Button>
            <Button icon={Check} loading={pending} onClick={submitEdit}>Сохранить</Button>
          </>
        }
      >
        {editForm && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Название" className="sm:col-span-2">
              <Input value={editForm.title} onChange={(event) => setEditForm((current) => ({ ...current, title: event.target.value }))} />
            </Field>
            <Field label="Класс">
              <Select value={editForm.grade} onChange={(event) => setEditForm((current) => ({ ...current, grade: event.target.value }))}>
                {Array.from({ length: 11 }).map((_, index) => (
                  <option key={index + 1} value={index + 1}>{index + 1} класс</option>
                ))}
              </Select>
            </Field>
            <Field label="Порядок">
              <Input type="number" value={editForm.order_index} onChange={(event) => setEditForm((current) => ({ ...current, order_index: event.target.value }))} />
            </Field>
            <Field label="Описание" className="sm:col-span-2">
              <Textarea value={editForm.description} onChange={(event) => setEditForm((current) => ({ ...current, description: event.target.value }))} />
            </Field>
            <Field label="Иконка">
              <Input value={editForm.icon} onChange={(event) => setEditForm((current) => ({ ...current, icon: event.target.value }))} maxLength={8} />
            </Field>
            <Field label="Цвет">
              <Select value={editForm.color} onChange={(event) => setEditForm((current) => ({ ...current, color: event.target.value }))}>
                <option value="">Без цвета</option>
                {COLORS.map((color) => <option key={color} value={color}>{color}</option>)}
              </Select>
            </Field>
            <Field label="Страница с" hint="Для текстов и пособий.">
              <Input type="number" value={editForm.page_start} onChange={(event) => setEditForm((current) => ({ ...current, page_start: event.target.value }))} />
            </Field>
            <Field label="Страница по">
              <Input type="number" value={editForm.page_end} onChange={(event) => setEditForm((current) => ({ ...current, page_end: event.target.value }))} />
            </Field>
          </div>
        )}
      </Modal>
    </div>
  );
}
