import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  Check,
  Crown,
  Gift,
  Lock,
  Package,
  PawPrint,
  ShoppingBag,
  Sparkles,
  Star,
  Wand2,
} from "lucide-react";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Modal,
  PageHeader,
  Progress,
  SectionTitle,
  Skeleton,
  StatCard,
  Tabs,
} from "../components/ui";
import { useAction, useApi, useSession, toast } from "../lib/hooks";
import { api, invalidate } from "../lib/api";
import { plural } from "../lib/format";

function priceLabel(item) {
  if (item.price_coins && item.price_xp) return `${item.price_coins} 🪙 + ${item.price_xp} ✨`;
  if (item.price_coins) return `${item.price_coins} 🪙`;
  return `${item.price_xp} ✨`;
}

function ItemCard({ item, pending, onBuy, onEquip, onAvatar }) {
  const isAvatar = item.kind === "avatar_pack";
  return (
    <Card className="relative flex flex-col overflow-hidden p-4">
      {item.discount > 0 && (
        <span className="absolute right-3 top-3 rounded-lg bg-rose-500/20 px-2 py-0.5 text-[10px] font-bold text-rose-200">
          −{item.discount}%
        </span>
      )}
      <div className="flex items-start gap-3">
        <span className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-2xl">
          {item.icon || "🎁"}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-bold text-white">{item.name}</p>
          <p className="mt-0.5 text-[11px] text-mist-500">{item.tagline || item.rarity_name}</p>
        </div>
      </div>
      <p className="mt-3 line-clamp-2 flex-1 text-[11px] leading-relaxed text-mist-500">{item.description}</p>

      {isAvatar && item.avatars?.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {item.avatars.map((avatar) => (
            <span key={avatar} className="flex h-7 w-7 items-center justify-center rounded-lg border border-white/8 bg-white/5 text-sm">{avatar}</span>
          ))}
        </div>
      )}

      <div className="mt-4 flex items-center justify-between gap-2">
        <div className="min-w-0">
          {item.owned ? (
            <Badge tone={item.equipped ? "green" : "iris"}>{item.equipped ? "надето" : "куплено"}</Badge>
          ) : item.locked ? (
            <span className="text-[11px] font-semibold text-mist-500">🔒 {item.reason || `с ${item.level} уровня`}</span>
          ) : (
            <span className="text-sm font-bold text-white">{priceLabel(item)}</span>
          )}
          {item.repeatable && item.quantity ? <span className="ml-1.5 text-[10px] text-mist-600">×{item.quantity}</span> : null}
        </div>

        {item.owned && item.slot && !item.equipped ? (
          <Button size="sm" variant="ghost" loading={pending} onClick={() => onEquip(item)}>Надеть</Button>
        ) : item.owned && item.equipped ? (
          <Button size="sm" variant="plain" icon={Check} disabled>Активно</Button>
        ) : item.owned && isAvatar ? (
          <Button size="sm" variant="ghost" loading={pending} onClick={() => onAvatar(item.avatars?.[0])}>Выбрать</Button>
        ) : item.repeatable && item.owned ? (
          <Button size="sm" variant="ghost" loading={pending} onClick={() => onBuy(item)}>Ещё</Button>
        ) : (
          <Button size="sm" loading={pending} disabled={!item.can_buy || item.owned} onClick={() => onBuy(item)}>
            {item.locked ? "Закрыто" : item.can_buy ? "Купить" : "Мало монет"}
          </Button>
        )}
      </div>
      {item.owned && item.repeatable ? (
        <p className="mt-2 text-[10px] text-mist-600">{item.reason || "Можно покупать повторно"}</p>
      ) : null}
    </Card>
  );
}

