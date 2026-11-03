import { useEffect, useMemo, useState } from "react";
import {
  Ban,
  Check,
  Clock,
  Film,
  Link2,
  Play,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  Sparkles,
  Trash2,
  Youtube,
  Zap,
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
  SectionTitle,
  Select,
  Skeleton,
  StatCard,
  Tabs,
} from "../../components/ui";
import { useAction, useApi, toast } from "../../lib/hooks";
import { api, invalidate } from "../../lib/api";
import { formatDateTime, plural } from "../../lib/format";
import { SearchBox, Toggle } from "./shared";

const BASE_FORM = {
  enabled: false,
  api_key: "",
  region_code: "BY",
  relevance_language: "ru",
  max_per_topic: 3,
  min_duration: 60,
  max_duration: 3600,
  cache_days: 14,
  ai_ranking: true,
};

export function AdminYouTube() {
  const { data, loading, error, refresh } = useApi("/admin/youtube");
  const [tab, setTab] = useState("topics");
  const [search, setSearch] = useState("");
  const [form, setForm] = useState(BASE_FORM);
  const [keyInput, setKeyInput] = useState("");
  const [manualFor, setManualFor] = useState(null);
  const [manualUrl, setManualUrl] = useState("");
  const [busy, setBusy] = useState("");
  const { pending, run } = useAction();

  const settings = data?.settings || {};
  const status = data?.status || {};
  const stats = data?.stats || {};
  const topics = data?.topics || [];
  const manual = data?.manual || [];
  const limits = data?.limits || {};

  useEffect(() => {
    setForm({
      enabled: Boolean(settings.enabled),
      region_code: settings.region_code || "BY",
      relevance_language: settings.relevance_language || "ru",
      max_per_topic: Number(settings.max_per_topic || 3),
      min_duration: Number(settings.min_duration || 60),
      max_duration: Number(settings.max_duration || 3600),
      cache_days: Number(settings.cache_days || 14),
      ai_ranking: Boolean(settings.ai_ranking),
    });
  }, [settings.enabled, settings.region_code, settings.relevance_language, settings.max_per_topic, settings.min_duration, settings.max_duration, settings.cache_days, settings.ai_ranking]);

  const visibleTopics = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return topics;
    return topics.filter((topic) => `${topic.title} ${topic.slug} ${topic.subject_name}`.toLowerCase().includes(query));
  }, [topics, search]);

  const visibleManual = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return manual;
    return manual.filter((video) => `${video.title} ${video.topic_title} ${video.channel}`.toLowerCase().includes(query));
  }, [manual, search]);

  const save = async () => {
    try {
      const payload = await run(() => api.put("/admin/youtube", {
        ...form,
        api_key: keyInput.trim(),
        keep_key: !keyInput.trim(),
        clear_key: false,
      }));
      invalidate("/admin");
      await refresh();
      setKeyInput("");
      toast(payload.message || "Настройки YouTube сохранены", payload.ok === false ? "info" : "success");
    } catch (err) {
      toast(err.message || "Не удалось сохранить настройки", "error");
    }
  };

  const test = async () => {
    setBusy("test");
    try {
      const payload = await run(() => api.post("/admin/youtube/test", {}));
      toast(payload.message || (payload.ok ? "Связь есть" : "Проверка не удалась"), payload.ok ? "success" : "error");
      await refresh();
    } catch (err) {
      toast(err.message || "Проверка не удалась", "error");
    } finally {
      setBusy("");
    }
  };

  const clearCache = async () => {
    if (!window.confirm("Очистить автоматически подобранные видео? Ручные ссылки сохранятся.")) return;
    setBusy("clear");
    try {
      const payload = await run(() => api.post("/admin/youtube/clear-cache", {}));
      toast(payload.message || "Кэш очищен", "success");
      await refresh();
    } catch (err) {
      toast(err.message || "Не удалось очистить кэш", "error");
    } finally {
      setBusy("");
    }
  };

  const warm = async () => {
    setBusy("warm");
    try {
      const payload = await run(() => api.post("/admin/youtube/warm", { limit: limits.warm || 5 }));
      toast(payload.message || `Обработано тем: ${payload.processed || 0}`, payload.stopped ? "info" : "success");
      await refresh();
    } catch (err) {
      toast(err.message || "Не удалось подобрать видео", "error");
    } finally {
      setBusy("");
    }
  };

  const refreshTopic = async (topic) => {
    setBusy(topic.slug);
    try {
      const payload = await run(() => api.post("/admin/youtube/refresh-topic", { slug: topic.slug }));
      toast(payload.message || "Видео обновлены", "success");
      await refresh();
    } catch (err) {
      toast(err.message || "Не удалось обновить тему", "error");
    } finally {
      setBusy("");
    }
  };

  const addManual = async () => {
    if (!manualFor || !manualUrl.trim()) {
      toast("Вставьте ссылку на YouTube", "info");
      return;
    }
    try {
      const payload = await run(() => api.post("/admin/youtube/manual", { slug: manualFor.slug, video_url: manualUrl.trim() }));
      toast(payload.message || "Видео добавлено", "success");
      setManualFor(null);
      setManualUrl("");
      await refresh();
    } catch (err) {
      toast(err.message || "Не удалось добавить видео", "error");
    }
  };

  const blockVideo = async (video) => {
    if (!window.confirm(`Скрыть видео «${video.title}» из темы?`)) return;
    try {
      const payload = await run(() => api.del(`/admin/youtube/videos/${video.id}`));
      toast(payload.message || "Видео скрыто", "success");
      await refresh();
    } catch (err) {
      toast(err.message || "Не удалось скрыть видео", "error");
    }
  };

  if (loading && !data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-16 w-full" />
        <div className="grid gap-3 sm:grid-cols-4">{Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-28" />)}</div>
        <Skeleton className="h-72 w-full" />
      </div>
    );
  }

  const configured = Boolean(status.configured || status.has_key);

  return (
    <div className="space-y-6">
      <PageHeader
        title="YouTube"
        subtitle="Видео к темам помогают разобраться быстрее. Подборка кэшируется, ручные ссылки всегда остаются."
        actions={
          <>
            <Button variant="ghost" icon={Zap} loading={busy === "warm"} onClick={warm}>Подобрать 5 тем</Button>
            <Button icon={RefreshCw} loading={busy === "test"} onClick={test}>Проверить связь</Button>
          </>
        }
      />

      {error && <ErrorState error={error} onRetry={refresh} />}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Youtube} label="Тем с видео" value={stats.with_videos || 0} hint={`из ${stats.topics || 0}`} tone="rose" />
        <StatCard icon={Film} label="Авто-видео" value={stats.auto || 0} hint={`${stats.manual || 0} ручных`} tone="iris" />
        <StatCard icon={Clock} label="Свежий кэш" value={stats.fresh || 0} hint={`${stats.errors || 0} ошибок`} tone="cyan" />
        <StatCard icon={Sparkles} label="ИИ-ранжирование" value={settings.ai_ranking ? "вкл" : "выкл"} hint={configured ? "ключ задан" : "ключ не задан"} tone="gold" />
      </div>

      {stats.last_error && (
        <Card className="border-rose-400/20 bg-rose-500/[0.04] p-4">
          <p className="text-[11px] font-bold text-rose-200">Последняя ошибка YouTube</p>
          <p className="mt-1 text-[11px] leading-relaxed text-rose-200/70">{stats.last_error}</p>
        </Card>
      )}

      <Card className="p-5 sm:p-6">
        <SectionTitle
          eyebrow="Интеграция"
          title="Настройки"
          subtitle="Ключ хранится на сервере и не показывается в интерфейсе."
          action={<Badge tone={status.enabled && configured ? "green" : "gold"}><Settings2 size={12} /> {status.enabled && configured ? "активна" : "не готова"}</Badge>}
        />
        <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div className="sm:col-span-2 lg:col-span-3">
            <Toggle
              value={form.enabled}
              onChange={(value) => setForm((current) => ({ ...current, enabled: value }))}
              label="Показывать видео детям"
              text="Если выключено, видео не запрашиваются и не отображаются."
            />
          </div>
          <Field label="API-ключ YouTube" hint={settings.has_key ? "Ключ уже сохранён. Оставьте пустым, чтобы не менять." : "Получите в Google Cloud Console → YouTube Data API v3."}>
            <Input value={keyInput} onChange={(event) => setKeyInput(event.target.value)} placeholder={settings.has_key ? "••••••••" : "AIza…"} />
          </Field>
          <Field label="Регион"><Input value={form.region_code} onChange={(event) => setForm((current) => ({ ...current, region_code: event.target.value.toUpperCase() }))} maxLength={4} /></Field>
          <Field label="Язык запросов">
            <Select value={form.relevance_language} onChange={(event) => setForm((current) => ({ ...current, relevance_language: event.target.value }))}>
              <option value="ru">Русский</option>
              <option value="be">Белорусский</option>
              <option value="en">Английский</option>
            </Select>
          </Field>
          <Field label="Видео на тему"><Input type="number" min={1} max={10} value={form.max_per_topic} onChange={(event) => setForm((current) => ({ ...current, max_per_topic: event.target.value }))} /></Field>
          <Field label="Мин. длительность, сек"><Input type="number" min={0} value={form.min_duration} onChange={(event) => setForm((current) => ({ ...current, min_duration: event.target.value }))} /></Field>
          <Field label="Макс. длительность, сек"><Input type="number" min={60} value={form.max_duration} onChange={(event) => setForm((current) => ({ ...current, max_duration: event.target.value }))} /></Field>
          <Field label="Кэш, дней"><Input type="number" min={1} max={90} value={form.cache_days} onChange={(event) => setForm((current) => ({ ...current, cache_days: event.target.value }))} /></Field>
          <div className="sm:col-span-2 lg:col-span-3">
            <Toggle
              value={form.ai_ranking}
              onChange={(value) => setForm((current) => ({ ...current, ai_ranking: value }))}
              label="ИИ-ранжирование"
              text="Подсказывает, какие видео лучше подходят теме и классу."
            />
          </div>
          <div className="flex flex-wrap gap-2 sm:col-span-2 lg:col-span-3">
            <Button icon={Check} loading={pending} onClick={save}>Сохранить</Button>
            <Button variant="ghost" icon={Trash2} loading={busy === "clear"} onClick={clearCache}>Очистить кэш</Button>
            {settings.has_key && <Badge tone="green"><Check size={11} /> ключ сохранён</Badge>}
          </div>
        </div>
      </Card>

      <Tabs
        tabs={[
          { key: "topics", label: "Темы", count: topics.length },
          { key: "manual", label: "Ручные видео", count: manual.length },
        ]}
        value={tab}
        onChange={setTab}
      />

      <Card className="p-4">
        <SearchBox value={search} onChange={setSearch} placeholder="Тема, slug или видео…" />
      </Card>

      {tab === "topics" && (
        <Card className="divide-y divide-white/6 p-2">
          {visibleTopics.length === 0 && <EmptyState icon="🔍" title="Ничего не нашлось" text="Попробуйте другой запрос." />}
          {visibleTopics.map((topic) => (
            <div key={topic.slug} className="flex flex-col gap-3 rounded-xl px-3 py-3 transition hover:bg-white/[0.025] sm:flex-row sm:items-center">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/8 bg-white/[0.03] text-xs font-bold text-white">
                {topic.grade}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="truncate text-xs font-bold text-white">{topic.title}</p>
                  {topic.videos > 0 ? <Badge tone="green">{topic.videos} видео</Badge> : <Badge>без видео</Badge>}
                  {topic.manual > 0 && <Badge tone="cyan">{topic.manual} ручных</Badge>}
                  {topic.error && <Badge tone="rose">ошибка</Badge>}
                  {topic.fresh ? <Badge tone="iris">кэш свежий</Badge> : null}
                </div>
                <p className="mt-0.5 truncate text-[10px] text-mist-600">
                  {topic.subject_name} · <span className="font-mono">{topic.slug}</span>
                  {topic.checked_at ? ` · проверено ${formatDateTime(topic.checked_at)}` : ""}
                </p>
                {topic.error && <p className="mt-0.5 line-clamp-1 text-[10px] text-rose-300/80">{topic.error}</p>}
              </div>
              <div className="flex shrink-0 items-center gap-1.5">
                <Button size="sm" variant="ghost" icon={RefreshCw} loading={busy === topic.slug} onClick={() => refreshTopic(topic)}>Обновить</Button>
                <IconButton icon={Link2} label="Добавить ссылку" onClick={() => { setManualFor(topic); setManualUrl(""); }} />
              </div>
            </div>
          ))}
        </Card>
      )}

      {tab === "manual" && (
        <div className="grid gap-3 sm:grid-cols-2">
          {visibleManual.length === 0 && <Card className="sm:col-span-2"><EmptyState icon="🎬" title="Ручных видео нет" text="Добавьте ссылку к теме — она всегда будет первой в списке." /></Card>}
          {visibleManual.map((video) => (
            <Card key={video.id} className="p-4">
              <div className="flex items-start gap-3">
                {video.thumbnail ? (
                  <img src={video.thumbnail} alt="" className="h-16 w-24 shrink-0 rounded-xl border border-white/10 object-cover" loading="lazy" />
                ) : (
                  <span className="flex h-16 w-24 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-xl">🎬</span>
                )}
                <div className="min-w-0 flex-1">
                  <p className="line-clamp-2 text-xs font-bold text-white">{video.title}</p>
                  <p className="mt-1 truncate text-[10px] text-mist-600">{video.channel || "YouTube"} · {video.duration_label || "—"}</p>
                  <p className="mt-0.5 truncate text-[10px] text-iris-300">{video.topic_title || video.topic_slug}</p>
                </div>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-1.5">
                <Badge tone="cyan">ручное</Badge>
                {video.watch_url ? (
                  <a href={video.watch_url} target="_blank" rel="noreferrer" className="btn btn-ghost btn-sm">
                    <Play size={13} /> Открыть
                  </a>
                ) : null}
                <Button size="sm" variant="plain" icon={Ban} className="text-rose-300" onClick={() => blockVideo(video)}>Скрыть</Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal
        open={Boolean(manualFor)}
        onClose={() => setManualFor(null)}
        title="Ручное видео"
        description={manualFor?.title || ""}
        footer={<><Button variant="ghost" onClick={() => setManualFor(null)}>Отмена</Button><Button icon={Link2} loading={pending} onClick={addManual}>Добавить</Button></>}
      >
        <div className="space-y-4">
          <Field label="Ссылка на YouTube" hint="Обычная ссылка, Shorts или youtu.be — распознаем автоматически.">
            <Input value={manualUrl} onChange={(event) => setManualUrl(event.target.value)} placeholder="https://www.youtube.com/watch?v=…" autoFocus />
          </Field>
          <p className="text-[11px] leading-relaxed text-mist-500">
            Ручные видео не исчезают при очистке кэша и показываются первыми. Максимум — {limits.manual_per_topic || 10} на тему.
          </p>
        </div>
      </Modal>
    </div>
  );
}
