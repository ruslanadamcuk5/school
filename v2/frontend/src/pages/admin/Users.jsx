import { useMemo, useState } from "react";
import {
  Check,
  KeyRound,
  Mail,
  Pencil,
  Plus,
  Power,
  Search,
  ShieldCheck,
  Trash2,
  UserPlus,
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
  IconButton,
  Input,
  Modal,
  PageHeader,
  Select,
  Skeleton,
  StatCard,
} from "../../components/ui";
import { useAction, useApi, toast } from "../../lib/hooks";
import { api, invalidate } from "../../lib/api";
import { ROLE_LABEL, formatDate, formatDateTime, plural, relativeTime } from "../../lib/format";
import { RoleBadge, SearchBox, Toolbar } from "./shared";

const EMPTY_CREATE = {
  login: "",
  password: "",
  role: "student",
  first_name: "",
  last_name: "",
  email: "",
  city_id: "",
  school_id: "",
  class_id: "",
};

function roleCounts(users) {
  return users.reduce((acc, user) => {
    acc[user.role] = (acc[user.role] || 0) + 1;
    return acc;
  }, {});
}

export function AdminUsers() {
  const { data, loading, error, refresh } = useApi("/admin/users");
  const { data: orgs } = useApi("/admin/orgs", { ttl: 120_000 });
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState(EMPTY_CREATE);
  const [editUser, setEditUser] = useState(null);
  const [editForm, setEditForm] = useState(null);
  const [pwdUser, setPwdUser] = useState(null);
  const [password, setPassword] = useState("");
  const { pending, run } = useAction();

  const users = data?.users || [];
  const counts = useMemo(() => roleCounts(users), [users]);
  const cities = orgs?.cities || [];
  const schools = orgs?.schools || [];
  const classes = orgs?.classes || [];

  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    return users.filter((user) => {
      if (role !== "all" && user.role !== role) return false;
      if (!query) return true;
      return `${user.login} ${user.first_name} ${user.last_name} ${user.email || ""} ${user.school_name || ""}`
        .toLowerCase()
        .includes(query);
    });
  }, [users, role, search]);

  const afterChange = async (message) => {
    invalidate("/admin");
    await refresh();
    toast(message, "success");
  };

  const submitCreate = async () => {
    if (!createForm.login.trim() || createForm.login.trim().length < 3) {
      toast("Логин — не короче 3 символов", "info");
      return;
    }
    if (createForm.password.length < 6) {
      toast("Пароль — не короче 6 символов", "info");
      return;
    }
    try {
      await run(() => api.post("/admin/users", {
        ...createForm,
        login: createForm.login.trim().toLowerCase(),
        city_id: createForm.city_id || null,
        school_id: createForm.school_id || null,
        class_id: createForm.class_id || null,
      }));
      setCreateOpen(false);
      setCreateForm(EMPTY_CREATE);
      await afterChange("Пользователь создан");
    } catch (err) {
      toast(err.message || "Не удалось создать пользователя", "error");
    }
  };

  const openEdit = (user) => {
    setEditUser(user);
    setEditForm({
      login: user.login || "",
      first_name: user.first_name || "",
      last_name: user.last_name || "",
      email: user.email || "",
      phone: user.phone || "",
      role: user.role || "student",
      is_active: Boolean(user.is_active),
      city_id: user.city_id ? String(user.city_id) : "",
      school_id: user.school_id ? String(user.school_id) : "",
    });
  };

  const submitEdit = async () => {
    if (!editUser || !editForm) return;
    try {
      await run(() => api.patch(`/admin/users/${editUser.id}`, {
        ...editForm,
        city_id: editForm.city_id || null,
        school_id: editForm.school_id || null,
      }));
      setEditUser(null);
      setEditForm(null);
      await afterChange("Данные обновлены");
    } catch (err) {
      toast(err.message || "Не удалось сохранить", "error");
    }
  };

  const toggleActive = async (user) => {
    try {
      await run(() => api.patch(`/admin/users/${user.id}`, { is_active: !user.is_active }));
      await afterChange(user.is_active ? "Доступ закрыт" : "Доступ открыт");
    } catch (err) {
      toast(err.message || "Не удалось изменить доступ", "error");
    }
  };

  const submitPassword = async () => {
    if (!pwdUser) return;
    if (password.length < 6) {
      toast("Пароль — не короче 6 символов", "info");
      return;
    }
    try {
      await run(() => api.post(`/admin/users/${pwdUser.id}/password`, { password }));
      setPwdUser(null);
      setPassword("");
      toast("Пароль изменён", "success");
    } catch (err) {
      toast(err.message || "Не удалось изменить пароль", "error");
    }
  };

  const remove = async (user) => {
    if (!window.confirm(`Удалить аккаунт @${user.login}? Это действие нельзя отменить.`)) return;
    try {
      await run(() => api.del(`/admin/users/${user.id}`));
      await afterChange("Пользователь удалён");
    } catch (err) {
      toast(err.message || "Не удалось удалить пользователя", "error");
    }
  };

  const tabs = [
    { key: "all", label: "Все", count: users.length },
    ...["student", "parent", "teacher", "admin"].map((key) => ({
      key,
      label: ROLE_LABEL[key],
      count: counts[key] || 0,
    })),
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Пользователи"
        subtitle="Аккаунты учеников, родителей, учителей и администраторов. Пароли и доступы — здесь."
        actions={<Button icon={UserPlus} onClick={() => setCreateOpen(true)}>Новый пользователь</Button>}
      />

      {error && <ErrorState error={error} onRetry={refresh} />}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Users} label="Всего аккаунтов" value={users.length} tone="iris" />
        <StatCard icon={ShieldCheck} label="Учителя" value={counts.teacher || 0} tone="cyan" />
        <StatCard icon={Users} label="Ученики" value={counts.student || 0} tone="green" />
        <StatCard icon={Power} label="Активны" value={users.filter((user) => user.is_active).length} tone="gold" />
      </div>

      <Card className="space-y-3 p-4">
        <SearchBox value={search} onChange={setSearch} placeholder="Имя, логин, email или школа…" />
        <div className="no-scrollbar flex gap-1 overflow-x-auto rounded-2xl border border-white/8 bg-white/[0.025] p-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setRole(tab.key)}
              className={`flex shrink-0 items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold transition ${
                role === tab.key ? "bg-white/10 text-white" : "text-mist-500 hover:text-white"
              }`}
            >
              {tab.label}
              <span className="text-[10px] opacity-60">{tab.count}</span>
            </button>
          ))}
        </div>
      </Card>

      {loading && !data ? (
        <div className="space-y-2">{Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-20" />)}</div>
      ) : visible.length === 0 ? (
        <Card>
          <EmptyState
            icon="🔍"
            title={users.length ? "Ничего не нашлось" : "Аккаунтов пока нет"}
            text={users.length ? "Измените запрос или фильтр роли." : "Создайте первого пользователя."}
            action={<Button icon={Plus} onClick={() => setCreateOpen(true)}>Создать</Button>}
          />
        </Card>
      ) : (
        <Card className="divide-y divide-white/6 p-2">
          {visible.map((user) => (
            <div key={user.id} className="flex flex-col gap-3 rounded-xl px-3 py-3 transition hover:bg-white/[0.025] sm:flex-row sm:items-center">
              <div className="flex min-w-0 flex-1 items-center gap-3">
                <Avatar emoji={user.avatar || "🦊"} size={44} seed={user.login} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate text-sm font-bold text-white">{user.first_name} {user.last_name}</p>
                    <RoleBadge role={user.role} />
                    {!user.is_active && <Badge tone="rose">заблокирован</Badge>}
                  </div>
                  <p className="mt-0.5 truncate text-[11px] text-mist-500">
                    @{user.login}
                    {user.email ? ` · ${user.email}` : ""}
                    {user.school_name ? ` · ${user.school_name}` : ""}
                  </p>
                  <p className="mt-0.5 text-[10px] text-mist-600">
                    {user.last_login ? `Вход: ${relativeTime(user.last_login)}` : `Создан: ${formatDate(user.created_at, { year: true })}`}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-1.5 sm:justify-end">
                <Button size="sm" variant="ghost" icon={Pencil} onClick={() => openEdit(user)}>Изменить</Button>
                <IconButton icon={KeyRound} label="Сменить пароль" onClick={() => { setPwdUser(user); setPassword(""); }} />
                <IconButton
                  icon={Power}
                  label={user.is_active ? "Закрыть доступ" : "Открыть доступ"}
                  className={user.is_active ? "text-emerald-300" : "text-rose-300"}
                  onClick={() => toggleActive(user)}
                />
                <IconButton icon={Trash2} label="Удалить" className="text-rose-300" onClick={() => remove(user)} />
              </div>
            </div>
          ))}
        </Card>
      )}

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Новый пользователь"
        description="Аккаунт сразу сможет войти в приложение и на сайт."
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>Отмена</Button>
            <Button icon={Check} loading={pending} onClick={submitCreate}>Создать</Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Логин" hint="Латиница, от 3 символов.">
            <Input value={createForm.login} onChange={(event) => setCreateForm((current) => ({ ...current, login: event.target.value }))} placeholder="ivanov" />
          </Field>
          <Field label="Пароль" hint="Не короче 6 символов.">
            <Input value={createForm.password} onChange={(event) => setCreateForm((current) => ({ ...current, password: event.target.value }))} placeholder="••••••" />
          </Field>
          <Field label="Роль">
            <Select value={createForm.role} onChange={(event) => setCreateForm((current) => ({ ...current, role: event.target.value }))}>
              {["student", "parent", "teacher", "admin"].map((key) => (
                <option key={key} value={key}>{ROLE_LABEL[key]}</option>
              ))}
            </Select>
          </Field>
          <Field label="Email" hint="Необязательно.">
            <Input type="email" value={createForm.email} onChange={(event) => setCreateForm((current) => ({ ...current, email: event.target.value }))} placeholder="mail@school.by" />
          </Field>
          <Field label="Имя">
            <Input value={createForm.first_name} onChange={(event) => setCreateForm((current) => ({ ...current, first_name: event.target.value }))} />
          </Field>
          <Field label="Фамилия">
            <Input value={createForm.last_name} onChange={(event) => setCreateForm((current) => ({ ...current, last_name: event.target.value }))} />
          </Field>
          <Field label="Город">
            <Select value={createForm.city_id} onChange={(event) => setCreateForm((current) => ({ ...current, city_id: event.target.value }))}>
              <option value="">Не выбран</option>
              {cities.map((city) => <option key={city.id} value={city.id}>{city.name}</option>)}
            </Select>
          </Field>
          <Field label="Школа">
            <Select value={createForm.school_id} onChange={(event) => setCreateForm((current) => ({ ...current, school_id: event.target.value }))}>
              <option value="">Не выбрана</option>
              {schools.map((school) => <option key={school.id} value={school.id}>{school.name}</option>)}
            </Select>
          </Field>
          {createForm.role === "student" && (
            <Field label="Класс" hint="Можно назначить сразу или позже." className="sm:col-span-2">
              <Select value={createForm.class_id} onChange={(event) => setCreateForm((current) => ({ ...current, class_id: event.target.value }))}>
                <option value="">Без класса</option>
                {classes.map((klass) => (
                  <option key={klass.id} value={klass.id}>{klass.school_name} · {klass.title}</option>
                ))}
              </Select>
            </Field>
          )}
        </div>
      </Modal>

      <Modal
        open={Boolean(editUser && editForm)}
        onClose={() => { setEditUser(null); setEditForm(null); }}
        title={editUser ? `@${editUser.login}` : "Пользователь"}
        description="Личные данные, роль и доступ."
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => { setEditUser(null); setEditForm(null); }}>Отмена</Button>
            <Button icon={Check} loading={pending} onClick={submitEdit}>Сохранить</Button>
          </>
        }
      >
        {editForm && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Логин">
              <Input value={editForm.login} onChange={(event) => setEditForm((current) => ({ ...current, login: event.target.value }))} />
            </Field>
            <Field label="Роль">
              <Select value={editForm.role} onChange={(event) => setEditForm((current) => ({ ...current, role: event.target.value }))}>
                {["student", "parent", "teacher", "admin"].map((key) => (
                  <option key={key} value={key}>{ROLE_LABEL[key]}</option>
                ))}
              </Select>
            </Field>
            <Field label="Имя">
              <Input value={editForm.first_name} onChange={(event) => setEditForm((current) => ({ ...current, first_name: event.target.value }))} />
            </Field>
            <Field label="Фамилия">
              <Input value={editForm.last_name} onChange={(event) => setEditForm((current) => ({ ...current, last_name: event.target.value }))} />
            </Field>
            <Field label="Email">
              <Input value={editForm.email} onChange={(event) => setEditForm((current) => ({ ...current, email: event.target.value }))} />
            </Field>
            <Field label="Телефон">
              <Input value={editForm.phone} onChange={(event) => setEditForm((current) => ({ ...current, phone: event.target.value }))} />
            </Field>
            <Field label="Город">
              <Select value={editForm.city_id} onChange={(event) => setEditForm((current) => ({ ...current, city_id: event.target.value }))}>
                <option value="">Не выбран</option>
                {cities.map((city) => <option key={city.id} value={city.id}>{city.name}</option>)}
              </Select>
            </Field>
            <Field label="Школа">
              <Select value={editForm.school_id} onChange={(event) => setEditForm((current) => ({ ...current, school_id: event.target.value }))}>
                <option value="">Не выбрана</option>
                {schools.map((school) => <option key={school.id} value={school.id}>{school.name}</option>)}
              </Select>
            </Field>
            <div className="sm:col-span-2">
              <button
                type="button"
                onClick={() => setEditForm((current) => ({ ...current, is_active: !current.is_active }))}
                className={`flex w-full items-center gap-3 rounded-xl border px-3.5 py-3 text-left transition ${
                  editForm.is_active ? "border-emerald-400/25 bg-emerald-500/[0.06]" : "border-rose-400/25 bg-rose-500/[0.06]"
                }`}
              >
                <Power size={16} className={editForm.is_active ? "text-emerald-300" : "text-rose-300"} />
                <div className="flex-1">
                  <p className="text-xs font-bold text-white">{editForm.is_active ? "Доступ открыт" : "Доступ закрыт"}</p>
                  <p className="text-[11px] text-mist-500">Нажмите, чтобы {editForm.is_active ? "заблокировать" : "разблокировать"} вход.</p>
                </div>
              </button>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        open={Boolean(pwdUser)}
        onClose={() => setPwdUser(null)}
        title="Новый пароль"
        description={pwdUser ? `@${pwdUser.login}` : ""}
        footer={
          <>
            <Button variant="ghost" onClick={() => setPwdUser(null)}>Отмена</Button>
            <Button icon={KeyRound} loading={pending} onClick={submitPassword}>Сменить</Button>
          </>
        }
      >
        <Field label="Пароль" hint="Не короче 6 символов. Сообщите его пользователю лично.">
          <Input value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••" autoFocus />
        </Field>
      </Modal>
    </div>
  );
}
