import { useEffect, useState } from "react";
import { Check, Map, RefreshCw, Sparkles } from "lucide-react";
import {
  Badge,
  Button,
  Card,
  ErrorState,
  Field,
  Input,
  PageHeader,
  Select,
  Skeleton,
} from "../../components/ui";
import { useAction, useApi, toast } from "../../lib/hooks";
import { api, invalidate } from "../../lib/api";

export function AdminMap() {
  const { data, loading, error, refresh } = useApi("/admin/map-settings");
  const [form, setForm] = useState(null);
  const { pending, run } = useAction();

  const presets = data?.presets || [];

  useEffect(() => {
    if (data?.settings) setForm({ ...data.settings });
  }, [data]);

  const change = (key, value) => setForm((current) => ({ ...current, [key]: value }));

  const pickPreset = (provider) => {
    const preset = presets.find((item) => item.id === provider);
    setForm((current) => ({
      ...current,
      provider,
      tile_url: preset?.tile_url ?? current.tile_url,
      attribution: preset?.attribution ?? current.attribution,
      crs: preset?.crs ?? current.crs,
      max_zoom: preset?.max_zoom ?? current.max_zoom,
    }));
  };

  const save = async () => {
    try {
      const result = await run(() => api.put("/admin/map-settings", form));
      invalidate("/admin");
      await refresh();
      toast(result.message || "Настройки карты сохранены", "success");
    } catch (err) {
      toast(err.message || "Не удалось сохранить настройки карты", "error");
    }
  };

  if (loading && !data) {
    return <div className="space-y-4"><Skeleton className="h-16 w-full" /><Skeleton className="h-96 w-full" /></div>;
  }

  if (error && !data) return <ErrorState error={error} onRetry={refresh} />;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Карта"
        subtitle="Провайдер тайлов и стартовый вид карты. Настройки общие для сайта, кабинета родителя и Android-приложения."
        actions={<Button icon={Check} loading={pending} onClick={save}>Сохранить</Button>}
      />

      {form && (
        <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
          <Card className="space-y-4 p-5 sm:p-6">
            <h2 className="font-display text-lg font-semibold text-white">Провайдер</h2>
            <Field label="Сервис карты" hint="Можно выбрать готовый или указать свои тайлы.">
              <Select value={form.provider} onChange={(event) => pickPreset(event.target.value)}>
                {presets.map((preset) => (
                  <option key={preset.id} value={preset.id}>{preset.name}</option>
                ))}
              </Select>
            </Field>
            {presets.find((preset) => preset.id === form.provider)?.note && (
              <p className="rounded-xl border border-white/7 bg-white/[0.02] px-3 py-2 text-[11px] leading-relaxed text-mist-500">
                {presets.find((preset) => preset.id === form.provider).note}
              </p>
            )}

            <Field label="Адрес тайлов" hint="Обязательны подстановки {x}, {y} и {z}.">
              <Input value={form.tile_url || ""} onChange={(event) => change("tile_url", event.target.value)} spellCheck={false} placeholder="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
            </Field>
            <Field label="Подпись источника">
              <Input value={form.attribution || ""} onChange={(event) => change("attribution", event.target.value)} maxLength={200} placeholder="© OpenStreetMap" />
            </Field>
            <Field label="Система координат">
              <Select value={form.crs} onChange={(event) => change("crs", event.target.value)}>
                <option value="mercator">Меркатор (OSM)</option>
                <option value="yandex">Яндекс</option>
              </Select>
            </Field>
          </Card>

          <Card className="space-y-4 p-5 sm:p-6">
            <h2 className="font-display text-lg font-semibold text-white">Вид карты</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Масштаб">
                <Input type="number" min={0} max={22} value={form.zoom} onChange={(event) => change("zoom", event.target.value)} />
              </Field>
              <Field label="Максимальный zoom">
                <Input type="number" min={1} max={22} value={form.max_zoom} onChange={(event) => change("max_zoom", event.target.value)} />
              </Field>
              <Field label="Минимальный zoom">
                <Input type="number" min={0} max={22} value={form.min_zoom} onChange={(event) => change("min_zoom", event.target.value)} />
              </Field>
              <Field label="Широта центра" hint="От -90 до 90">
                <Input type="number" step="0.000001" min={-90} max={90} value={form.center_lat} onChange={(event) => change("center_lat", event.target.value)} />
              </Field>
              <Field label="Долгота центра" hint="От -180 до 180" className="sm:col-span-2">
                <Input type="number" step="0.000001" min={-180} max={180} value={form.center_lon} onChange={(event) => change("center_lon", event.target.value)} />
              </Field>
            </div>
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <Badge tone="iris">{form.crs}</Badge>
              <Badge tone="cyan">zoom {form.zoom}</Badge>
              <Badge tone="green">{form.center_lat}, {form.center_lon}</Badge>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button icon={Check} loading={pending} onClick={save}>Сохранить</Button>
              <Button variant="ghost" icon={RefreshCw} onClick={refresh}>Сбросить изменения</Button>
            </div>
          </Card>
        </div>
      )}

      <Card className="flex items-start gap-3 p-5">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-white/8 bg-white/5 text-iris-300">
          <Map size={18} />
        </span>
        <p className="text-xs leading-relaxed text-mist-500">
          После смены провайдера обновите страницу «Карта детей». Если новые тайлы не загружаются,
          проверьте адрес: в нём должны быть <span className="font-mono text-mist-300">{"{x}"}</span>,{" "}
          <span className="font-mono text-mist-300">{"{y}"}</span> и{" "}
          <span className="font-mono text-mist-300">{"{z}"}</span>.
        </p>
      </Card>
    </div>
  );
}
