import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  BookOpen,
  Check,
  Download,
  FileText,
  GraduationCap,
  Layers,
  Link2,
  Plus,
  RefreshCw,
  Sparkles,
  Trash2,
  Upload,
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
import { api, downloadFile, invalidate, openFile } from "../../lib/api";
import { formatDate, plural } from "../../lib/format";
import { SearchBox, Toggle } from "./shared";

const GRADES = Array.from({ length: 11 }, (_, index) => index + 1);

const EMPTY_FORM = {
  subject_id: "",
  grade: 3,
  title: "",
  author: "",
  publisher: "",
  year: "",
  description: "",
  auto_link: true,
  class_ids: [],
};

function sizeLabel(bytes) {
  const value = Number(bytes || 0);
  if (!value) return "—";
  if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} МБ`;
  return `${Math.max(1, Math.round(value / 1024))} КБ`;
}

function ClassPicker({ classes, value, onChange }) {
  return (
    <div className="max-h-52 space-y-1 overflow-y-auto rounded-xl border border-white/8 bg-white/[0.02] p-2">
      {classes.length === 0 && <p className="px-2 py-3 text-xs text-mist-500">Классов пока нет.</p>}
      {classes.map((klass) => {
        const checked = value.includes(klass.id);
        return (
          <label
            key={klass.id}
            className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 text-xs text-mist-200 hover:bg-white/5"
          >
            <input
              type="checkbox"
              checked={checked}
              onChange={() =>
                onChange(checked ? value.filter((id) => id !== klass.id) : [...value, klass.id])
              }
              className="h-4 w-4 accent-iris-500"
            />
            <span className="min-w-0 flex-1 truncate">
              {klass.school_name} · {klass.title}
            </span>
            <span className="shrink-0 text-[10px] text-mist-600">{klass.students_count || 0} уч.</span>
          </label>
        );
      })}
    </div>
  );
}

export function AdminTextbooks() {
  const navigate = useNavigate();
  const { data, loading, error, refresh } = useApi("/admin/textbooks");
  const { data: orgs } = useApi("/admin/orgs", { ttl: 120_000 });
  const [search, setSearch] = useState("");
  const [subject, setSubject] = useState("all");
  const [grade, setGrade] = useState("all");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState("");
  const { pending, run } = useAction();

  const textbooks = data?.textbooks || [];
  const subjects = orgs?.subjects || [];
  const classes = orgs?.classes || [];

  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    return textbooks.filter((book) => {
      if (subject !== "all" && String(book.subject_id) !== String(subject)) return false;
      if (grade !== "all" && String(book.grade) !== String(grade)) return false;
      if (!query) return true;
      return `${book.title} ${book.author || ""} ${book.subject_name || ""} ${book.original_name || ""}`
        .toLowerCase()
        .includes(query);
    });
  }, [textbooks, search, subject, grade]);

  useEffect(() => {
    if (!orgs) return;
    setForm((current) =>
      current.subject_id ? current : { ...current, subject_id: String(orgs.subjects?.[0]?.id || "") },
    );
  }, [orgs]);

  const upload = async () => {
    if (!file) {
      toast("Выберите PDF-файл книги", "info");
      return;
    }
    if (!form.subject_id) {
      toast("Выберите предмет", "info");
      return;
    }
    const payload = new FormData();
    payload.append("file", file);
    payload.append("subject_id", form.subject_id);
    payload.append("grade", form.grade);
    payload.append("title", form.title);
    payload.append("author", form.author);
    payload.append("publisher", form.publisher);
    payload.append("year", form.year);
    payload.append("description", form.description);
    if (form.auto_link) payload.append("auto_link", "1");
    form.class_ids.forEach((id) => payload.append("class_ids", id));
    try {
      const result = await run(() => api.form("/admin/textbooks", payload));
      setOpen(false);
      setFile(null);
      setForm({ ...EMPTY_FORM, subject_id: form.subject_id });
      invalidate("/admin");
      await refresh();
      toast(
        `Книга загружена: ${result.pages || 0} стр., тем привязано ${result.topics_linked || 0}`,
        "success",
      );
      if (result.textbook_id) navigate(`/app/admin/textbooks/${result.textbook_id}`);
    } catch (err) {
      toast(err.message || "Не удалось загрузить книгу", "error");
    }
  };

  const remove = async (book) => {
    if (!window.confirm(`Удалить пособие «${book.title}»? Это действие необратимо.`)) return;
    setBusy(`delete-${book.id}`);
    try {
      await run(() => api.del(`/admin/textbooks/${book.id}`));
      invalidate("/admin");
      await refresh();
      toast("Пособие удалено", "success");
    } catch (err) {
      toast(err.message || "Не удалось удалить пособие", "error");
    } finally {
      setBusy("");
    }
  };

  const downloadPdf = async (book) => {
    setBusy(`pdf-${book.id}`);
    try {
      await downloadFile(`/admin/textbooks/${book.id}/file`, book.original_name || `${book.title}.pdf`);
    } catch (err) {
      toast(err.message || "Не удалось скачать PDF", "error");
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Пособия и книги"
        subtitle="Загрузка PDF, привязка тем и выдача книг классам. Всё, что здесь появится, сразу доступно в библиотеке учеников."
        actions={
          <Button icon={Upload} onClick={() => setOpen(true)}>Загрузить книгу</Button>
        }
      />

      {error && <ErrorState error={error} onRetry={refresh} />}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={BookOpen} label="Пособий" value={textbooks.length} tone="iris" />
        <StatCard icon={Layers} label="С темами" value={textbooks.filter((book) => book.topics_count > 0).length} tone="cyan" />
        <StatCard icon={GraduationCap} label="Классов" value={new Set(textbooks.map((book) => book.grade)).size} tone="green" />
        <StatCard icon={FileText} label="Страниц" value={textbooks.reduce((sum, book) => sum + Number(book.pages || 0), 0).toLocaleString("ru-RU")} tone="gold" />
      </div>

      <Card className="space-y-3 p-4">
        <SearchBox value={search} onChange={setSearch} placeholder="Название, автор, предмет…" />
        <div className="grid grid-cols-2 gap-2">
          <Select value={subject} onChange={(event) => setSubject(event.target.value)}>
            <option value="all">Все предметы</option>
            {subjects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </Select>
          <Select value={grade} onChange={(event) => setGrade(event.target.value)}>
            <option value="all">Все классы</option>
            {GRADES.map((item) => <option key={item} value={item}>{item} класс</option>)}
          </Select>
        </div>
      </Card>

      {loading && !data ? (
        <div className="space-y-2">{Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className="h-24" />)}</div>
      ) : visible.length === 0 ? (
        <Card>
          <EmptyState
            icon="📚"
            title={textbooks.length ? "Ничего не нашлось" : "Пособий пока нет"}
            text={textbooks.length ? "Измените поиск или фильтры." : "Загрузите первую книгу — ученики увидят её в библиотеке."}
            action={<Button icon={Upload} onClick={() => setOpen(true)}>Загрузить книгу</Button>}
          />
        </Card>
      ) : (
        <Card className="divide-y divide-white/6 p-2">
          {visible.map((book) => (
            <div key={book.id} className="flex flex-col gap-3 rounded-xl px-3 py-3 transition hover:bg-white/[0.025] sm:flex-row sm:items-center">
              <div className="flex min-w-0 flex-1 items-start gap-3">
                <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-white/8 bg-white/5 text-lg">
                  {book.subject_icon || "📘"}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      to={`/app/admin/textbooks/${book.id}`}
                      className="min-w-0 text-sm font-bold text-white hover:text-iris-300"
                    >
                      {book.title}
                    </Link>
                    <Badge tone="iris">{book.grade} класс</Badge>
                    {book.topics_count > 0 ? (
                      <Badge tone="green">{book.topics_count} {plural(book.topics_count, ["тема", "темы", "тем"])}</Badge>
                    ) : (
                      <Badge tone="gold">без тем</Badge>
                    )}
                  </div>
                  <p className="mt-0.5 truncate text-[11px] text-mist-500">
                    {book.subject_name || "Без предмета"}
                    {book.author ? ` · ${book.author}` : ""}
                    {book.original_name ? ` · ${book.original_name}` : ""}
                  </p>
                  <p className="mt-0.5 text-[10px] text-mist-600">
                    {book.pages || 0} стр. · {sizeLabel(book.size_bytes)} · загружено {formatDate(book.created_at, { year: true })}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-1.5 sm:justify-end">
                <Button size="sm" variant="ghost" icon={BookOpen} onClick={() => navigate(`/app/admin/textbooks/${book.id}`)}>Открыть</Button>
                <IconButton icon={Download} label="Скачать PDF" loading={busy === `pdf-${book.id}`} onClick={() => downloadPdf(book)} />
                <IconButton icon={Trash2} label="Удалить" className="text-rose-300" loading={busy === `delete-${book.id}`} onClick={() => remove(book)} />
              </div>
            </div>
          ))}
        </Card>
      )}

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Загрузить книгу"
        description="PDF-пособие появится в каталоге и в библиотеке выбранных классов."
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>Отмена</Button>
            <Button icon={Upload} loading={pending} onClick={upload}>Загрузить</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="PDF-файл" hint="До 80 МБ. Сканы тоже подойдут." className="sm:col-span-2">
            <label className="flex cursor-pointer flex-col items-center gap-2 rounded-2xl border border-dashed border-white/15 bg-white/[0.02] px-4 py-6 text-center transition hover:border-iris-400/50 hover:bg-white/[0.04]">
              <Upload size={22} className="text-iris-300" />
              <span className="text-sm font-semibold text-white">
                {file ? file.name : "Выберите PDF-файл"}
              </span>
              <span className="text-[11px] text-mist-500">
                {file ? sizeLabel(file.size) : "Нажмите, чтобы выбрать файл"}
              </span>
              <input
                type="file"
                accept="application/pdf,.pdf"
                className="hidden"
                onChange={(event) => setFile(event.target.files?.[0] || null)}
              />
            </label>
          </Field>
          <Field label="Название" hint="Если пусто — возьмём имя файла.">
            <Input value={form.title} onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))} placeholder="Математика. 3 класс" />
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
          <Field label="Автор">
            <Input value={form.author} onChange={(event) => setForm((current) => ({ ...current, author: event.target.value }))} placeholder="И. И. Иванов" />
          </Field>
          <Field label="Издательство">
            <Input value={form.publisher} onChange={(event) => setForm((current) => ({ ...current, publisher: event.target.value }))} placeholder="НИО" />
          </Field>
          <Field label="Год">
            <Input value={form.year} onChange={(event) => setForm((current) => ({ ...current, year: event.target.value }))} placeholder="2025" />
          </Field>
          <Field label="Описание" className="sm:col-span-2">
            <Textarea value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} placeholder="Краткое описание для библиотеки…" />
          </Field>
          <div className="sm:col-span-2">
            <Toggle
              value={form.auto_link}
              onChange={(value) => setForm((current) => ({ ...current, auto_link: value }))}
              label="Автоматически найти темы в PDF"
              text="Содержание распознаётся, темы создаются и привязываются к страницам."
            />
          </div>
          <Field label="Показать классам" hint="Необязательно. Книга появится в библиотеке учеников выбранных классов." className="sm:col-span-2">
            <ClassPicker
              classes={classes}
              value={form.class_ids}
              onChange={(class_ids) => setForm((current) => ({ ...current, class_ids }))}
            />
          </Field>
        </div>
      </Modal>
    </div>
  );
}

export function AdminTextbookDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, loading, error, refresh } = useApi(`/admin/textbooks/${id}`);
  const { data: orgs } = useApi("/admin/orgs", { ttl: 120_000 });
  const [form, setForm] = useState(null);
  const [rows, setRows] = useState([]);
  const [manual, setManual] = useState("");
  const [busy, setBusy] = useState("");
  const { pending, run } = useAction();

  const textbook = data?.textbook;
  const topics = data?.topics || [];

  useEffect(() => {
    if (!textbook) return;
    setForm({
      title: textbook.title || "",
      author: textbook.author || "",
      publisher: textbook.publisher || "",
      year: textbook.year || "",
      description: textbook.description || "",
      subject_id: String(textbook.subject_id || ""),
      grade: Number(textbook.grade || 3),
    });
  }, [textbook]);

  useEffect(() => {
    setRows(topics.map((topic) => ({
      slug: topic.slug,
      title: topic.title,
      grade: topic.grade,
      icon: topic.icon,
      page: topic.page || "",
      page_end: topic.page_end || "",
    })));
  }, [data]);

  const saveMeta = async () => {
    setBusy("meta");
    try {
      await run(() => api.patch(`/admin/textbooks/${id}`, {
        ...form,
        grade: Number(form.grade),
        subject_id: Number(form.subject_id),
      }));
      invalidate("/admin");
      await refresh();
      toast("Сведения о пособии обновлены", "success");
    } catch (err) {
      toast(err.message || "Не удалось сохранить", "error");
    } finally {
      setBusy("");
    }
  };

  const importPdf = async () => {
    setBusy("import");
    try {
      const result = await run(() => api.post(`/admin/textbooks/${id}/import-topics`, {}));
      await refresh();
      toast(result.message || "Темы обновлены", "success");
    } catch (err) {
      toast(err.message || "Не удалось распознать содержание", "error");
    } finally {
      setBusy("");
    }
  };

  const saveTopics = async () => {
    setBusy("topics");
    try {
      const payload = rows
        .filter((row) => Number(row.page) > 0)
        .map((row) => ({
          slug: row.slug,
          page: Number(row.page),
          page_end: Number(row.page_end) || Number(row.page),
        }));
      const result = await run(() => api.put(`/admin/textbooks/${id}/topics`, { topics: payload }));
      await refresh();
      toast(`Привязано тем: ${result.linked}`, "success");
    } catch (err) {
      toast(err.message || "Не удалось сохранить привязку", "error");
    } finally {
      setBusy("");
    }
  };

  const addManual = async () => {
    if (!manual.trim()) return;
    setBusy("manual");
    try {
      const result = await run(() => api.post(`/admin/textbooks/${id}/topics/manual`, { text: manual }));
      setManual("");
      await refresh();
      toast(`Добавлено тем: ${result.linked}`, "success");
    } catch (err) {
      toast(err.message || "Не удалось разобрать список", "error");
    } finally {
      setBusy("");
    }
  };

  const openPdf = async () => {
    try {
      await openFile(`/admin/textbooks/${id}/file`);
    } catch (err) {
      toast(err.message || "Не удалось открыть PDF", "error");
    }
  };

  const downloadPdf = async () => {
    try {
      await downloadFile(`/admin/textbooks/${id}/file`, textbook?.original_name || "book.pdf");
    } catch (err) {
      toast(err.message || "Не удалось скачать PDF", "error");
    }
  };

  const removeTextbook = async () => {
    if (!window.confirm(`Удалить пособие «${textbook?.title || ""}»?`)) return;
    try {
      await run(() => api.del(`/admin/textbooks/${id}`));
      invalidate("/admin");
      toast("Пособие удалено", "success");
      navigate("/app/admin/textbooks");
    } catch (err) {
      toast(err.message || "Не удалось удалить пособие", "error");
    }
  };

  if (loading && !data) {
    return <div className="space-y-4"><Skeleton className="h-16 w-full" /><Skeleton className="h-96 w-full" /></div>;
  }

  if (error && !data) {
    return <ErrorState error={error} onRetry={refresh} />;
  }

  return (
    <div className="space-y-6">
      <button onClick={() => navigate("/app/admin/textbooks")} className="inline-flex items-center gap-1.5 text-xs font-semibold text-mist-400 hover:text-white">
        <ArrowLeft size={15} /> Все пособия
      </button>

      <PageHeader
        title={textbook?.title || "Пособие"}
        subtitle={`${textbook?.subject_name || "Предмет"} · ${textbook?.grade} класс · ${textbook?.pages || 0} стр.`}
        actions={
          <>
            <Button variant="ghost" icon={BookOpen} onClick={openPdf}>Открыть PDF</Button>
            <Button variant="ghost" icon={Download} onClick={downloadPdf}>Скачать</Button>
            <Button variant="ghost" icon={Trash2} className="text-rose-300" onClick={removeTextbook}>Удалить</Button>
          </>
        }
      />

      <div className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
        <Card className="space-y-4 p-5 sm:p-6">
          <h2 className="font-display text-lg font-semibold text-white">Сведения о пособии</h2>
          {form && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Название" className="sm:col-span-2">
                <Input value={form.title} onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))} />
              </Field>
              <Field label="Предмет">
                <Select value={form.subject_id} onChange={(event) => setForm((current) => ({ ...current, subject_id: event.target.value }))}>
                  <option value="">Выберите предмет</option>
                  {(orgs?.subjects || []).map((item) => (
                    <option key={item.id} value={item.id}>{item.name}</option>
                  ))}
                </Select>
              </Field>
              <Field label="Класс">
                <Input type="number" min={1} max={11} value={form.grade} onChange={(event) => setForm((current) => ({ ...current, grade: event.target.value }))} />
              </Field>
              <Field label="Автор">
                <Input value={form.author} onChange={(event) => setForm((current) => ({ ...current, author: event.target.value }))} />
              </Field>
              <Field label="Издательство">
                <Input value={form.publisher} onChange={(event) => setForm((current) => ({ ...current, publisher: event.target.value }))} />
              </Field>
              <Field label="Год">
                <Input value={form.year} onChange={(event) => setForm((current) => ({ ...current, year: event.target.value }))} />
              </Field>
              <Field label="Описание" className="sm:col-span-2">
                <Textarea value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} />
              </Field>
              <div className="sm:col-span-2">
                <Button icon={Check} loading={pending && busy === "meta"} onClick={saveMeta}>Сохранить сведения</Button>
              </div>
            </div>
          )}
        </Card>

        <Card className="space-y-4 p-5 sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-display text-lg font-semibold text-white">Темы и страницы</h2>
            <Button size="sm" variant="ghost" icon={Sparkles} loading={pending && busy === "import"} onClick={importPdf}>
              Найти в PDF
            </Button>
          </div>
          <p className="text-xs leading-relaxed text-mist-500">
            Укажите страницу начала темы. Поле «до» необязательно — тогда тема занимает одну страницу.
          </p>
          <div className="max-h-[420px] space-y-1.5 overflow-y-auto pr-1">
            {rows.length === 0 && <p className="text-xs text-mist-500">Для этого предмета и класса тем пока нет.</p>}
            {rows.map((row, index) => (
              <div key={row.slug} className="flex items-center gap-2 rounded-xl border border-white/7 bg-white/[0.02] px-2.5 py-2">
                <span className="w-5 shrink-0 text-center text-sm">{row.icon || "•"}</span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-semibold text-white">{row.title}</p>
                  <p className="truncate text-[10px] text-mist-600">{row.slug}</p>
                </div>
                <Input
                  type="number"
                  min={0}
                  placeholder="стр."
                  value={row.page}
                  onChange={(event) => setRows((current) => current.map((item, i) => i === index ? { ...item, page: event.target.value } : item))}
                  className="!w-16 !px-2 !py-1.5 text-center text-xs"
                />
                <Input
                  type="number"
                  min={0}
                  placeholder="до"
                  value={row.page_end}
                  onChange={(event) => setRows((current) => current.map((item, i) => i === index ? { ...item, page_end: event.target.value } : item))}
                  className="!w-16 !px-2 !py-1.5 text-center text-xs"
                />
              </div>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button icon={Link2} loading={pending && busy === "topics"} onClick={saveTopics}>Сохранить привязку</Button>
            <Badge tone="cyan">{rows.filter((row) => Number(row.page) > 0).length} привязано</Badge>
          </div>

          <div className="border-t border-white/8 pt-4">
            <Field label="Добавить темы вручную" hint="По одной строке: «Название — 12».">
              <Textarea
                value={manual}
                onChange={(event) => setManual(event.target.value)}
                placeholder={"Сложение чисел — 12\nВычитание чисел — 18"}
              />
            </Field>
            <div className="mt-2">
              <Button size="sm" variant="ghost" icon={Plus} loading={pending && busy === "manual"} onClick={addManual}>
                Добавить темы
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
