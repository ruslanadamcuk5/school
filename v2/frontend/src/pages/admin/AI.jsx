import { useEffect, useMemo, useState } from "react";
import {
  Bot,
  Check,
  Cpu,
  ExternalLink,
  KeyRound,
  RefreshCw,
  Server,
  Sparkles,
  Trash2,
  Wand2,
  Zap,
} from "lucide-react";
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
} from "../../components/ui";
import { useAction, useApi, toast } from "../../lib/hooks";
import { api, invalidate } from "../../lib/api";
import { formatDateTime, relativeTime, text } from "../../lib/format";
import { Toggle } from "./shared";

export function AdminAI() {
  const { data, loading, error, refresh } = useApi("/admin/ai");
  const [form, setForm] = useState(null);
  const [keyInput, setKeyInput] = useState("");
  const [busy, setBusy] = useState(false);
  const { pending, run } = useAction();

  const settings = data?.settings || {};
  const providers = data?.providers || [];
  const stats = data?.stats || {};
  const recent = stats.recent || [];

  useEffect(() => {
    setForm({
      enabled: Boolean(settings.enabled),
      provider: settings.provider || "openrouter",
      base_url: settings.base_url || "",
      model: settings.model || "",
      temperature: Number(settings.temperature ?? 0.3),
      max_tokens: Number(settings.max_tokens || 900),
      system_note: settings.system_note || "",
    });
  }, [settings.enabled, settings.provider, settings.base_url, settings.model, settings.temperature, settings.max_tokens, settings.system_note]);

  const activeProvider = useMemo(
    () => providers.find((provider) => provider.id === form?.provider) || providers[0],
    [providers, form?.provider],
  );

  const changeProvider = (providerId) => {
    const provider = providers.find((item) => item.id === providerId);
    setForm((current) => ({
      ...current,
      provider: providerId,
      base_url: provider?.base_url || "",
      model: provider?.models?.[0] || "",
    }));
  };

  const save = async () => {
    if (!form) return;
    try {
      await run(() => api.put("/admin/ai", {
        ...form,
        temperature: Number(form.temperature),
        max_tokens: Number(form.max_tokens),
        api_key: keyInput.trim(),
        keep_key: !keyInput.trim(),
      }));
      invalidate("/admin");
      await refresh();
      setKeyInput("");
      toast("Настройки ИИ сохранены", "success");
    } catch (err) {
      toast(err.message || "Не удалось сохранить настройки", "error");
    }
  };

  const test = async () => {
    setBusy(true);
    try {
      const payload = await run(() => api.post("/admin/ai/test", {}));
      toast(payload.message || (payload.ok ? "Модель отвечает" : "Проверка не удалась"), payload.ok ? "success" : "error");
      await refresh();
    } catch (err) {
      toast(err.message || "Проверка не удалась", "error");
    } finally {
      setBusy(false);
    }
  };

  const clearCache = async () => {
    if (!window.confirm("Удалить готовые объяснения и кэш вопросов? Они будут созданы заново при следующем запросе.")) return;
    try {
      const payload = await run(() => api.post("/admin/ai/clear-cache", {}));
      toast(`Очищено объяснений: ${payload.removed ?? 0}`, "info");
      await refresh();
    } catch (err) {
      toast(err.message || "Не удалось очистить кэш", "error");
    }
  };

  const total = Number(stats.total || 0);
  const ok = Number(stats.ok || 0);
  const percent = total ? Math.round((ok / total) * 100) : 0;

  if (loading && !data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-16 w-full" />
        <div className="grid gap-3 sm:grid-cols-4">{Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-28" />)}</div>
        <Skeleton className="h-80 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Искусственный интеллект"
        subtitle="Объяснения ошибок, подсказки и разбор заданий. Один ключ — и дети получают помощь в моменте."
        actions={
          <>
            <Button variant="ghost" icon={RefreshCw} loading={busy} onClick={test}>Проверить модель</Button>
            <Button variant="ghost" icon={Trash2} loading={pending} onClick={clearCache}>Очистить кэш</Button>
            <Button icon={Check} loading={pending} onClick={save}>Сохранить</Button>
          </>
        }
      />

      {error && <ErrorState error={error} onRetry={refresh} />}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Wand2} label="Объяснений" value={stats.total || 0} tone="iris" />
        <StatCard icon={Check} label="Успешных" value={stats.ok || 0} hint={`${percent}%`} tone="green" />
        <StatCard icon={Zap} label="Ошибок" value={stats.failed || 0} tone="rose" />
        <StatCard icon={Cpu} label="Провайдер" value={settings.provider_name || settings.provider || "—"} hint={settings.has_key ? "ключ задан" : "ключ не задан"} tone="cyan" />
      </div>

      <div className="grid min-w-0 gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <Card className="min-w-0 p-5 sm:p-6">
          <SectionTitle
            eyebrow="Подключение"
            title="Провайдер и модель"
            subtitle="Подойдёт любой OpenAI-совместимый сервис."
            action={<Badge tone={settings.enabled && settings.has_key ? "green" : "gold"}><Bot size={12} /> {settings.enabled && settings.has_key ? "активен" : "не готов"}</Badge>}
          />

          {form && (
            <div className="mt-5 space-y-4">
              <Toggle
                value={form.enabled}
                onChange={(value) => setForm((current) => ({ ...current, enabled: value }))}
                label="Включить ИИ-подсказки"
                text="Дети увидят кнопку «Объясни» после ошибки."
              />

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Провайдер" className="sm:col-span-2">
                  <Select value={form.provider} onChange={(event) => changeProvider(event.target.value)}>
                    {providers.map((provider) => (
                      <option key={provider.id} value={provider.id}>{provider.name}</option>
                    ))}
                  </Select>
                  {activeProvider?.note && <p className="mt-1.5 break-words text-[11px] leading-relaxed text-mist-600">{activeProvider.note}</p>}
                </Field>

                {activeProvider?.models?.length ? (
                  <Field label="Модель" className="sm:col-span-2">
                    <Select value={form.model} onChange={(event) => setForm((current) => ({ ...current, model: event.target.value }))}>
                      {activeProvider.models.map((model) => <option key={model} value={model}>{model}</option>)}
                    </Select>
                  </Field>
                ) : (
                  <Field label="Модель" className="sm:col-span-2">
                    <Input value={form.model} onChange={(event) => setForm((current) => ({ ...current, model: event.target.value }))} placeholder="Название модели" />
                  </Field>
                )}

                <Field label="Адрес API" className="sm:col-span-2" hint={activeProvider?.keys_url ? `Ключ: ${activeProvider.keys_url}` : ""}>
                  <Input value={form.base_url} onChange={(event) => setForm((current) => ({ ...current, base_url: event.target.value }))} placeholder="https://…/v1" />
                </Field>

                <Field label="API-ключ" hint={settings.has_key ? "Ключ сохранён. Оставьте пустым, чтобы не менять." : "Вставьте ключ провайдера."}>
                  <Input value={keyInput} onChange={(event) => setKeyInput(event.target.value)} placeholder={settings.has_key ? "••••••••" : "sk-…"} />
                </Field>
                {activeProvider?.keys_url && (
                  <div className="flex items-end">
                    <a href={activeProvider.keys_url} target="_blank" rel="noreferrer" className="btn btn-ghost">
                      <ExternalLink size={15} /> Где взять ключ
                    </a>
                  </div>
                )}

                <Field label="Температура" hint="0 — строго, 1 — свободно.">
                  <Input type="number" step="0.1" min={0} max={2} value={form.temperature} onChange={(event) => setForm((current) => ({ ...current, temperature: event.target.value }))} />
                </Field>
                <Field label="Максимум токенов">
                  <Input type="number" min={64} max={8000} value={form.max_tokens} onChange={(event) => setForm((current) => ({ ...current, max_tokens: event.target.value }))} />
                </Field>
                <Field label="Системная заметка" hint="Например: объясняй простыми словами, как для 3 класса." className="sm:col-span-2">
                  <Textarea value={form.system_note} onChange={(event) => setForm((current) => ({ ...current, system_note: event.target.value }))} placeholder="Тон и правила ответов…" />
                </Field>
              </div>

              <div className="flex flex-wrap gap-2">
                <Button icon={Check} loading={pending} onClick={save}>Сохранить</Button>
                <Button variant="ghost" icon={RefreshCw} loading={busy} onClick={test}>Проверить связь</Button>
                {settings.has_key && <Badge tone="green"><KeyRound size={11} /> ключ сохранён</Badge>}
              </div>
            </div>
          )}
        </Card>

        <div className="space-y-5">
          <Card className="p-5 sm:p-6">
            <SectionTitle eyebrow="Здоровье" title="Качество ответов" />
            <div className="mt-4">
              <div className="mb-1.5 flex items-center justify-between text-[10px] font-bold text-mist-500">
                <span>Успешные ответы</span>
                <span>{total ? `${percent}%` : "нет данных"}</span>
              </div>
              <Progress value={percent} />
            </div>
            <div className="mt-4 grid grid-cols-3 gap-2">
              {[
                ["Всего", total],
                ["Успешно", ok],
                ["Ошибок", stats.failed || 0],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl border border-white/7 bg-white/[0.025] px-3 py-2.5 text-center">
                  <p className="font-display text-base font-semibold text-white">{value}</p>
                  <p className="mt-0.5 text-[10px] font-bold uppercase tracking-wider text-mist-600">{label}</p>
                </div>
              ))}
            </div>
            {stats.last_error ? (
              <p className="mt-4 line-clamp-4 break-words rounded-xl border border-rose-400/20 bg-rose-500/[0.06] px-3 py-2 text-[11px] leading-relaxed text-rose-200/80">
                {text(stats.last_error)}
              </p>
            ) : (
              <p className="mt-4 text-[11px] leading-relaxed text-mist-500">
                Если ответов пока нет, проверьте связь кнопкой «Проверить модель».
              </p>
            )}
          </Card>

          <Card className="p-5 sm:p-6">
            <SectionTitle eyebrow="Провайдеры" title="Доступные сервисы" />
            <div className="mt-4 space-y-2">
              {providers.slice(0, 5).map((provider) => (
                <div key={provider.id} className="flex items-center gap-2.5 rounded-xl border border-white/7 bg-white/[0.02] px-3 py-2.5">
                  <Server size={14} className="shrink-0 text-iris-300" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[11px] font-bold text-white">{provider.name}</p>
                    <p className="truncate text-[10px] text-mist-600">{provider.models?.length || 0} моделей</p>
                  </div>
                  {form?.provider === provider.id && <Badge tone="green">выбран</Badge>}
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      <div>
        <SectionTitle eyebrow="История" title="Последние объяснения" subtitle="Свежие запросы к модели и их результат." />
        <Card className="mt-4 p-2">
          {recent.length === 0 && <EmptyState icon="✨" title="Объяснений пока нет" text="Они появятся, когда дети начнут пользоваться подсказками." />}
          {recent.map((item, index) => (
            <div key={`${item.created_at}-${index}`} className="flex items-start gap-3 rounded-xl px-3 py-2.5">
              <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${item.ok || item.status === "ok" ? "bg-emerald-400" : "bg-rose-400"}`} />
              <div className="min-w-0 flex-1">
                <p className="text-[11px] font-semibold text-white">{text(item.prompt || item.question || item.kind, "Запрос к ИИ")}</p>
                <p className="mt-0.5 line-clamp-2 text-[10px] text-mist-600">{text(item.answer || item.error || item.detail)}</p>
              </div>
              <span className="shrink-0 text-[10px] text-mist-600">
                {item.created_at ? relativeTime(item.created_at) : ""}
              </span>
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}
