import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Bookmark,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  FileText,
  GraduationCap,
  Heart,
  Library,
  Sparkles,
  Star,
  ZoomIn,
  ZoomOut,
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
import { api, invalidate, objectUrl } from "../lib/api";
import { formatDate, plural, subjectColor } from "../lib/format";

function BookCard({ book }) {
  const tone = subjectColor(book.subject_name === "Математика" ? "indigo" : "cyan");
  return (
    <Link
      to={`/app/library/${book.id}`}
      className="card card-hover group relative overflow-hidden p-5"
      style={{ background: `linear-gradient(150deg, ${tone.soft}, rgba(255,255,255,.015))` }}
    >
      <div className="flex items-start justify-between gap-3">
        <span className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-ink-900/40 text-2xl">
          {book.subject_icon || "📘"}
        </span>
        <div className="flex flex-col items-end gap-1.5">
          {book.grade ? <Badge>{book.grade} класс</Badge> : null}
          {book.pages ? <span className="text-[10px] font-bold uppercase tracking-wider text-mist-600">{book.pages} стр.</span> : null}
        </div>
      </div>
      <h3 className="mt-4 font-display text-[0.98rem] font-semibold leading-snug text-white">{book.title}</h3>
      <p className="mt-1 truncate text-xs text-mist-500">{book.author || "Учебное пособие"}</p>
      <p className="mt-2 line-clamp-2 text-[11px] leading-relaxed text-mist-500">{book.description}</p>
      <div className="mt-4 flex items-center justify-between text-[11px] font-semibold text-mist-600">
        <span>{book.topics_count ? `${book.topics_count} ${plural(book.topics_count, ["тема", "темы", "тем"])}` : "для чтения"}</span>
        <span className="inline-flex items-center gap-1 text-iris-300 opacity-0 transition group-hover:opacity-100">
          Открыть <ArrowRight size={12} />
        </span>
      </div>
    </Link>
  );
}

