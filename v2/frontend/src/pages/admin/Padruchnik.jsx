import { useState } from "react";
import {
  BookOpen,
  Download,
  ExternalLink,
  FileUp,
  GraduationCap,
  Search,
  Sparkles,
} from "lucide-react";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Input,
  Modal,
  PageHeader,
  Select,
  Skeleton,
  StatCard,
} from "../../components/ui";
import { useAction, useApi, toast } from "../../lib/hooks";
import { api, invalidate } from "../../lib/api";

const GRADES = Array.from({ length: 11 }, (_, index) => index + 1);

export function AdminPadruchnik() {
  const { data: orgs } = useApi("/admin/orgs", { ttl: 120_000 });
  const [query, setQuery] = useState("");
  const [grade, setGrade] = useState("");
  const [page, setPage] = useState(0);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [target, setTarget] = useState(null);
  const [form, setForm] = useState({ subject_id: "", grade: 3, class_ids: [] });
  const [uploadOpen, setUploadOpen] = useState(false);
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState("");
  const { pending, run } = useAction();

  const subjects = orgs?.subjects || [];
  const classes = orgs?.classes || [];

  const search = async (nextPage = 0) => {
    if (!query.trim() && !grade) {
      toast("Введите название или выберите класс", "info");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (query.trim()) params.set("q", query.trim());
      if (grade) params.set("grade", grade);
      params.set("page", String(nextPage));
      const payload = await api.get(`/padruchnik/search?${params.toString()}`);
      setResult(payload);
      setPage(nextPage);
    } catch (err) {
      setError(err);
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const openImport = (book) => {
    setTarget(book);
    setForm({
      subject_id: String(subjects[0]?.id || ""),
      grade: book.grade || 3,
      class_ids: [],
    });
    setFile(null);
    setUploadOpen(false);
  };

  const importBook = async () => {
    if (!target || !form.subject_id) {
      toast("Выберите предмет", "info");
      return;
    }
    setBusy("import");
    try {
      const payload = await run(() => api.post("/padruchnik/import", {
        book_id: target.id,
        subject_id: Number(form.subject_id),
        grade: Number(form.grade),
        class_ids: form.class_ids,
      }));
      invalidate("/admin");
      toast(`«${payload.title || target.title}» добавлено: ${payload.pages || 0} стр.`, "success");
      setTarget(null);
    } catch (err) {
      toast(err.message || "Не удалось импортировать пособие", "error");
    } finally {
      setBusy("");
    }
  };

  const uploadBook = async () => {
    if (!target || !file) {
      toast("Выберите PDF-файл", "info");
      return;
    }
    const payload = new FormData();
    payload.append("file", file);
    payload.append("book_id", target.id);
    payload.append("subject_id", form.subject_id);
    payload.append("grade", form.grade);
    form.class_ids.forEach((id) => payload.append("class_ids", id));
    setBusy("upload");
    try {
      const result = await run(() => api.form("/padruchnik/upload", payload));
      invalidate("/admin");
      toast(`PDF загружен: ${result.pages || 0} стр.`, "success");
      setTarget(null);
      setFile(null);
    } catch (err) {
      toast(err.message || "Не удалось загрузить PDF", "error");
    } finally {
      setBusy("");
    }
  };

  const items = result?.items || [];
  const total = result?.total;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Пособия e-padruchnik"
        subtitle="Найдите учебник в каталоге и добавьте его в пособия. Если портал не отдаёт PDF, загрузите файл вручную."
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={BookOpen} label="В каталоге" value={total != null ? total : "—"} tone="iris" />
        <StatCard icon={GraduationCap} label="Класс" value={grade || "все"} tone="cyan" />
        <StatCard icon={Search} label="Найдено" value={items.length} tone="green" />
        <StatCard icon={Sparkles} label="Источник" value={result?.source || "—"} tone="gold" />
      </div>

      <Card className="space-y-3 p-4">
        <div className="flex flex-col gap-2 sm:flex-row">
          <div className="min-w-0 flex-1">
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && search(0)}
              placeholder="Название, автор или предмет…"
            />
          </div>
          <div className="w-full sm:w-40">
            <Select value={grade} onChange={(event) => setGrade(event.target.value)}>
              <option value="">Все классы</option>
              {GRADES.map((item) => <option key={item} value={item}>{item} класс</option>)}
            </Select>
          </div>
          <Button icon={Search} loading={loading} onClick={() => search(0)}>Искать</Button>
        </div>
        <p className="text-[11px] text-mist-600">
          Каталог работает даже там, где портал не пускает сервер. PDF можно загрузить вручную.
        </p>
      </Card>

      {error && <ErrorState error={error} onRetry={() => search(page)} />}

      {loading ? (
        <div className="space-y-2">{Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className="h-20" />)}</div>
      ) : !result ? (
        <Card>
          <EmptyState
            icon="🔎"
            title="Найдите пособие"
            text="Введите название или выберите класс — покажем книги из каталога e-padruchnik."
          />
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <EmptyState
            icon="📭"
            title="Ничего не найдено"
            text={result.error || "Попробуйте другое название или класс."}
          />
        </Card>
      ) : (
        <Card className="divide-y divide-white/6 p-2">
          {items.map((book) => (
            <div key={book.id} className="flex flex-col gap-3 rounded-xl px-3 py-3 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="min-w-0 text-sm font-bold text-white">{book.title}</p>
                  {book.grade ? <Badge tone="iris">{book.grade} класс</Badge> : null}
                  {book.year ? <Badge>{book.year}</Badge> : null}
                </div>
                <p className="mt-0.5 truncate text-[11px] text-mist-500">
                  {book.author || "Автор не указан"}
                  {book.language ? ` · язык ${book.language}` : ""}
                  {book.level ? ` · уровень ${book.level}` : ""}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-1.5 sm:justify-end">
                {book.pdf_url ? (
                  <a href={book.pdf_url} target="_blank" rel="noreferrer" className="btn btn-ghost">
                    <ExternalLink size={15} /> PDF
                  </a>
                ) : null}
                <Button size="sm" icon={Download} onClick={() => openImport(book)}>Добавить</Button>
              </div>
            </div>
          ))}
        </Card>
      )}

      {result && (
        <div className="flex items-center justify-between gap-3">
          <Button size="sm" variant="ghost" disabled={page === 0} onClick={() => search(Math.max(0, page - 1))}>
            Назад
          </Button>
          <span className="text-[11px] text-mist-600">Страница {page + 1}</span>
          <Button size="sm" variant="ghost" disabled={!result.has_next} onClick={() => search(page + 1)}>
            Дальше
          </Button>
        </div>
      )}

      <Modal
        open={Boolean(target)}
        onClose={() => setTarget(null)}
        title="Добавить пособие"
        description={target?.title}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setTarget(null)}>Отмена</Button>
            {uploadOpen ? (
              <Button icon={FileUp} loading={pending && busy === "upload"} onClick={uploadBook}>Загрузить PDF</Button>
            ) : (
              <Button icon={Download} loading={pending && busy === "import"} onClick={importBook}>Импортировать</Button>
            )}
          </>
        }
      >
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
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
          </div>

          <Field label="Показать классам" hint="Необязательно: книга появится в библиотеке выбранных классов.">
            <div className="max-h-40 space-y-1 overflow-y-auto rounded-xl border border-white/8 bg-white/[0.02] p-2">
              {classes.map((klass) => {
                const checked = form.class_ids.includes(klass.id);
                return (
                  <label key={klass.id} className="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-1.5 text-xs text-mist-200 hover:bg-white/5">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => setForm((current) => ({
                        ...current,
                        class_ids: checked
                          ? current.class_ids.filter((id) => id !== klass.id)
                          : [...current.class_ids, klass.id],
                      }))}
                      className="h-4 w-4 accent-iris-500"
                    />
                    <span className="min-w-0 flex-1 truncate">{klass.school_name} · {klass.title}</span>
                  </label>
                );
              })}
            </div>
          </Field>

          <div className="rounded-xl border border-white/8 bg-white/[0.02] p-3">
            <button
              type="button"
              onClick={() => setUploadOpen((value) => !value)}
              className="flex w-full items-center justify-between gap-3 text-left"
            >
              <div>
                <p className="text-xs font-bold text-white">Портал не отдаёт PDF?</p>
                <p className="mt-0.5 text-[11px] text-mist-500">Загрузите файл вручную — темы распознаются автоматически.</p>
              </div>
              <Badge tone={uploadOpen ? "green" : "gold"}>{uploadOpen ? "включено" : "вручную"}</Badge>
            </button>
            {uploadOpen && (
              <label className="mt-3 flex cursor-pointer flex-col items-center gap-1.5 rounded-xl border border-dashed border-white/15 px-4 py-4 text-center hover:border-iris-400/50">
                <FileUp size={20} className="text-iris-300" />
                <span className="text-xs font-semibold text-white">{file ? file.name : "Выберите PDF-файл"}</span>
                <input
                  type="file"
                  accept="application/pdf,.pdf"
                  className="hidden"
                  onChange={(event) => setFile(event.target.files?.[0] || null)}
                />
              </label>
            )}
          </div>
        </div>
      </Modal>
    </div>
  );
}