export default function ShopPage() {
  const { refreshSession } = useSession();
  const { data, loading, error, refresh, setData } = useApi("/shop");
  const [tab, setTab] = useState("");
  const [detail, setDetail] = useState(null);
  const { pending, run } = useAction();

  const categories = data?.categories || [];
  const activeKey = tab || categories[0]?.key || "";
  const active = categories.find((category) => category.key === activeKey);
  const featured = data?.featured;
  const chest = data?.chest;
  const gifts = data?.gifts || [];
  const avatars = data?.avatars || [];
  const decor = data?.decor || {};

  const apply = (payload) => {
    if (payload?.shop) setData((current) => (current ? { ...current, ...payload.shop } : payload.shop));
    invalidate("/shop");
    refreshSession().catch(() => {});
  };

  const buy = async (item) => {
    setDetail(null);
    try {
      const payload = await run(() => api.post("/shop/buy", { item_key: item.key }));
      apply(payload);
      toast(payload.message || `Куплено: ${item.name}`, "success");
    } catch (err) {
      toast(err.message || "Не удалось купить", "error");
    }
  };

  const equip = async (item) => {
    try {
      const payload = await run(() => api.post("/shop/equip", { item_key: item.key }));
      apply(payload);
      toast(payload.message || "Готово", "success");
    } catch (err) {
      toast(err.message || "Не удалось надеть", "error");
    }
  };

  const setAvatar = async (avatar) => {
    if (!avatar) return;
    try {
      const payload = await run(() => api.post("/shop/avatar", { avatar }));
      apply(payload);
      toast(`Аватар обновлён: ${avatar}`, "success");
    } catch (err) {
      toast(err.message || "Не удалось сменить аватар", "error");
    }
  };

  const claimChest = async () => {
    try {
      const payload = await run(() => api.post("/shop/chest", {}));
      apply(payload);
      toast(payload.message || `Сундук: +${payload.coins || 0} 🪙 и +${payload.xp || 0} ✨`, "success");
    } catch (err) {
      toast(err.message || "Сундук уже открыт", "error");
    }
  };

  const claimGift = async (gift) => {
    try {
      const payload = await run(() => api.post("/shop/gifts/claim", { gift_id: gift.id }));
      apply(payload);
      toast(payload.message || "Подарок открыт", "success");
    } catch (err) {
      toast(err.message || "Не удалось открыть подарок", "error");
    }
  };

  if (loading && !data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-44 w-full" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-28" />)}
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error && !data) {
    return <ErrorState error={error} onRetry={refresh} />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Магазин"
        subtitle="Монеты за старания превращаются в усилители, наряды и питомцев. Здесь нет платежей — только заработанное."
        actions={
          <div className="flex items-center gap-2">
            <Badge tone="gold">🪙 {Number(data?.balance?.coins || 0).toLocaleString("ru-RU")}</Badge>
            <Badge tone="iris">✨ {Number(data?.total_xp || 0).toLocaleString("ru-RU")}</Badge>
          </div>
        }
      />

      {data?.announcement ? (
        <div className="flex items-start gap-2.5 rounded-2xl border border-iris-400/25 bg-iris-500/[0.08] px-4 py-3 text-xs leading-relaxed text-mist-300">
          <Sparkles size={15} className="mt-0.5 shrink-0 text-iris-300" />
          {data.announcement}
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Star} label="Уровень" value={data?.level || 1} hint={`${data?.level_info?.title || "Новичок"} · до следующего ${data?.level_info?.need ?? 0} XP`} tone="iris" />
        <StatCard icon={ShoppingBag} label="Монеты" value={Number(data?.balance?.coins || 0).toLocaleString("ru-RU")} hint={`Скидка дня ${data?.discount_percent || 0}%`} tone="gold" />
        <StatCard icon={Package} label="Коллекция" value={`${data?.collection?.percent || 0}%`} hint={`${data?.collection?.owned || 0} из ${data?.collection?.total || 0} предметов`} tone="cyan" />
        <StatCard icon={Gift} label="Подарки" value={data?.gift_count || 0} hint={data?.gift_count ? "Ждут в магазине" : "Пока нет новых"} tone="green" />
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.25fr_0.75fr]">
        <Card className="relative overflow-hidden p-6">
          <div className="pointer-events-none absolute -right-20 -top-24 h-64 w-64 rounded-full bg-amber-400/15 blur-3xl" />
          <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center">
            <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-3xl border border-amber-300/25 bg-gradient-to-br from-amber-300/20 to-iris-500/10 text-4xl">
              🎁
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-amber-300">Сундук дня</p>
              <h2 className="mt-1 font-display text-xl font-semibold text-white">
                {chest?.available ? "Награда уже ждёт" : "Сундук открыт"}
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-mist-500">
                {chest?.available
                  ? `Внутри от ${chest.min_coins} до ${chest.max_coins} монет и немного опыта. Открывается раз в день.`
                  : "Возвращайтесь завтра — сундук наполнится снова."}
              </p>
            </div>
            <Button icon={Gift} loading={pending} disabled={!chest?.available} onClick={claimChest}>
              {chest?.available ? "Открыть" : "Завтра"}
            </Button>
          </div>
        </Card>

        <Card className="relative overflow-hidden p-5">
          <SectionTitle eyebrow="Питомец" title={data?.pet?.name || "Пока никого"} />
          <div className="mt-4 flex items-center gap-3">
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-3xl">
              {data?.pet?.icon || "🥚"}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-white">{data?.pet ? "Живёт у вас" : "Купите питомца в магазине"}</p>
              <p className="mt-0.5 text-[11px] text-mist-500">{data?.pet?.stage_name || "Он будет расти от ваших тренировок."}</p>
            </div>
            <Link to="/app/pet" className="icon-btn h-9 w-9"><ArrowRight size={15} /></Link>
          </div>
        </Card>
      </div>

      {gifts.length > 0 && (
        <Card className="p-5">
          <SectionTitle eyebrow="Подарки" title="Вам кое-что передали" subtitle="Подарки от учителя и родителей за старания." />
          <div className="mt-4 grid gap-2.5 sm:grid-cols-2">
            {gifts.map((gift) => (
              <div key={gift.id} className="flex items-center gap-3 rounded-2xl border border-rose-400/20 bg-rose-500/[0.05] p-3.5">
                <span className="text-2xl">{gift.icon || "🎁"}</span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-bold text-white">{gift.title || "Подарок"}</p>
                  <p className="truncate text-[11px] text-mist-500">{gift.message || gift.from_name || "За старания"}</p>
                </div>
                <Button size="sm" loading={pending} onClick={() => claimGift(gift)}>Открыть</Button>
              </div>
            ))}
          </div>
        </Card>
      )}

      {featured && (
        <Card className="relative overflow-hidden p-6" style={{ background: "linear-gradient(140deg, rgba(139,123,255,.14), rgba(34,211,238,.05) 55%, rgba(255,255,255,.015))" }}>
          <div className="pointer-events-none absolute -bottom-24 -right-16 h-64 w-64 rounded-full bg-iris-500/20 blur-3xl" />
          <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center">
            <span className="flex h-16 w-16 items-center justify-center rounded-3xl border border-white/12 bg-ink-900/40 text-3xl">{featured.icon}</span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="gold"><Crown size={11} /> выбор дня</Badge>
                {featured.discount > 0 && <Badge tone="rose">−{featured.discount}%</Badge>}
              </div>
              <h3 className="mt-2 font-display text-lg font-semibold text-white">{featured.name}</h3>
              <p className="mt-1 text-xs leading-relaxed text-mist-400">{featured.description}</p>
            </div>
            <div className="flex flex-col items-stretch gap-2 sm:items-end">
              <span className="text-sm font-bold text-white">{priceLabel(featured)}</span>
              <Button
                icon={ShoppingBag}
                loading={pending}
                disabled={featured.owned || !featured.can_buy}
                onClick={() => buy(featured)}
              >
                {featured.owned ? "Уже есть" : featured.can_buy ? "Забрать" : featured.reason || "Закрыто"}
              </Button>
            </div>
          </div>
        </Card>
      )}

      <Tabs
        tabs={categories.map((category) => ({
          key: category.key,
          label: `${category.icon} ${category.name}`,
          count: category.items.length,
        }))}
        value={activeKey}
        onChange={setTab}
      />

      {active && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {active.items.map((item) => (
            <ItemCard
              key={item.key}
              item={item}
              pending={pending}
              onBuy={(value) => (value.can_buy ? buy(value) : setDetail(value))}
              onEquip={equip}
              onAvatar={setAvatar}
            />
          ))}
        </div>
      )}

      <Card className="p-5 sm:p-6">
        <SectionTitle
          eyebrow="Аватары"
          title="Как вы выглядите"
          subtitle="Смена аватара бесплатна. Новые открываются за уровни и в наборах."
          action={<Badge tone="iris">{avatars.length} доступно</Badge>}
        />
        <div className="mt-5 flex flex-wrap gap-2">
          {avatars.map((avatar) => (
            <button
              key={avatar}
              onClick={() => setAvatar(avatar)}
              className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.03] text-2xl transition hover:border-iris-400/40 hover:bg-iris-500/10"
              title="Выбрать аватар"
            >
              {avatar}
            </button>
          ))}
          {avatars.length === 0 && <EmptyState icon="🦊" title="Аватары недоступны" text="Проверьте подключение и обновите страницу." />}
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="p-5">
          <SectionTitle eyebrow="Сейчас надето" title="Образ профиля" />
          <div className="mt-4 space-y-2">
            {[
              ["Рамка", decor.frame ? "активна" : "нет"],
              ["Тема", decor.theme || "стандартная"],
              ["Титул", decor.title || "без титула"],
              ["Питомец", decor.pet?.name || "нет"],
            ].map(([label, value]) => (
              <div key={label} className="flex items-center justify-between rounded-xl border border-white/7 bg-white/[0.02] px-3.5 py-2.5">
                <span className="text-xs text-mist-500">{label}</span>
                <span className="text-xs font-bold text-white">{value}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-5">
          <SectionTitle eyebrow="История" title="Последние подарки" />
          <div className="mt-4 space-y-2">
            {(data?.gift_history || []).length === 0 && (
              <p className="rounded-xl border border-white/7 bg-white/[0.02] px-3.5 py-4 text-center text-xs text-mist-500">
                Подарков пока не было — старайтесь, и они появятся.
              </p>
            )}
            {(data?.gift_history || []).slice(0, 5).map((gift) => (
              <div key={gift.id} className="flex items-center gap-2.5 rounded-xl border border-white/7 bg-white/[0.02] px-3.5 py-2.5">
                <span className="text-lg">{gift.icon || "🎁"}</span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-semibold text-white">{gift.title || "Подарок"}</p>
                  <p className="text-[10px] text-mist-600">{gift.status === "claimed" ? "открыт" : gift.status === "pending" ? "ждёт" : "отменён"}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Modal
        open={Boolean(detail)}
        onClose={() => setDetail(null)}
        title={detail?.name || "Предмет"}
        description={detail?.tagline}
        footer={<Button onClick={() => setDetail(null)}>Понятно</Button>}
      >
        {detail && (
          <div className="space-y-4">
            <div className="flex items-center gap-4">
              <span className="flex h-16 w-16 items-center justify-center rounded-3xl border border-white/10 bg-white/5 text-3xl">{detail.icon}</span>
              <div>
                <Badge tone="gold">{detail.rarity_icon} {detail.rarity_name}</Badge>
                <p className="mt-1.5 text-sm font-bold text-white">{priceLabel(detail)}</p>
              </div>
            </div>
            <p className="text-sm leading-relaxed text-mist-400">{detail.description}</p>
            {detail.reason && <p className="text-xs font-semibold text-amber-300">{detail.reason}</p>}
            <Progress value={detail.level ? Math.min(100, (data?.level || 1) / detail.level * 100) : 100} />
            <p className="text-[11px] text-mist-600">Откроется на {detail.level} уровне. Сейчас у вас {data?.level || 1}.</p>
          </div>
        )}
      </Modal>
    </div>
  );
}
