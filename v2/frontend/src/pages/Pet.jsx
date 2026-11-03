import { Link } from "react-router-dom";
import { ArrowRight, Heart, PawPrint, ShoppingBag, Sparkles, Star } from "lucide-react";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, Progress, SectionTitle, Skeleton } from "../components/ui";
import { useAction, useApi, useSession, toast } from "../lib/hooks";
import { api, invalidate } from "../lib/api";

export default function PetPage() {
  const { refreshSession } = useSession();
  const { data, loading, error, refresh } = useApi("/pet");
  const { pending, run } = useAction();
  const pet = data?.pet;

  const pat = async () => {
    try {
      const payload = await run(() => api.post("/pet/pat", {}));
      invalidate("/pet");
      await refresh();
      refreshSession().catch(() => {});
      toast(payload.message || (payload.xp ? `+${payload.xp} XP` : "Питомец доволен"), "success");
    } catch (err) {
      toast(err.message || "Не удалось погладить питомца", "error");
    }
  };

  if (loading && !data) {
    return <div className="space-y-4"><Skeleton className="h-72 w-full" /><Skeleton className="h-48 w-full" /></div>;
  }

  if (error && !data) {
    return <ErrorState error={error} onRetry={refresh} />;
  }

  if (!pet) {
    return (
      <div className="space-y-6">
        <PageHeader title="Питомец" subtitle="Живой спутник, который растёт от ваших верных ответов." />
        <Card className="relative overflow-hidden p-8 text-center sm:p-12">
          <div className="pointer-events-none absolute inset-x-0 -top-24 mx-auto h-64 w-64 rounded-full bg-amber-400/15 blur-3xl" />
          <div className="relative">
            <div className="mx-auto flex h-28 w-28 items-center justify-center rounded-[2rem] border border-white/10 bg-gradient-to-br from-amber-300/20 to-iris-500/10 text-6xl">
              🥚
            </div>
            <h2 className="mt-6 font-display text-2xl font-semibold text-white">Яйцо ждёт хозяина</h2>
            <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-mist-400">
              Выберите питомца в магазине — кота, сову или дракона. Он будет расти
              вместе с вами и иногда дарить опыт за заботу.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              <Link to="/app/shop"><Button icon={ShoppingBag}>Выбрать питомца</Button></Link>
              <Link to="/app/learn"><Button variant="ghost">К тренировкам</Button></Link>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={pet.name}
        subtitle={pet.tip || "Питомец растёт от верных ответов. Заглядывайте каждый день."}
        actions={pet.can_pat ? <Badge tone="gold"><Sparkles size={12} /> +{pet.xp_reward} XP сегодня</Badge> : <Badge tone="green">обнимашки на сегодня</Badge>}
      />

      <Card className="relative overflow-hidden p-7 sm:p-10">
        <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-amber-400/15 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-28 -left-16 h-64 w-64 rounded-full bg-iris-500/15 blur-3xl" />
        <div className="relative flex flex-col items-center gap-6 sm:flex-row sm:items-center sm:gap-10">
          <div className="relative">
            <div className="absolute inset-0 rounded-full bg-amber-400/20 blur-2xl" />
            <div className={`relative flex h-40 w-40 items-center justify-center rounded-[2.5rem] border border-white/12 bg-gradient-to-br from-amber-300/20 to-iris-500/10 text-7xl ${pet.can_pat ? "animate-pulse-soft" : ""}`}>
              {pet.stage_icon || pet.icon}
            </div>
            {pet.grew && <Badge tone="gold" className="mt-3">вырос!</Badge>}
          </div>

          <div className="min-w-0 flex-1 text-center sm:text-left">
            <div className="flex flex-wrap items-center justify-center gap-2 sm:justify-start">
              <Badge tone="iris"><Star size={11} /> стадия {pet.index}</Badge>
              <Badge tone="gold">{pet.stage_name}</Badge>
            </div>
            <h2 className="mt-3 font-display text-2xl font-semibold text-white">
              {pet.grew ? "Я подрос!" : pet.can_pat ? "Хочешь обняться?" : "Спасибо за заботу"}
            </h2>
            <p className="mt-2 max-w-md text-sm leading-relaxed text-mist-400">{pet.tip}</p>

            <div className="mx-auto mt-5 max-w-md sm:mx-0">
              <div className="mb-1.5 flex items-center justify-between text-[11px] font-bold text-mist-500">
                <span>Прогресс роста</span>
                <span>{pet.max ? "максимум" : `${pet.progress} / ${pet.next_at}`}</span>
              </div>
              <Progress value={pet.percent} />
            </div>

            <div className="mt-5 flex flex-wrap justify-center gap-2 sm:justify-start">
              <Button icon={Heart} loading={pending} disabled={!pet.can_pat} onClick={pat}>
                {pet.can_pat ? "Погладить" : "Уже сегодня"}
              </Button>
              <Link to="/app/shop"><Button variant="ghost" icon={ShoppingBag}>Магазин питомцев</Button></Link>
            </div>
          </div>
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="p-5 sm:p-6">
          <SectionTitle eyebrow="Забота" title="Как растёт питомец" subtitle="Каждый верный ответ добавляет ему немного роста." />
          <div className="mt-4 space-y-2.5">
            {[
              ["✅", "Решайте тренировки", "Верные ответы приносят прогресс питомцу."],
              ["🔥", "Держите серию", "Ежедневные занятия ускоряют рост."],
              ["💛", "Заходите каждый день", "Раз в день питомец делится опытом за ласку."],
            ].map(([icon, title, text]) => (
              <div key={title} className="flex items-start gap-3 rounded-2xl border border-white/8 bg-white/[0.025] p-3.5">
                <span className="text-lg">{icon}</span>
                <div>
                  <p className="text-xs font-bold text-white">{title}</p>
                  <p className="mt-0.5 text-[11px] leading-relaxed text-mist-500">{text}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-5 sm:p-6">
          <SectionTitle eyebrow="Дальше" title="Чем заняться" />
          <div className="mt-4 space-y-2">
            <Link to="/app/learn" className="flex items-center gap-3 rounded-xl border border-white/8 bg-white/[0.025] px-3.5 py-3 transition hover:border-iris-400/30">
              <PawPrint size={16} className="text-iris-300" />
              <div className="flex-1">
                <p className="text-xs font-bold text-white">Покормить ростом</p>
                <p className="text-[10px] text-mist-500">Решите несколько заданий</p>
              </div>
              <ArrowRight size={13} className="text-mist-600" />
            </Link>
            <Link to="/app/schedule" className="flex items-center gap-3 rounded-xl border border-white/8 bg-white/[0.025] px-3.5 py-3 transition hover:border-iris-400/30">
              <Sparkles size={16} className="text-cyan-300" />
              <div className="flex-1">
                <p className="text-xs font-bold text-white">Планы на день</p>
                <p className="text-[10px] text-mist-500">Расписание уроков</p>
              </div>
              <ArrowRight size={13} className="text-mist-600" />
            </Link>
          </div>
        </Card>
      </div>

      {!pet.can_pat && (
        <Card>
          <EmptyState icon="🌙" title="На сегодня всё" text="Питомец уже получил свою порцию обнимашек. Возвращайтесь завтра." />
        </Card>
      )}
    </div>
  );
}
