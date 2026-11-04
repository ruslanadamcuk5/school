import { useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  Check,
  GraduationCap,
  Layers,
  Pencil,
  Plus,
  Sparkles,
  Trash2,
  Users,
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
import { SearchBox, Toggle } from "./shared";

const GRADES = Array.from({ length: 11 }, (_, index) => index + 1);

const EMPTY = {
  subject_id: "",
  title: "",
  grade: 3,
  description: "",
  teacher_id: "",
  school_id: "",
  class_ids: [],
};

function ClassPicker({ classes, value, onChange }) {
  return (
    <div className="max-h-44 space-y-1 overflow-y-auto rounded-xl border border-white/8 bg-white/[0.02] p-2">
      {classes.length === 0 && <p className="px-2 py-3 text-xs text-mist-500">Классов пока нет.</p>}
      {classes.map((klass) => {
        const checked = value.includes(klass.id);
        return (
          <label key={klass.id} className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 text-xs text-mist-200 hover:bg-white/5">
            <input
              type="checkbox"
              checked={checked}
              onChange={() => onChange(checked ? value.filter((id) => id !== klass.id) : [...value, klass.id])}
              className="h-4 w-4 accent-iris-500"
            />
            <span className="min-w-0 flex-1 truncate">{klass.school_name} · {klass.title}</span>
            <span className="shrink-0 text-[10px] text-mist-600">{klass.students_count || 0} уч.</span>
          </label>
        );
      })}
    </div>
  );
}

export function AdminCourses() {
  const { data, loading, error, refresh } = useApi("/admin/courses");
  const [search, setSearch] = useState("");
  const [subject, setSubject] = useState("all");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [classes, setClasses] = useState([]);
  const [topics, setTopics] = useState([]);
  const [newTopic, setNewTopic] = useState({ title: "", description: "" });
  const [busy, setBusy] = useState("");
  const { pending, run } = useAction();

  const courses = data?.courses || [];
  const subjects = data?.subjects || [];
  const allClasses = data?.classes || [];
  const teachers = data?.teachers || [];

  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    return courses.filter((course) => {
      if (subject !== "all" && String(course.subject_id) !== String(subject)) return false;
      if (!query) return true;
      return `${course.title} ${course.subject_name || ""} ${course.teacher_first || ""} ${course.teacher_last || ""}`
        .toLowerCase()
        .includes(query);
    });
  }, [courses, search, subject]);

  const openCreate = () => {
    setEditing(null);
    setForm({ ...EMPTY, subject_id: String(subjects[0]?.id || "") });
    setOpen(true);
  };

  const openEdit = (course) => {
    setEditing(course);
    setForm({
      subject_id: String(course.subject_id || ""),
      title: course.title || "",
      grade: Number(course.grade || 3),
      description: course.description || "",
      teacher_id: course.teacher_id ? String(course.teacher_id) : "",
      school_id: course.school_id ? String(course.school_id) : "",
      class_ids: [],
    });
    setOpen(true);
  };

  const submit = async () => {
    if (!form.subject_id || !form.title.trim()) {
      toast("Укажите предмет и название курса", "info");
      return;
    }
    const payload = {
      ...form,
      subject_id: Number(form.subject_id),
      grade: Number(form.grade),
      teacher_id: form.teacher_id ? Number(form.teacher_id) : null,
      school_id: form.school_id ? Number(form.school_id) : null,
      class_ids: form.class_ids,
    };
    try {
      await run(() => editing
        ? api.patch(`/admin/courses/${editing.id}`, payload)
        : api.post("/admin/courses", payload));
      setOpen(false);
      invalidate("/admin");
      await refresh();
      toast(editing ? "Курс обновлён" : "Курс создан", "success");
    } catch (err) {
      toast(err.message || "Не удалось сохранить курс", "error");
    }
  };

  const remove = async (course) => {
    if (!window.confirm(`Удалить курс «${course.title}»?`)) return;
    setBusy(`del-${course.id}`);
    try {
      await run(() => api.del(`/admin/courses/${course.id}`));
      invalidate("/admin");
      await refresh();
      toast("Курс удалён", "success");
    } catch (err) {
      toast(err.message || "Не удалось удалить курс", "error");
    } finally {
      setBusy("");
    }
  };

  const openDetail = async (course) => {
    setDetail({ course, topics: [], classes: [], class_ids: [] });
    setDetailLoading(true);
    try {
      const payload = await api.get(`/admin/courses/${course.id}`);
      setDetail(payload);
      setTopics(payload.topics || []);
      setClasses(payload.all_classes || []);
    } catch (err) {
      toast(err.message || "Не удалось открыть курс", "error");
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  };

  const saveDetail = async () => {
    if (!detail) return;
    setBusy("detail");
    try {
      const enabled = topics.filter((topic) => topic.enabled).map((topic) => topic.slug);
      await run(() => api.put(`/admin/courses/${detail.course.id}/topics`, {
        topics: enabled,
        class_ids: detail.class_ids,
      }));
      invalidate("/admin");
      await refresh();
      toast(`Курс сохранён: тем ${enabled.length}`, "success");
    } catch (err) {
      toast(err.message || "Не удалось сохранить курс", "error");
    } finally {
      setBusy("");
    }
  };

  const addTopic = async () => {
    if (!detail || !newTopic.title.trim()) return;
    setBusy("topic");
    try {
      const result = await run(() => api.post(`/admin/courses/${detail.course.id}/topics`, newTopic));
      setNewTopic({ title: "", description: "" });
      const payload = await api.get(`/admin/courses/${detail.course.id}`);
      setDetail(payload);
      setTopics(payload.topics || []);
      toast(`Тема добавлена: ${result.slug}`, "success");
    } catch (err) {
      toast(err.message || "Не удалось добавить тему", "error");
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Курсы"
        subtitle="Наборы тем для класса: учитель ведёт курс, ученики видят его в карте обучения."
        actions={<Button icon={Plus} onClick={openCreate}>Новый курс</Button>}
      />

      {error && <ErrorState error={error} onRetry={refresh} />}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={BookOpen} label="Курсов" value={courses.length} tone="iris" />
        <StatCard icon={Layers} label="Тем в курсах" value={courses.reduce((sum, course) => sum + Number(course.topics_count || 0), 0)} tone="cyan" />
        <StatCard icon={GraduationCap} label="Классов" value={courses.reduce((sum, course) => sum + Number(course.classes_count || 0), 0)} tone="green" />
        <StatCard icon={Users} label="Учителей" value={new Set(courses.map((course) => course.teacher_id).filter(Boolean)).size} tone="gold" />
      </div>

      <Card className="space-y-3 p-4">
        <SearchBox value={search} onChange={setSearch} placeholder="Название курса или учитель…" />
        <Select value={subject} onChange={(event) => setSubject(event.target.value)}>
          <option value="all">Все предметы</option>
          {subjects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </Select>
      </Card>

      {loading && !data ? (
        <div className="grid gap-3 sm:grid-cols-2">{Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-40" />)}</div>
      ) : visible.length === 0 ? (
        <Card>
          <EmptyState
            icon="🧭"
            title={courses.length ? "Ничего не нашлось" : "Курсов пока нет"}
            text={courses.length ? "Измените поиск или предмет." : "Создайте курс и добавьте в него темы."}
            action={<Button icon={Plus} onClick={openCreate}>Новый курс</Button>}
          />
        </Card>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {visible.map((course) => (
            <Card key={course.id} className="flex flex-col gap-3 p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold text-white">{course.title}</p>
                  <p className="mt-0.5 truncate text-[11px] text-mist-500">
                    {course.subject_icon} {course.subject_name} · {course.grade} класс
                  </p>
                </div>
                <Badge tone={course.is_active ? "green" : "rose"}>{course.is_active ? "активен" : "выключен"}</Badge>
              </div>
              <p className="line-clamp-2 min-h-[32px] text-[11px] leading-relaxed text-mist-500">
                {course.description || "Без описания"}
              </p>
              <div className="flex flex-wrap gap-1.5">
                <Badge tone="iris">{course.topics_count || 0} {plural(course.topics_count || 0, ["тема", "темы", "тем"])}</Badge>
                <Badge tone="cyan">{course.classes_count || 0} кл.</Badge>
                {(course.teacher_first || course.teacher_last) && (
                  <Badge tone="gold">{course.teacher_first} {course.teacher_last}</Badge>
                )}
              </div>
              <div className="mt-auto flex flex-wrap gap-1.5 pt-1">
                <Button size="sm" variant="ghost" icon={Layers} onClick={() => openDetail(course)}>Темы и классы</Button>
                <IconButton icon={Pencil} label="Изменить" onClick={() => openEdit(course)} />
                <IconButton icon={Trash2} label="Удалить" className="text-rose-300" loading={busy === `del-${course.id}`} onClick={() => remove(course)} />
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title={editing ? "Изменить курс" : "Новый курс"}
        description="Курс объединяет темы предмета для конкретного класса."
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>Отмена</Button>
            <Button icon={Check} loading={pending} onClick={submit}>{editing ? "Сохранить" : "Создать"}</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Название" className="sm:col-span-2">
            <Input value={form.title} onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))} placeholder="Математика: дроби" />
          </Field>
          <Field label="Предмет">
            <Select value={form.subject_id} onChange={(event) => setForm((current) => ({ ...current, subject_id: event.target.value }))}>
              <option value="">Выберите предмет</option>
              {subjects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </Select>
          </Field>
          <Field label="Класс">
            <Select value={form.grade} onChange={(event) => setForm((current) => ({ ...current, grade: Number(event.target.value) }))}>
              {GRADES.map((item) => <option key={item} value={item}>{item} класс</option>)}
            </Select>
          </Field>
          <Field label="Учитель">
            <Select value={form.teacher_id} onChange={(event) => setForm((current) => ({ ...current, teacher_id: event.target.value }))}>
              <option value="">Не назначен</option>
              {teachers.map((item) => <option key={item.id} value={item.id}>{item.first_name} {item.last_name} (@{item.login})</option>)}
            </Select>
          </Field>
          <Field label="Школа">
            <Select value={form.school_id} onChange={(event) => setForm((current) => ({ ...current, school_id: event.target.value }))}>
              <option value="">Не выбрана</option>
              {(data?.schools || []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </Select>
          </Field>
          <Field label="Описание" className="sm:col-span-2">
            <Textarea value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} placeholder="Чему посвящён курс…" />
          </Field>
          <Field label="Классы курса" hint="Ученики этих классов увидят курс." className="sm:col-span-2">
            <ClassPicker classes={allClasses} value={form.class_ids} onChange={(class_ids) => setForm((current) => ({ ...current, class_ids }))} />
          </Field>
        </div>
      </Modal>

      <Modal
        open={Boolean(detail)}
        onClose={() => setDetail(null)}
        title={detail?.course?.title || "Курс"}
        description="Отметьте темы и классы, которые входят в курс."
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setDetail(null)}>Закрыть</Button>
            <Button icon={Check} loading={pending && busy === "detail"} onClick={saveDetail}>Сохранить курс</Button>
          </>
        }
      >
        {detailLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <div className="space-y-5">
            <div>
              <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-mist-600">Темы предмета и класса</p>
              <div className="max-h-64 space-y-1 overflow-y-auto rounded-xl border border-white/8 bg-white/[0.02] p-2">
                {topics.length === 0 && <p className="px-2 py-3 text-xs text-mist-500">Тем пока нет — создайте новую ниже.</p>}
                {topics.map((topic, index) => (
                  <label key={topic.slug} className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 text-xs text-mist-200 hover:bg-white/5">
                    <input
                      type="checkbox"
                      checked={topic.enabled}
                      onChange={() => setTopics((current) => current.map((item, i) => i === index ? { ...item, enabled: !item.enabled } : item))}
                      className="h-4 w-4 accent-iris-500"
                    />
                    <span className="w-4 shrink-0 text-center">{topic.icon || "•"}</span>
                    <span className="min-w-0 flex-1 truncate">{topic.title}</span>
                    <span className="shrink-0 text-[10px] text-mist-600">{topic.grade} кл.</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-mist-600">Классы курса</p>
              <ClassPicker
                classes={classes}
                value={detail?.class_ids || []}
                onChange={(class_ids) => setDetail((current) => ({ ...current, class_ids }))}
              />
            </div>

            <div className="rounded-xl border border-white/8 bg-white/[0.02] p-3">
              <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-mist-600">Новая тема</p>
              <div className="grid gap-2 sm:grid-cols-[1fr_auto]">
                <Input value={newTopic.title} onChange={(event) => setNewTopic((current) => ({ ...current, title: event.target.value }))} placeholder="Название темы" />
                <Button size="sm" variant="ghost" icon={Plus} loading={pending && busy === "topic"} onClick={addTopic}>Добавить</Button>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
