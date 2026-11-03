import { useEffect, useMemo, useState } from "react";
import {
  Check,
  Coins,
  Gift,
  Megaphone,
  Pencil,
  Percent,
  Plus,
  RotateCcw,
  Search,
  Sparkles,
  Star,
  Store,
  Tag,
  Trash2,
  Trophy,
  Users,
  X,
  Zap,
} from "lucide-react";
import {
  Avatar,
  Badge,
  Button,
  Card,
  Coin,
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
  Textarea,
  Xp,
} from "../../components/ui";
import { useAction, useApi, toast } from "../../lib/hooks";
import { api, invalidate } from "../../lib/api";
import { formatDate, formatDateTime, plural, scoreTone } from "../../lib/format";
import { SearchBox, Toggle } from "./shared";

const EVENT_KINDS = [
  { key: "double_coins", label: "Двойные монеты", hint: "Монеты за ответы ×N" },
  { key: "double_xp", label: "Двойной опыт", hint: "Опыт за ответы ×N" },
  { key: "discount", label: "Скидка в магазине", hint: "Скидка N% на всё" },
];

function categoryName(categories, key) {
  return categories.find((category) => category.key === key)?.name || key;
}

function categoryIcon(categories, key) {
  return categories.find((category) => category.key === key)?.icon || "🛍";
}

