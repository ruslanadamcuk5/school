import { useState } from "react";
import { Link } from "react-router-dom";
import {
  AtSign,
  Award,
  CalendarDays,
  Check,
  Copy,
  Flame,
  GraduationCap,
  LogOut,
  Mail,
  ShieldCheck,
  Sparkles,
  Target,
  Trophy,
  UserRound,
} from "lucide-react";
import { Avatar, Badge, Button, Card, Field, Input, PageHeader, Progress, SectionTitle, StatCard } from "../components/ui";
import { useAction, useApi, useSession, toast } from "../lib/hooks";
import { api, invalidate } from "../lib/api";
import { ROLE_LABEL, formatDate, levelInfo, plural } from "../lib/format";

export default function ProfilePage() {
  const { session, refreshSession, signOut, updateLearner } = useSession();
  const user = session?.user;
  const learner = session?.learner;
  const isStudent = user?.role === "student";
  const { data: map } = useApi(isStudent ? "/map" : "/notifications", { enabled: Boolean(user) });
  const { data: shop } = useApi("/shop", { enabled: isStudent });
  const { pending, run } = useAction();
  const [name, setName] = useState(learner?.name || user?.first_name || "");
  const [copied, setCopied] = useState(false);
  const stats = map?.stats || {};
  const level = levelInfo(stats.xp ?? learner?.xp_total ?? 0);
  const avatars = shop?.avatars || [];

  const saveName = async () => {
    const value = name.trim();
    if (!value) {
      toast("Имя не может быть пустым", "info");
      return;
    }
    try {
      if (isStudent && learner?.id) {
        await run(() => api.patch(`/parent/children/${learner.id}`, { name: value }));
      }
      updateLearner({ name: value });
      invalidate("/map");
      toast("Имя обновлено", "success");
    } catch (err) {
      toast(err.message || "Не удалось сохранить имя", "error");
    }
  };

  const chooseAvatar = async (avatar) => {
    try {
      const payload = await run(() => api.post("/shop/avatar", { avatar }));
      updateLearner({ avatar: payload.avatar || avatar });
      invalidate("/shop");
      toast("Аватар обновлён", "success");
    } catch (err) {
      toast(err.message || "Не удалось сменить аватар", "error");
    }
  };

  const copyCode = async () => {
    const code = user?.child_code;
    if (!code) return;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(code);
      } else {
        const area = document.createElement("textarea");
        area.value = code;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        document.body.removeChild(area);
      }
      setCopied(true);
      toast("Код скопирован", "success");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast("Не удалось скопировать — выделите код вручную", "info");
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Профиль"
        subtitle="Личные данные, прогресс и безопасность аккаунта."
        actions={<Badge tone="iris"><UserRound size={12} /> {ROLE_LABEL[user?.role] || "Профиль"}</Badge>}
      />

      <Card className="relative overflow-hidden p-5 sm:p-8">
        <div className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-iris-500/20 blur-3xl" />
        <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:gap-6">
          <Avatar
            emoji={isStudent ? learner?.avatar || "🦊" : user?.avatar || "👤"}
            size={isStudent ? 76 : 84}
            seed={user?.login}
            ring
          />
          <div className="min-w-0 flex-1">
            <h2 className="break-words font-display text-xl font-semibold text-white sm:text-2xl">
              {user?.first_name} {user?.last_name}
            </h2>
            <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-mist-500">
              <span className="inline-flex items-center gap-1"><AtSign size={12} /> {user?.login}</span>
              <span className="inline-flex items-center gap-1"><GraduationCap size={12} /> {ROLE_LABEL[user?.role]}</span>
              {user?.created_at ? <span className="inline-flex items-center gap-1"><CalendarDays size={12} /> с {formatDate(user.created_at)}</span> : null}
            </p>
            {isStudent && (
              <div className="mt-4 max-w-sm">
                <div className="mb-1.5 flex items-center justify-between text-[11px] font-bold text-mist-500">
                  <span>Уровень {level.level} · {stats.level_title || "Новичок"}</span>
                  <span>{level.percent}%</span>
                </div>
                <Progress value={level.percent} />
                <p className="mt-1.5 text-[11px] text-mist-600">Ещё {level.need} XP до уровня {level.level + 1}</p>
              </div>
            )}
          </div>
          {isStudent && (
            <div className="grid grid-cols-2 gap-2 sm:flex">
              <Link to="/app/shop" className="w-full sm:w-auto"><Button variant="ghost" icon={Sparkles} className="w-full sm:w-auto">Магазин</Button></Link>
              <Link to="/app/learn" className="w-full sm:w-auto"><Button icon={Trophy} className="w-full sm:w-auto">Учиться</Button></Link>
            </div>
          )}
        </div>
      </Card>

      {isStudent && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard icon={Trophy} label="Уровень" value={level.level} hint={stats.level_title || "Новичок"} tone="iris" />
          <StatCard icon={Flame} label="Серия" value={stats.streak_days || 0} suffix={plural(stats.streak_days || 0, ["день", "дня", "дней"])} tone="gold" />
          <StatCard icon={Target} label="Точность" value={`${stats.accuracy || 0}%`} hint={`${stats.total_correct || 0} из ${stats.total_attempts || 0}`} tone="cyan" />
          <StatCard icon={Award} label="Звёзды" value={stats.stars || 0} hint="За успешные раунды" tone="green" />
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-2">
        <Card className="p-5 sm:p-6">
          <SectionTitle eyebrow="Данные" title="Как вас зовут" subtitle="Имя видят учитель и родители." />
          <div className="mt-5 space-y-4">
            <Field label="Имя">
              <Input value={name} onChange={(event) => setName(event.target.value)} maxLength={60} />
            </Field>
            <Field label="Логин" hint="Логин меняет администратор, чтобы не потерялся доступ.">
              <Input value={user?.login || ""} disabled />
            </Field>
            <Field label="Email">
              <div className="relative">
                <Mail size={15} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-mist-500" />
                <Input value={user?.email || ""} placeholder="не указан" className="pl-9" disabled />
              </div>
            </Field>
            <Button icon={Check} loading={pending} onClick={saveName} disabled={!name.trim() || name.trim() === (learner?.name || user?.first_name)}>
              Сохранить
            </Button>
          </div>
        </Card>

        <div className="space-y-5">
          {isStudent && avatars.length > 0 && (
            <Card className="p-5 sm:p-6">
              <SectionTitle eyebrow="Аватар" title="Выберите образ" subtitle="Все доступные аватары уже открыты." />
              <div className="mt-4 flex flex-wrap gap-2">
                {avatars.map((avatar) => {
                  const active = avatar === learner?.avatar;
                  return (
                    <button
                      key={avatar}
                      onClick={() => chooseAvatar(avatar)}
                      className={`flex h-11 w-11 items-center justify-center rounded-xl border text-xl transition ${
                        active ? "border-iris-400/50 bg-iris-500/20" : "border-white/8 bg-white/[0.03] hover:border-white/20"
                      }`}
                    >
                      {avatar}
                    </button>
                  );
                })}
              </div>
            </Card>
          )}

          {isStudent && user?.child_code && (
            <Card className="border-iris-400/20 bg-iris-500/[0.045] p-5 sm:p-6">
              <SectionTitle
                eyebrow="Семья"
                title="Код для родителя"
                subtitle="Передайте его родителю — он привяжет ваш профиль и увидит прогресс."
              />
              <div className="mt-4 flex flex-col gap-2.5 sm:flex-row sm:items-center">
                <div className="min-w-0 flex-1 rounded-xl border border-iris-400/25 bg-ink-950/40 px-2.5 py-3 text-center sm:px-4">
                  <p className="break-all font-display text-xl font-semibold tracking-[0.18em] text-white sm:text-2xl sm:tracking-[0.3em]">{user.child_code}</p>
                </div>
                <Button variant="ghost" icon={copied ? Check : Copy} onClick={copyCode} className="w-full sm:w-auto">
                  {copied ? "Скопировано" : "Копировать"}
                </Button>
              </div>
            </Card>
          )}

          <Card className="p-5 sm:p-6">
            <SectionTitle eyebrow="Безопасность" title="Доступ" />
            <div className="mt-4 space-y-2">
              <div className="flex items-start gap-3 rounded-xl border border-emerald-400/20 bg-emerald-500/[0.05] p-3.5">
                <ShieldCheck size={16} className="mt-0.5 shrink-0 text-emerald-300" />
                <div>
                  <p className="text-xs font-bold text-white">Аккаунт защищён</p>
                  <p className="mt-0.5 text-[11px] leading-relaxed text-mist-500">
                    Пароль хранится в зашифрованном виде. Никто, кроме вас, не видит личные данные.
                  </p>
                </div>
              </div>
              {user?.role === "parent" && (
                <Link to="/app/parent/help" className="flex items-center gap-3 rounded-xl border border-white/8 bg-white/[0.025] p-3.5 transition hover:border-iris-400/30">
                  <Sparkles size={16} className="text-iris-300" />
                  <div className="flex-1">
                    <p className="text-xs font-bold text-white">Родительская помощь</p>
                    <p className="text-[11px] text-mist-500">Удалённый экран и звуковой вызов</p>
                  </div>
                </Link>
              )}
            </div>
          </Card>

          <Card className="p-5">
            <Button variant="ghost" icon={LogOut} className="w-full" onClick={() => signOut()}>
              Выйти из аккаунта
            </Button>
            <p className="mt-3 text-center text-[10px] text-mist-600">
              {isStudent ? "Прогресс сохранится — можно вернуться в любой момент." : "Данные останутся в безопасности."}
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}
