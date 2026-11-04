import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  BookOpen,
  Check,
  Copy,
  KeyRound,
  Mail,
  Power,
  ShieldCheck,
  Trash2,
  UserRound,
  Users,
} from "lucide-react";
import {
  Avatar,
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  Field,
  Input,
  Modal,
  PageHeader,
  Progress,
  Select,
  Skeleton,
  StatCard,
} from "../../components/ui";
import { useAction, useApi, toast } from "../../lib/hooks";
import { api, invalidate } from "../../lib/api";
import { ROLE_LABEL, formatDateTime, relativeTime } from "../../lib/format";
import { RoleBadge } from "./shared";

export function AdminUserDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, loading, error, refresh } = useApi(`/admin/users/${id}`);
  const [form, setForm] = useState(null);
  const [pwdOpen, setPwdOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [classId, setClassId] = useState("");
  const [busy, setBusy] = useState("");
  const { pending, run } = useAction();

  const user = data?.user;
  const orgs = data?.orgs || {};
  const attempts = data?.attempts || [];
  const classes = data?.classes || [];
  const learners = data?.learners || [];

  const correct = attempts.filter((item) => item.correct).length;
  const percent = attempts.length ? Math.round((correct / attempts.length) * 100) : 0;

  useEffect(() => {
    if (!user) return;
    setForm({
      login: user.login || "",
      first_name: user.first_name || "",
      last_name: user.last_name || "",
      email: user.email || "",
      phone: user.phone || "",
      avatar: user.avatar || "🦊",
      role: user.role || "student",
      city_id: user.city_id ? String(user.city_id) : "",
      school_id: user.school_id ? String(user.school_id) : "",
      is_active: Boolean(user.is_active),
    });
  }, [user]);

  const availableClasses = useMemo(() => {
    const linked = new Set(classes.map((klass) => klass.id));
    return (orgs.classes || []).filter((klass) => !linked.has(klass.id));
  }, [orgs.classes, classes]);

  const save = async () => {
    setBusy("save");
    try {
      await run(() => api.patch(`/admin/users/${id}`, {
        ...form,
        city_id: form.city_id || null,
        school_id: form.school_id || null,
      }));
      invalidate("/admin");
      await refresh();
      toast("Пользователь обновлён", "success");
    } catch (err) {
      toast(err.message || "Не удалось сохранить", "error");
    } finally {
      setBusy("");
    }
  };

  const toggle = async () => {
    setBusy("toggle");
    try {
      await run(() => api.patch(`/admin/users/${id}`, { is_active: !user.is_active }));
      await refresh();
      toast(user.is_active ? "Доступ закрыт" : "Доступ открыт", "success");
    } catch (err) {
      toast(err.message || "Не удалось изменить доступ", "error");
    } finally {
      setBusy("");
    }
  };

  const resetPassword = async () => {
    if (password.length < 6) {
      toast("Пароль — не короче 6 символов", "info");
      return;
    }
    try {
      await run(() => api.post(`/admin/users/${id}/password`, { password }));
      setPwdOpen(false);
      setPassword("");
      toast("Пароль изменён", "success");
    } catch (err) {
      toast(err.message || "Не удалось изменить пароль", "error");
    }
  };

  const addClass = async () => {
    if (!classId) return;
    setBusy("class");
    try {
      await run(() => api.post(`/admin/classes/${classId}/students`, { student_id: Number(id) }));
      setClassId("");
      await refresh();
      toast("Ученик добавлен в класс", "success");
    } catch (err) {
      toast(err.message || "Не удалось добавить в класс", "error");
    } finally {
      setBusy("");
    }
  };

  const removeClass = async (klass) => {
    setBusy(`class-${klass.id}`);
    try {
      await run(() => api.post(`/admin/classes/${klass.id}/students`, { student_id: Number(id), remove: true }));
      await refresh();
      toast("Ученик убран из класса", "success");
    } catch (err) {
      toast(err.message || "Не удалось убрать из класса", "error");
    } finally {
      setBusy("");
    }
  };

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(user.child_code || "");
      toast("Код скопирован", "success");
    } catch {
      toast(`Код ребёнка: ${user.child_code}`, "info");
    }
  };

  const removeUser = async () => {
    if (!window.confirm(`Удалить пользователя @${user.login}?`)) return;
    try {
      await run(() => api.del(`/admin/users/${id}`));
      invalidate("/admin");
      toast("Пользователь удалён", "success");
      navigate("/app/admin/users");
    } catch (err) {
      toast(err.message || "Не удалось удалить пользователя", "error");
    }
  };

  if (loading && !data) {
    return <div className="space-y-4"><Skeleton className="h-16 w-full" /><Skeleton className="h-96 w-full" /></div>;
  }

  if (error && !data) return <ErrorState error={error} onRetry={refresh} />;
  if (!user) return null;

  return (
    <div className="space-y-6">
      <button onClick={() => navigate("/app/admin/users")} className="inline-flex items-center gap-1.5 text-xs font-semibold text-mist-400 hover:text-white">
        <ArrowLeft size={15} /> Все пользователи
      </button>

      <PageHeader
        title={`${user.first_name || ""} ${user.last_name || ""}`.trim() || `@${user.login}`}
        subtitle={`@${user.login} · ${ROLE_LABEL[user.role] || user.role}${user.school_name ? ` · ${user.school_name}` : ""}`}
        actions={
          <>
            <Button variant="ghost" icon={KeyRound} onClick={() => { setPassword(""); setPwdOpen(true); }}>Сменить пароль</Button>
            <Button variant="ghost" icon={Power} className={user.is_active ? "text-emerald-300" : "text-rose-300"} loading={busy === "toggle"} onClick={toggle}>
              {user.is_active ? "Закрыть доступ" : "Открыть доступ"}
            </Button>
            <Button variant="ghost" icon={Trash2} className="text-rose-300" onClick={removeUser}>Удалить</Button>
          </>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={UserRound} label="Роль" value={ROLE_LABEL[user.role] || user.role} tone="iris" />
        <StatCard icon={BookOpen} label="Попыток" value={attempts.length} hint={`${percent}% верных`} tone="cyan" />
        <StatCard icon={Users} label="Профилей детей" value={learners.length} tone="green" />
        <StatCard icon={ShieldCheck} label="Статус" value={user.is_active ? "активен" : "закрыт"} tone={user.is_active ? "green" : "rose"} />
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_1fr]">
        <Card className="space-y-4 p-5 sm:p-6">
          <div className="flex items-center gap-3">
            <Avatar emoji={user.avatar || "🦊"} size={52} seed={user.login} ring />
            <div className="min-w-0">
              <p className="truncate text-sm font-bold text-white">{user.first_name} {user.last_name}</p>
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                <RoleBadge role={user.role} />
                {!user.is_active && <Badge tone="rose">заблокирован</Badge>}
                {user.last_login && <span className="text-[10px] text-mist-600">вход {relativeTime(user.last_login)}</span>}
              </div>
            </div>
          </div>

          {form && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Логин">
                <Input value={form.login} onChange={(event) => setForm((current) => ({ ...current, login: event.target.value }))} />
              </Field>
              <Field label="Роль">
                <Select value={form.role} onChange={(event) => setForm((current) => ({ ...current, role: event.target.value }))}>
                  {(data?.roles || ["student", "parent", "teacher", "admin"]).map((role) => (
                    <option key={role} value={role}>{ROLE_LABEL[role] || role}</option>
                  ))}
                </Select>
              </Field>
              <Field label="Имя">
                <Input value={form.first_name} onChange={(event) => setForm((current) => ({ ...current, first_name: event.target.value }))} />
              </Field>
              <Field label="Фамилия">
                <Input value={form.last_name} onChange={(event) => setForm((current) => ({ ...current, last_name: event.target.value }))} />
              </Field>
              <Field label="Аватар" hint="Один эмодзи">
                <Input value={form.avatar} maxLength={8} onChange={(event) => setForm((current) => ({ ...current, avatar: event.target.value }))} placeholder="🦊" />
              </Field>
              <Field label="Email">
                <Input type="email" value={form.email} onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))} />
              </Field>
              <Field label="Телефон">
                <Input value={form.phone} onChange={(event) => setForm((current) => ({ ...current, phone: event.target.value }))} />
              </Field>
              {user.role === "student" && user.child_code && (
                <Field label="Код ребёнка" hint="Родитель вводит его, чтобы привязать ребёнка." className="sm:col-span-2">
                  <div className="flex items-center gap-2">
                    <Input value={user.child_code} readOnly className="font-mono tracking-[0.2em] !text-iris-200" />
                    <Button size="sm" variant="ghost" icon={Copy} onClick={copyCode}>Копировать</Button>
                  </div>
                </Field>
              )}
              <Field label="Город">
                <Select value={form.city_id} onChange={(event) => setForm((current) => ({ ...current, city_id: event.target.value }))}>
                  <option value="">Не выбран</option>
                  {(orgs.cities || []).map((city) => <option key={city.id} value={city.id}>{city.name}</option>)}
                </Select>
              </Field>
              <Field label="Школа">
                <Select value={form.school_id} onChange={(event) => setForm((current) => ({ ...current, school_id: event.target.value }))}>
                  <option value="">Не выбрана</option>
                  {(orgs.schools || []).map((school) => <option key={school.id} value={school.id}>{school.name}</option>)}
                </Select>
              </Field>
              <div className="sm:col-span-2">
                <Button icon={Check} loading={pending && busy === "save"} onClick={save}>Сохранить профиль</Button>
              </div>
            </div>
          )}
        </Card>

        <div className="space-y-5">
          {user.role === "student" && (
            <Card className="space-y-3 p-5 sm:p-6">
              <h2 className="font-display text-lg font-semibold text-white">Классы</h2>
              {classes.length === 0 && <p className="text-xs text-mist-500">Ученик пока не добавлен ни в один класс.</p>}
              {classes.map((klass) => (
                <div key={klass.id} className="flex items-center gap-2 rounded-xl border border-white/7 bg-white/[0.02] px-3 py-2">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-bold text-white">{klass.school_name} · {klass.title}</p>
                    <p className="text-[10px] text-mist-600">{klass.city_name} · {klass.students_count || 0} учеников</p>
                  </div>
                  <Button size="sm" variant="ghost" loading={busy === `class-${klass.id}`} onClick={() => removeClass(klass)}>Убрать</Button>
                </div>
              ))}
              <div className="flex gap-2">
                <Select value={classId} onChange={(event) => setClassId(event.target.value)}>
                  <option value="">Добавить в класс…</option>
                  {availableClasses.map((klass) => (
                    <option key={klass.id} value={klass.id}>{klass.school_name} · {klass.title}</option>
                  ))}
                </Select>
                <Button size="sm" variant="ghost" icon={Check} loading={busy === "class"} onClick={addClass}>ОК</Button>
              </div>
            </Card>
          )}

          {user.role === "parent" && (
            <Card className="space-y-3 p-5 sm:p-6">
              <h2 className="font-display text-lg font-semibold text-white">Дети</h2>
              {(data.children || []).length === 0 && <p className="text-xs text-mist-500">Дети не привязаны.</p>}
              {(data.children || []).map((child) => (
                <Link key={child.id} to={`/app/admin/users/${child.id}`} className="flex items-center gap-2 rounded-xl border border-white/7 bg-white/[0.02] px-3 py-2 hover:border-white/15">
                  <Avatar emoji={child.avatar || "🦊"} size={32} seed={child.login} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-bold text-white">{child.first_name} {child.last_name}</p>
                    <p className="text-[10px] text-mist-600">@{child.login} · {child.relation || "ребёнок"}</p>
                  </div>
                </Link>
              ))}
            </Card>
          )}

          {user.role === "student" && (
            <Card className="space-y-3 p-5 sm:p-6">
              <h2 className="font-display text-lg font-semibold text-white">Родители</h2>
              {(data.parents || []).length === 0 && <p className="text-xs text-mist-500">Родители не привязаны.</p>}
              {(data.parents || []).map((parent) => (
                <Link key={parent.id} to={`/app/admin/users/${parent.id}`} className="flex items-center gap-2 rounded-xl border border-white/7 bg-white/[0.02] px-3 py-2 hover:border-white/15">
                  <Avatar emoji={parent.avatar || "👤"} size={32} seed={parent.login} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-bold text-white">{parent.first_name} {parent.last_name}</p>
                    <p className="text-[10px] text-mist-600">@{parent.login} · {parent.relation || "родитель"}</p>
                  </div>
                </Link>
              ))}
            </Card>
          )}

          {learners.length > 0 && (
            <Card className="space-y-3 p-5 sm:p-6">
              <h2 className="font-display text-lg font-semibold text-white">Профили обучения</h2>
              {learners.map((learner) => (
                <div key={learner.id} className="flex items-center gap-2 rounded-xl border border-white/7 bg-white/[0.02] px-3 py-2">
                  <span className="text-lg">{learner.avatar || "🦊"}</span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-bold text-white">{learner.name}</p>
                    <p className="text-[10px] text-mist-600">{learner.grade} класс · {learner.xp || 0} XP · {learner.coins || 0} монет</p>
                  </div>
                  <Badge tone="gold">🔥 {learner.streak_days || 0}</Badge>
                </div>
              ))}
            </Card>
          )}
        </div>
      </div>

      <Card className="p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-lg font-semibold text-white">Последние ответы</h2>
          <div className="flex items-center gap-3">
            <span className="text-[11px] text-mist-500">{correct} из {attempts.length} верно</span>
            <div className="w-32"><Progress value={percent} /></div>
          </div>
        </div>
        {attempts.length === 0 ? (
          <EmptyState icon="📝" title="Ответов пока нет" text="Здесь появятся последние попытки ученика." />
        ) : (
          <div className="mt-4 divide-y divide-white/6">
            {attempts.map((attempt) => (
              <div key={attempt.id} className="flex items-center gap-3 py-2">
                <span className={`h-2 w-2 shrink-0 rounded-full ${attempt.correct ? "bg-emerald-400" : "bg-rose-400"}`} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-semibold text-white">{attempt.topic_title || attempt.topic_slug || attempt.mode || "Задание"}</p>
                  <p className="truncate text-[10px] text-mist-600">
                    Ответ: {attempt.given_answer || "—"} · ожидалось: {attempt.expected || "—"}
                  </p>
                </div>
                <span className="shrink-0 text-[10px] text-mist-600">{formatDateTime(attempt.created_at)}</span>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Modal
        open={pwdOpen}
        onClose={() => setPwdOpen(false)}
        title="Новый пароль"
        description={`Пароль для @${user.login}. Не короче 6 символов.`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setPwdOpen(false)}>Отмена</Button>
            <Button icon={KeyRound} loading={pending} onClick={resetPassword}>Сохранить</Button>
          </>
        }
      >
        <Field label="Пароль">
          <Input value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••" />
        </Field>
      </Modal>
    </div>
  );
}