export function AdminShop() {
  const { data, setData, loading, error, refresh } = useApi("/admin/shop");
  const [tab, setTab] = useState("catalog");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [announcement, setAnnouncement] = useState("");
  const [featured, setFeatured] = useState("");
  const [itemModal, setItemModal] = useState(null);
  const [itemForm, setItemForm] = useState(null);
  const [eventOpen, setEventOpen] = useState(false);
  const [giftOpen, setGiftOpen] = useState(false);
  const [eventForm, setEventForm] = useState({ title: "", description: "", icon: "🎉", kind: "double_coins", value: 2, starts_on: "", ends_on: "" });
  const [giftForm, setGiftForm] = useState({ learner_id: "", item_key: "", reason: "", message: "", coins: 0, xp: 0 });
  const { pending, run } = useAction();

  const summary = data?.summary || {};
  const board = data?.board || [];
  const catalog = data?.catalog || [];
  const categories = data?.categories || [];
  const events = data?.events || [];
  const gifts = data?.gifts || [];
  const reasons = data?.reasons || [];

  useEffect(() => {
    setAnnouncement(data?.announcement || "");
    setFeatured(data?.featured_key || "");
  }, [data?.announcement, data?.featured_key]);

  const apply = (payload) => {
    if (payload?.shop) {
      setData(payload.shop);
    } else {
      refresh();
    }
    const message = payload?.message;
    if (message) toast(message, "success");
  };

  const visibleCatalog = useMemo(() => {
    const query = search.trim().toLowerCase();
    return catalog.filter((item) => {
      if (category !== "all" && item.category !== category) return false;
      if (!query) return true;
      return `${item.name} ${item.key} ${item.tagline} ${item.description}`.toLowerCase().includes(query);
    });
  }, [catalog, search, category]);

  const saveAnnouncement = async () => {
    try {
      const payload = await run(() => api.put("/admin/shop/announcement", { announcement }));
      invalidate("/admin");
      apply(payload);
    } catch (err) {
      toast(err.message || "Не удалось сохранить объявление", "error");
    }
  };

  const saveFeatured = async (key) => {
    setFeatured(key);
    try {
      const payload = await run(() => api.put("/admin/shop/featured", { item_key: key }));
      invalidate("/admin");
      apply(payload);
    } catch (err) {
      toast(err.message || "Не удалось изменить витрину", "error");
    }
  };

  const openItem = (item) => {
    const override = item.override || {};
    setItemModal(item);
    setItemForm({
      name: override.name ?? item.name ?? "",
      icon: override.icon ?? item.icon ?? "",
      tagline: override.tagline ?? item.tagline ?? "",
      description: override.description ?? item.description ?? "",
      price_coins: override.price_coins ?? item.coins ?? 0,
      price_xp: override.price_xp ?? item.xp ?? 0,
      discount_percent: override.discount_percent ?? 0,
      level: override.level ?? item.level ?? 1,
      is_active: override.is_active == null ? Boolean(item.is_active) : Boolean(override.is_active),
    });
  };

  const saveItem = async () => {
    if (!itemModal || !itemForm) return;
    try {
      const payload = await run(() => api.post(`/admin/shop/items/${itemModal.key}`, {
        ...itemForm,
        price_coins: Number(itemForm.price_coins) || 0,
        price_xp: Number(itemForm.price_xp) || 0,
        discount_percent: Number(itemForm.discount_percent) || 0,
        level: Number(itemForm.level) || 1,
      }));
      setItemModal(null);
      setItemForm(null);
      invalidate("/admin");
      apply(payload);
    } catch (err) {
      toast(err.message || "Не удалось сохранить товар", "error");
    }
  };

  const resetItem = async (item) => {
    if (!window.confirm(`Вернуть «${item.name}» к исходным настройкам каталога?`)) return;
    try {
      const payload = await run(() => api.post(`/admin/shop/items/${item.key}/reset`, {}));
      invalidate("/admin");
      apply(payload);
    } catch (err) {
      toast(err.message || "Не удалось сбросить товар", "error");
    }
  };

  const openEvent = () => {
    setEventForm({
      title: "",
      description: "",
      icon: "🎉",
      kind: "double_coins",
      value: 2,
      starts_on: data?.today || "",
      ends_on: data?.default_end || "",
    });
    setEventOpen(true);
  };

  const submitEvent = async () => {
    if (!eventForm.title.trim()) {
      toast("Придумайте название события", "info");
      return;
    }
    try {
      const payload = await run(() => api.post("/admin/shop/events", {
        ...eventForm,
        value: Number(eventForm.value) || 2,
      }));
      setEventOpen(false);
      invalidate("/admin");
      apply(payload);
    } catch (err) {
      toast(err.message || "Не удалось запустить событие", "error");
    }
  };

  const stopEvent = async (event) => {
    if (!window.confirm(`Остановить событие «${event.title}»?`)) return;
    try {
      const payload = await run(() => api.post(`/admin/shop/events/${event.id}/stop`, {}));
      invalidate("/admin");
      apply(payload);
    } catch (err) {
      toast(err.message || "Не удалось остановить событие", "error");
    }
  };

  const openGift = (learnerId = "") => {
    setGiftForm({ learner_id: learnerId ? String(learnerId) : "", item_key: "", reason: "", message: "", coins: 0, xp: 0 });
    setGiftOpen(true);
  };

  const submitGift = async () => {
    if (!giftForm.learner_id) {
      toast("Выберите ребёнка", "info");
      return;
    }
    if (!giftForm.item_key && !giftForm.coins && !giftForm.xp) {
      toast("Выберите предмет или начислите монеты/опыт", "info");
      return;
    }
    try {
      const payload = await run(() => api.post("/admin/shop/gifts", {
        ...giftForm,
        learner_id: Number(giftForm.learner_id),
        coins: Number(giftForm.coins) || 0,
        xp: Number(giftForm.xp) || 0,
      }));
      setGiftOpen(false);
      invalidate("/admin");
      apply(payload);
    } catch (err) {
      toast(err.message || "Не удалось отправить подарок", "error");
    }
  };

  const cancelGift = async (gift) => {
    if (!window.confirm(`Отменить подарок для ${gift.learner_name}?`)) return;
    try {
      const payload = await run(() => api.post(`/admin/shop/gifts/${gift.id}/cancel`, {}));
      invalidate("/admin");
      apply(payload);
    } catch (err) {
      toast(err.message || "Не удалось отменить подарок", "error");
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

  return (
    <div className="space-y-6">
      <PageHeader
        title="Магазин"
        subtitle="Каталог наград, витрина дня, живые события и подарки. Монеты и опыт мотивируют учиться."
        actions={
          <>
            <Button variant="ghost" icon={Gift} onClick={() => openGift()}>Подарок</Button>
            <Button icon={Plus} onClick={openEvent}>Событие</Button>
          </>
        }
      />

      {error && <ErrorState error={error} onRetry={refresh} />}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Store} label="Покупок сегодня" value={summary.purchases_today || 0} tone="iris" />
        <StatCard icon={Coins} label="Потрачено монет" value={summary.coins_spent || 0} hint="За всё время" tone="gold" />
        <StatCard icon={Gift} label="Подарков ждут" value={summary.pending || 0} hint={`${summary.today || 0} за сегодня`} tone="cyan" />
        <StatCard icon={Trophy} label="Получено подарков" value={summary.claimed || 0} tone="green" />
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.15fr_0.85fr]">
        <Card className="p-5 sm:p-6">
          <SectionTitle eyebrow="Витрина" title="Объявление для детей" subtitle="Короткий текст появится в магазине у учеников." />
          <div className="mt-4">
            <Textarea
              value={announcement}
              onChange={(event) => setAnnouncement(event.target.value)}
              maxLength={300}
              placeholder="Например: в пятницу двойные монеты за все задания!"
            />
            <div className="mt-2 flex items-center justify-between gap-2">
              <span className="text-[10px] text-mist-600">{announcement.length} / 300</span>
              <Button size="sm" icon={Megaphone} loading={pending} onClick={saveAnnouncement}>Сохранить</Button>
            </div>
          </div>
        </Card>

        <Card className="p-5 sm:p-6">
          <SectionTitle eyebrow="День" title="Товар дня" subtitle="Выделяется на главной магазина." />
          <div className="mt-4">
            <Select value={featured} onChange={(event) => saveFeatured(event.target.value)}>
              <option value="">Без товара дня</option>
              {catalog.map((item) => (
                <option key={item.key} value={item.key}>{item.icon} {item.name} · {item.final_coins} 🪙</option>
              ))}
            </Select>
            {featured && (
              <p className="mt-2 flex items-center gap-1.5 text-[11px] text-amber-200">
                <Star size={12} /> Сейчас выделен: {catalog.find((item) => item.key === featured)?.name || featured}
              </p>
            )}
          </div>
        </Card>
      </div>

      <Tabs
        tabs={[
          { key: "catalog", label: "Каталог", count: catalog.length },
          { key: "events", label: "События", count: events.length },
          { key: "gifts", label: "Подарки", count: gifts.length },
          { key: "board", label: "Лидеры", count: board.length },
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === "catalog" && (
        <div className="space-y-4">
          <Card className="space-y-3 p-4">
            <SearchBox value={search} onChange={setSearch} placeholder="Товар, ключ или описание…" />
            <div className="no-scrollbar flex gap-1 overflow-x-auto">
              <button onClick={() => setCategory("all")} className={`shrink-0 rounded-lg border px-2.5 py-1.5 text-[11px] font-semibold ${category === "all" ? "border-iris-400/40 bg-iris-500/15 text-white" : "border-white/8 text-mist-500"}`}>
                Все · {catalog.length}
              </button>
              {categories.map((item) => (
                <button key={item.key} onClick={() => setCategory(item.key)} className={`shrink-0 rounded-lg border px-2.5 py-1.5 text-[11px] font-semibold ${category === item.key ? "border-iris-400/40 bg-iris-500/15 text-white" : "border-white/8 text-mist-500"}`}>
                  {item.icon} {item.name}
                </button>
              ))}
            </div>
          </Card>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {visibleCatalog.map((item) => (
              <Card key={item.key} className="flex flex-col p-4">
                <div className="flex items-start gap-3">
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-xl">{item.icon}</span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-bold text-white">{item.name}</p>
                    <p className="truncate text-[10px] text-mist-600">{categoryIcon(categories, item.category)} {categoryName(categories, item.category)} · {item.key}</p>
                  </div>
                  <Badge tone={item.is_active ? "green" : "rose"}>{item.is_active ? "вкл" : "выкл"}</Badge>
                </div>
                <p className="mt-2 line-clamp-2 text-[11px] leading-relaxed text-mist-500">{item.tagline || item.description}</p>
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  <Badge tone="gold"><Coin value={item.final_coins} /></Badge>
                  {item.xp ? <Badge tone="iris"><Xp value={item.xp} /></Badge> : null}
                  <Badge>ур. {item.override?.level ?? item.level}</Badge>
                  {item.override?.discount_percent ? <Badge tone="rose">−{item.override.discount_percent}%</Badge> : null}
                  {item.override ? <Badge tone="cyan">настроен</Badge> : null}
                </div>
                <div className="mt-auto flex gap-1.5 pt-3">
                  <Button size="sm" variant="ghost" icon={Pencil} onClick={() => openItem(item)}>Изменить</Button>
                  {item.override && <IconButton icon={RotateCcw} label="Сбросить" onClick={() => resetItem(item)} />}
                </div>
              </Card>
            ))}
          </div>
          {visibleCatalog.length === 0 && <Card><EmptyState icon="🛍" title="Ничего не нашлось" text="Смените категорию или запрос." /></Card>}
        </div>
      )}

      {tab === "events" && (
        <div className="grid gap-3 sm:grid-cols-2">
          {events.map((event) => (
            <Card key={event.id} className={`p-5 ${event.is_active ? "border-amber-400/20 bg-amber-500/[0.03]" : ""}`}>
              <div className="flex items-start justify-between gap-3">
                <span className="flex h-11 w-11 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-xl">{event.icon}</span>
                <Badge tone={event.is_active ? "gold" : ""}>{event.is_active ? "идёт" : "завершено"}</Badge>
              </div>
              <h3 className="mt-3 font-display text-sm font-semibold text-white">{event.title}</h3>
              <p className="mt-1 text-[11px] text-mist-500">{event.description || EVENT_KINDS.find((kind) => kind.key === event.kind)?.label}</p>
              <p className="mt-2 text-[10px] text-mist-600">
                {formatDate(event.starts_on)} — {formatDate(event.ends_on)} · {event.kind === "discount" ? `−${event.value}%` : `×${event.value}`}
              </p>
              {event.is_active && (
                <Button size="sm" variant="ghost" icon={X} className="mt-3" onClick={() => stopEvent(event)}>Остановить</Button>
              )}
            </Card>
          ))}
          {events.length === 0 && <Card className="sm:col-span-2"><EmptyState icon="🎉" title="Событий пока нет" text="Запустите двойные монеты или скидку — дети увидят это в магазине." action={<Button icon={Plus} onClick={openEvent}>Запустить событие</Button>} /></Card>}
        </div>
      )}

      {tab === "gifts" && (
        <div className="space-y-2.5">
          {gifts.map((gift) => (
            <Card key={gift.id} className="p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <Avatar emoji={gift.learner_avatar || "🎁"} size={42} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-bold text-white">{gift.learner_name}</p>
                    <Badge tone={gift.status === "pending" ? "gold" : gift.status === "claimed" ? "green" : "rose"}>{gift.status === "pending" ? "ждёт" : gift.status === "claimed" ? "получен" : "отменён"}</Badge>
                    <Badge>{gift.icon} {gift.name}</Badge>
                  </div>
                  <p className="mt-1 text-[11px] text-mist-500">
                    {gift.reason || gift.tagline}
                    {gift.coins ? ` · +${gift.coins} 🪙` : ""}
                    {gift.xp ? ` · +${gift.xp} XP` : ""}
                  </p>
                  {gift.message && <p className="mt-0.5 text-[10px] text-mist-600">«{gift.message}»</p>}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-mist-600">{formatDateTime(gift.created_at)}</span>
                  {gift.status === "pending" && <IconButton icon={X} label="Отменить подарок" className="text-rose-300" onClick={() => cancelGift(gift)} />}
                </div>
              </div>
            </Card>
          ))}
          {gifts.length === 0 && <Card><EmptyState icon="🎁" title="Подарков пока нет" text="Отправьте ребёнку награду за старание." action={<Button icon={Gift} onClick={() => openGift()}>Отправить подарок</Button>} /></Card>}
        </div>
      )}

      {tab === "board" && (
        <Card className="p-2">
          {board.map((learner) => (
            <div key={`${learner.id}-${learner.account_login}`} className="flex flex-col gap-3 rounded-xl px-3 py-3 transition hover:bg-white/[0.025] sm:flex-row sm:items-center">
              <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-xs font-bold ${
                learner.rank === 1 ? "bg-amber-400/20 text-amber-200" : learner.rank === 2 ? "bg-slate-300/20 text-slate-100" : learner.rank === 3 ? "bg-orange-400/20 text-orange-200" : "bg-white/5 text-mist-400"
              }`}>
                {learner.rank}
              </span>
              <Avatar emoji={learner.avatar || "🦊"} size={40} seed={learner.account_login} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-bold text-white">{learner.name}</p>
                <p className="text-[10px] text-mist-600">@{learner.account_login || "—"} · {learner.grade} класс</p>
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                <Badge tone="gold"><Coin value={learner.coins} /></Badge>
                <Badge tone="iris">{learner.total_xp || learner.xp} XP</Badge>
                <Badge tone={scoreTone(learner.accuracy)}>{learner.accuracy}%</Badge>
                <Badge>{plural(learner.attempts || 0, ["попытка", "попытки", "попыток"])}</Badge>
                <Button size="sm" variant="ghost" icon={Gift} onClick={() => openGift(learner.id)}>Подарить</Button>
              </div>
            </div>
          ))}
          {board.length === 0 && <EmptyState icon="🏆" title="Лидеров пока нет" text="Как только появятся попытки, здесь будет рейтинг." />}
        </Card>
      )}

      <Modal
        open={Boolean(itemModal && itemForm)}
        onClose={() => { setItemModal(null); setItemForm(null); }}
        title={itemModal?.name || "Товар"}
        description={itemModal?.key}
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => { setItemModal(null); setItemForm(null); }}>Отмена</Button>
            <Button icon={Check} loading={pending} onClick={saveItem}>Сохранить</Button>
          </>
        }
      >
        {itemForm && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Название"><Input value={itemForm.name} onChange={(event) => setItemForm((current) => ({ ...current, name: event.target.value }))} /></Field>
            <Field label="Иконка"><Input value={itemForm.icon} onChange={(event) => setItemForm((current) => ({ ...current, icon: event.target.value }))} maxLength={8} /></Field>
            <Field label="Подпись" className="sm:col-span-2"><Input value={itemForm.tagline} onChange={(event) => setItemForm((current) => ({ ...current, tagline: event.target.value }))} /></Field>
            <Field label="Описание" className="sm:col-span-2"><Textarea value={itemForm.description} onChange={(event) => setItemForm((current) => ({ ...current, description: event.target.value }))} /></Field>
            <Field label="Цена, монеты"><Input type="number" min={0} value={itemForm.price_coins} onChange={(event) => setItemForm((current) => ({ ...current, price_coins: event.target.value }))} /></Field>
            <Field label="Цена, опыт" hint="0 — без оплаты опытом."><Input type="number" min={0} value={itemForm.price_xp} onChange={(event) => setItemForm((current) => ({ ...current, price_xp: event.target.value }))} /></Field>
            <Field label="Скидка, %" hint="0–90."><Input type="number" min={0} max={90} value={itemForm.discount_percent} onChange={(event) => setItemForm((current) => ({ ...current, discount_percent: event.target.value }))} /></Field>
            <Field label="Минимальный уровень"><Input type="number" min={1} value={itemForm.level} onChange={(event) => setItemForm((current) => ({ ...current, level: event.target.value }))} /></Field>
            <div className="sm:col-span-2">
              <Toggle
                value={itemForm.is_active}
                onChange={(value) => setItemForm((current) => ({ ...current, is_active: value }))}
                label="Товар доступен в магазине"
                text="Выключенные товары не показываются детям."
              />
            </div>
          </div>
        )}
      </Modal>

      <Modal
        open={eventOpen}
        onClose={() => setEventOpen(false)}
        title="Новое событие"
        description="Временный бонус для всех учеников."
        size="lg"
        footer={<><Button variant="ghost" onClick={() => setEventOpen(false)}>Отмена</Button><Button icon={Plus} loading={pending} onClick={submitEvent}>Запустить</Button></>}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Название" className="sm:col-span-2">
            <Input value={eventForm.title} onChange={(event) => setEventForm((current) => ({ ...current, title: event.target.value }))} placeholder="Неделя двойных монет" />
          </Field>
          <Field label="Тип">
            <Select value={eventForm.kind} onChange={(event) => setEventForm((current) => ({ ...current, kind: event.target.value, value: event.target.value === "discount" ? 20 : 2 }))}>
              {EVENT_KINDS.map((kind) => <option key={kind.key} value={kind.key}>{kind.label}</option>)}
            </Select>
          </Field>
          <Field label={eventForm.kind === "discount" ? "Скидка, %" : "Множитель"} hint={eventForm.kind === "discount" ? "5–70%" : "1.1–5"} >
            <Input type="number" step="0.1" value={eventForm.value} onChange={(event) => setEventForm((current) => ({ ...current, value: event.target.value }))} />
          </Field>
          <Field label="Начало"><Input type="date" value={eventForm.starts_on} onChange={(event) => setEventForm((current) => ({ ...current, starts_on: event.target.value }))} /></Field>
          <Field label="Окончание"><Input type="date" value={eventForm.ends_on} onChange={(event) => setEventForm((current) => ({ ...current, ends_on: event.target.value }))} /></Field>
          <Field label="Иконка"><Input value={eventForm.icon} onChange={(event) => setEventForm((current) => ({ ...current, icon: event.target.value }))} maxLength={8} /></Field>
          <Field label="Описание" className="sm:col-span-2">
            <Textarea value={eventForm.description} onChange={(event) => setEventForm((current) => ({ ...current, description: event.target.value }))} placeholder="Что происходит и почему это классно…" />
          </Field>
        </div>
      </Modal>

      <Modal
        open={giftOpen}
        onClose={() => setGiftOpen(false)}
        title="Подарок ребёнку"
        description="Предмет и/или бонусные монеты с опытом."
        size="lg"
        footer={<><Button variant="ghost" onClick={() => setGiftOpen(false)}>Отмена</Button><Button icon={Gift} loading={pending} onClick={submitGift}>Отправить</Button></>}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Ребёнок" className="sm:col-span-2">
            <Select value={giftForm.learner_id} onChange={(event) => setGiftForm((current) => ({ ...current, learner_id: event.target.value }))}>
              <option value="">Выберите ребёнка</option>
              {board.map((learner) => (
                <option key={`${learner.id}-${learner.account_login}`} value={learner.id}>
                  {learner.name} · {learner.grade} класс {learner.account_login ? `(@${learner.account_login})` : ""}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Предмет" className="sm:col-span-2">
            <Select value={giftForm.item_key} onChange={(event) => setGiftForm((current) => ({ ...current, item_key: event.target.value }))}>
              <option value="">Без предмета — только бонусы</option>
              {catalog.map((item) => <option key={item.key} value={item.key}>{item.icon} {item.name}</option>)}
            </Select>
          </Field>
          <Field label="Причина">
            <Select value={giftForm.reason} onChange={(event) => setGiftForm((current) => ({ ...current, reason: event.target.value }))}>
              <option value="">Без причины</option>
              {reasons.map((reason) => <option key={reason.text} value={reason.text}>{reason.icon} {reason.text}</option>)}
            </Select>
          </Field>
          <Field label="Монеты"><Input type="number" min={0} value={giftForm.coins} onChange={(event) => setGiftForm((current) => ({ ...current, coins: event.target.value }))} /></Field>
          <Field label="Опыт"><Input type="number" min={0} value={giftForm.xp} onChange={(event) => setGiftForm((current) => ({ ...current, xp: event.target.value }))} /></Field>
          <Field label="Сообщение" className="sm:col-span-2">
            <Textarea value={giftForm.message} onChange={(event) => setGiftForm((current) => ({ ...current, message: event.target.value }))} placeholder="Тёплые слова, которые увидит ребёнок…" />
          </Field>
        </div>
      </Modal>
    </div>
  );
}