export function LibraryPage() {
  const { data, loading, error, refresh } = useApi("/library");
  const [tab, setTab] = useState("books");
  const [search, setSearch] = useState("");
  const { pending, run } = useAction();

  const books = data?.books || [];
  const recommendations = data?.recommendations || [];
  const active = recommendations.filter((item) => !item.done);

  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return books;
    return books.filter((book) =>
      `${book.title} ${book.author} ${book.description} ${book.subject_name}`.toLowerCase().includes(query),
    );
  }, [books, search]);

  const complete = async (rec) => {
    try {
      await run(() => api.post(`/library/recommendations/${rec.id}/done`, {}));
      invalidate("/library");
      await refresh();
      toast("Отмечено как прочитанное", "success");
    } catch (err) {
      toast(err.message || "Не удалось обновить", "error");
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Библиотека"
        subtitle="Учебники и пособия, подобранные под класс. Рекомендации учителя — отдельно, чтобы не потерялись."
        actions={<Badge tone="iris"><Library size={12} /> {books.length} {plural(books.length, ["книга", "книги", "книг"])}</Badge>}
      />

      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard icon={BookOpen} label="Книг доступно" value={books.length} tone="iris" />
        <StatCard icon={Bookmark} label="Активные рекомендации" value={active.length} hint={active[0]?.note || "От учителя"} tone="gold" />
        <StatCard icon={CheckCircle2} label="Прочитано по совету" value={data?.stats?.done || 0} tone="green" />
      </div>

      <Tabs
        tabs={[
          { key: "books", label: "Книги", count: books.length },
          { key: "recs", label: "Рекомендации", count: recommendations.length },
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === "books" && (
        <Card className="p-4 sm:p-5">
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Найти книгу или автора…"
            className="field"
          />
        </Card>
      )}

      {error && <ErrorState error={error} onRetry={refresh} />}

      {loading && !data && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-52" />)}
        </div>
      )}

      {tab === "books" && !loading && visible.length === 0 && (
        <Card>
          <EmptyState
            icon="📚"
            title={books.length ? "Ничего не нашлось" : "Библиотека пока пуста"}
            text={books.length ? "Попробуйте другой запрос." : "Учитель добавит пособия — они появятся здесь автоматически."}
            action={books.length ? <Button variant="ghost" onClick={() => setSearch("")}>Сбросить</Button> : null}
          />
        </Card>
      )}

      {tab === "books" && visible.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {visible.map((book) => <BookCard key={book.id} book={book} />)}
        </div>
      )}

      {tab === "recs" && (
        <div className="space-y-3">
          {recommendations.length === 0 && (
            <Card>
              <EmptyState
                icon="💡"
                title="Рекомендаций пока нет"
                text="Когда учитель порекомендует книгу или тему, они появятся здесь."
              />
            </Card>
          )}
          {recommendations.map((rec) => (
            <Card key={rec.id} className="p-5">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
                <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-xl">📖</span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={rec.done ? "green" : "gold"}>{rec.done ? "прочитано" : "рекомендация"}</Badge>
                    {rec.topic_title ? <Badge tone="cyan">{rec.topic_title}</Badge> : null}
                  </div>
                  <p className="mt-2 font-display text-sm font-semibold text-white">{rec.title || "Книга"}</p>
                  {rec.note ? <p className="mt-1 text-xs leading-relaxed text-mist-500">{rec.note}</p> : null}
                  <p className="mt-1 text-[11px] text-mist-600">
                    {rec.teacher_first ? `${rec.teacher_first} ${rec.teacher_last || ""}` : "Учитель"}
                    {rec.created_at ? ` · ${formatDate(rec.created_at)}` : ""}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Link to={`/app/library/${rec.book_id}`}><Button size="sm" variant="ghost" icon={BookOpen}>Открыть</Button></Link>
                  {!rec.done && (
                    <Button size="sm" icon={CheckCircle2} loading={pending} onClick={() => complete(rec)}>Прочитано</Button>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

export function BookPage() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const numeric = Number(id);
  const isTextbook = numeric < 0;
  const path = isTextbook ? `/books/${Math.abs(numeric)}` : `/library/books/${numeric}`;
  const { data, loading, error, refresh } = useApi(path);
  const requestedPage = Math.max(1, Number(searchParams.get("page")) || 1);
  const [page, setPage] = useState(requestedPage);
  const [pageSrc, setPageSrc] = useState("");
  const [pageError, setPageError] = useState("");
  const [zoom, setZoom] = useState(false);
  const [pageDraft, setPageDraft] = useState(String(requestedPage));
  const readerRef = useRef(null);
  const { pending, run } = useAction();

  const book = data?.book;
  const topics = data?.topics || [];
  const recommendations = (data?.recommendations || []).filter((item) => !item.done);
  const pages = Number(book?.pages || 0);

  useEffect(() => {
    setPage(requestedPage);
  }, [numeric, requestedPage]);

  useEffect(() => {
    if (pages > 0) setPage((value) => Math.min(Math.max(1, value), pages));
  }, [pages]);

  useEffect(() => {
    setPageDraft(String(page));
  }, [page]);

  // Пришли из темы по ссылке «Читать тему · с. N» — сразу показываем страницу.
  useEffect(() => {
    if (!book || !searchParams.get("page")) return undefined;
    const timer = window.setTimeout(() => {
      readerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 120);
    return () => window.clearTimeout(timer);
  }, [book, numeric, requestedPage]);

  const commitPage = () => {
    const next = Math.round(Number(pageDraft));
    if (!Number.isFinite(next) || next < 1) {
      setPageDraft(String(page));
      return;
    }
    setPage(Math.min(pages || next, next));
  };

  useEffect(() => {
    if (!book || pages <= 0) {
      setPageSrc("");
      return undefined;
    }
    let alive = true;
    let url = "";
    setPageError("");
    setPageSrc("");
    objectUrl(`/books/${book.textbook_id || Math.abs(numeric)}/page/${page}.png`)
      .then((next) => {
        if (!alive) {
          URL.revokeObjectURL(next);
          return;
        }
        url = next;
        setPageSrc(next);
      })
      .catch((err) => { if (alive) setPageError(err.message || "Не удалось загрузить страницу"); });
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [book, page, pages, numeric]);

  const markDone = async (rec) => {
    try {
      await run(() => api.post(`/library/recommendations/${rec.id}/done`, {}));
      invalidate("/library");
      await refresh();
      toast("Рекомендация выполнена", "success");
    } catch (err) {
      toast(err.message || "Не удалось обновить", "error");
    }
  };

  if (loading && !data) {
    return <div className="space-y-4"><Skeleton className="h-52 w-full" /><Skeleton className="h-72 w-full" /></div>;
  }

  if (error || !book) {
    return (
      <div className="space-y-4">
        <Link to="/app/library" className="inline-flex items-center gap-1.5 text-sm font-semibold text-mist-500 hover:text-white"><ArrowLeft size={15} /> К библиотеке</Link>
        <ErrorState error={error} onRetry={refresh} />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <Link to="/app/library" className="inline-flex items-center gap-1.5 text-sm font-semibold text-mist-500 hover:text-white">
        <ArrowLeft size={15} /> К библиотеке
      </Link>

      <Card className="relative overflow-hidden p-6 sm:p-7">
        <div className="pointer-events-none absolute -right-20 -top-20 h-64 w-64 rounded-full bg-cyan-400/10 blur-3xl" />
        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-start">
          <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-3xl border border-white/12 bg-ink-900/50 text-3xl">
            {book.subject_icon || "📘"}
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="iris">{book.subject_name || "Пособие"}</Badge>
              {book.grade ? <Badge>{book.grade} класс</Badge> : null}
              {book.pages ? <Badge tone="cyan">{book.pages} стр.</Badge> : null}
            </div>
            <h1 className="mt-3 font-display text-2xl font-semibold text-white sm:text-3xl">{book.title}</h1>
            <p className="mt-1 text-sm text-mist-400">{book.author || "Автор не указан"}</p>
            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-mist-500">{book.description}</p>
          </div>
        </div>
      </Card>

      {recommendations.length > 0 && (
        <Card className="p-5">
          <SectionTitle eyebrow="От учителя" title="Рекомендация" />
          <div className="mt-4 space-y-2">
            {recommendations.map((rec) => (
              <div key={rec.id} className="flex flex-col gap-3 rounded-2xl border border-amber-400/20 bg-amber-400/[0.05] p-3.5 sm:flex-row sm:items-center">
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-bold text-amber-200">
                    {rec.topic_title ? `Тема «${rec.topic_title}»` : "Прочитайте книгу"}
                  </p>
                  {rec.note ? <p className="mt-0.5 text-[11px] leading-relaxed text-amber-100/70">{rec.note}</p> : null}
                </div>
                <Button size="sm" icon={CheckCircle2} loading={pending} onClick={() => markDone(rec)}>Выполнено</Button>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="grid gap-5 lg:grid-cols-[1.15fr_0.85fr]">
        <div ref={readerRef} className="min-w-0 scroll-mt-24 lg:order-2">
          <Card className="p-5 sm:p-6">
            <SectionTitle
              eyebrow="Чтение"
              title="Страницы пособия"
              action={
                pages > 0 ? (
                  <Button size="sm" variant="ghost" icon={zoom ? ZoomOut : ZoomIn} onClick={() => setZoom((value) => !value)}>
                    {zoom ? "Уместить" : "Крупнее"}
                  </Button>
                ) : null
              }
            />
            {pages > 0 ? (
              <>
                <div className={`mt-4 rounded-2xl border border-white/8 bg-ink-950 ${zoom ? "overflow-auto" : "overflow-hidden"}`}>
                  {pageSrc ? (
                    <img
                      src={pageSrc}
                      alt={`Страница ${page}`}
                      className={zoom ? "w-[170%] max-w-none" : "w-full"}
                    />
                  ) : (
                    <div className="flex min-h-64 items-center justify-center px-4 py-10 text-center text-xs text-mist-500">
                      {pageError || "Загружаем страницу…"}
                    </div>
                  )}
                </div>
                <div className="mt-4 flex items-center justify-between gap-2">
                  <Button variant="ghost" icon={ChevronLeft} disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>
                    Назад
                  </Button>
                  <div className="flex items-center gap-1.5 text-xs font-bold text-mist-500">
                    <input
                      aria-label="Номер страницы"
                      inputMode="numeric"
                      value={pageDraft}
                      onChange={(event) => setPageDraft(event.target.value.replace(/[^0-9]/g, ""))}
                      onBlur={commitPage}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          commitPage();
                        }
                      }}
                      className="w-14 rounded-lg border border-white/10 bg-ink-900 px-2 py-1.5 text-center text-xs font-bold text-white outline-none focus:border-iris-400/50"
                    />
                    <span>/ {pages}</span>
                  </div>
                  <Button variant="ghost" icon={ChevronRight} disabled={page >= pages} onClick={() => setPage((value) => Math.min(pages, value + 1))}>
                    Дальше
                  </Button>
                </div>
                <Progress value={Math.round((page / pages) * 100)} className="mt-3" />
              </>
            ) : (
              <EmptyState icon="📖" title="Файл не загружен" text="У пособия нет PDF-файла, но темы доступны для изучения." />
            )}
          </Card>
        </div>

        <Card className="min-w-0 p-5 sm:p-6 lg:order-1">
          <SectionTitle eyebrow="Содержание" title="Темы в пособии" subtitle="Переходите к теме, чтобы прочитать объяснение и потренироваться." />
          <div className="mt-5 space-y-2">
            {topics.length === 0 && <EmptyState icon="📄" title="Темы не привязаны" text="Пособие можно читать постранично выше." />}
            {topics.map((topic) => (
              <Link
                key={`${topic.topic_slug}-${topic.page || 0}`}
                to={`/app/learn/${topic.topic_slug}`}
                className="flex items-center gap-3 rounded-xl border border-white/8 bg-white/[0.025] px-3.5 py-3 transition hover:border-iris-400/30"
              >
                <span className="text-lg">{topic.icon || "📖"}</span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-bold text-white">{topic.title}</p>
                  <p className="text-[11px] text-mist-500">
                    {topic.grade ? `${topic.grade} класс` : "тема"}
                    {topic.page ? ` · стр. ${topic.page}${topic.page_end && topic.page_end !== topic.page ? `–${topic.page_end}` : ""}` : ""}
                  </p>
                </div>
                <ArrowRight size={14} className="text-mist-600" />
              </Link>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
