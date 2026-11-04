import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  ClipboardList,
  Clock,
  Hash,
  RefreshCw,
  ScrollText,
  Search,
  ShieldCheck,
  User,
} from "lucide-react";
import {
  Avatar,
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  Select,
  Skeleton,
  StatCard,
} from "../../components/ui";
import { useApi } from "../../lib/hooks";
import { formatDateTime, relativeTime, text, todayLabel } from "../../lib/format";
import { SearchBox } from "./shared";

const LIMIT = 300;

const ACTION_LABEL = {
  create: "создание",
  update: "изменение",
  delete: "удаление",
  reset: "сброс",
  login: "вход",
  logout: "выход",
  ai_test: "проверка ИИ",
  gift: "подарок",
  cancel: "отмена",
  publish: "публикация",
  close: "закрытие",
};

const ENTITY_LABEL = {
  user: "пользователь",
  topic: "тема",
  city: "город",
  school: "школа",
  class: "класс",
  shop_item: "товар магазина",
  shop_event: "событие магазина",
  shop_gift: "подарок",
  ai: "ИИ",
  ai_settings: "настройки ИИ",
  youtube: "YouTube",
  assignment: "задание",
  book: "книга",
};

function actionTone(action) {
  if (action === "delete" || action === "cancel") return "rose";
  if (action === "create") return "green";
  if (action === "login" || action === "logout") return "cyan";
  if (action === "reset") return "gold";
  return "iris";
}

function actionLabel(action) {
  return ACTION_LABEL[action] || action;
}

function entityLabel(entity) {
  return ENTITY_LABEL[entity] || entity;
}

export function AdminAudit() {
  const { data, loading, error, refresh } = useApi(`/admin/audit?limit=${LIMIT}`);
  const [search, setSearch] = useState("");
  const [action, setAction] = useState("all");
  const [entity, setEntity] = useState("all");

  const entries = data?.entries || [];

  const actions = useMemo(() => {
    const counts = new Map();
    entries.forEach((entry) => {
      counts.set(entry.action, (counts.get(entry.action) || 0) + 1);
    });
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [entries]);

  const entities = useMemo(() => {
    const counts = new Map();
    entries.forEach((entry) => {
      if (!entry.entity) return;
      counts.set(entry.entity, (counts.get(entry.entity) || 0) + 1);
    });
    return Array.from(counts.entries()).sort((a, b) => b[1] - a[1]);
  }, [entries]);

  const people = useMemo(() => {
    const ids = new Set(entries.map((entry) => entry.user_id).filter(Boolean));
    return ids.size;
  }, [entries]);

  const todayCount = useMemo(() => {
    const today = new Date();
    return entries.filter((entry) => {
      if (!entry.created_at) return false;
      const date = new Date(String(entry.created_at).replace(" ", "T"));
      return (
        date.getFullYear() === today.getFullYear() &&
        date.getMonth() === today.getMonth() &&
        date.getDate() === today.getDate()
      );
    }).length;
  }, [entries]);

  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    return entries.filter((entry) => {
      if (action !== "all" && entry.action !== action) return false;
      if (entity !== "all" && entry.entity !== entity) return false;
      if (!query) return true;
      const haystack = [
        entry.action,
        entry.entity,
        entry.entity_id,
        text(entry.details),
        entry.login,
        entry.first_name,
        entry.last_name,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [entries, action, entity, search]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Журнал действий"
        subtitle={`${todayLabel()} · история изменений платформы: кто, что и когда сделал. Последние ${LIMIT} записей.`}
        actions={
          <>
            <Link to="/app/admin">
              <span className="btn btn-ghost">
                <ArrowRight size={16} className="rotate-180" /> Обзор
              </span>
            </Link>
            <Button icon={RefreshCw} loading={loading} onClick={refresh}>
              Обновить
            </Button>
          </>
        }
      />

      {error && <ErrorState error={error} onRetry={refresh} />}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={ScrollText} label="Записей" value={entries.length} hint={`лимит ${LIMIT}`} tone="iris" />
        <StatCard icon={Activity} label="Сегодня" value={todayCount} hint="действий за день" tone="green" />
        <StatCard icon={User} label="Авторов" value={people} hint="уникальных аккаунтов" tone="cyan" />
        <StatCard icon={Hash} label="Типов действий" value={actions.length} hint={`${entities.length} сущностей`} tone="gold" />
      </div>

      <Card className="space-y-3 p-4">
        <SearchBox value={search} onChange={setSearch} placeholder="Логин, имя, сущность, детали…" />
        <div className="grid gap-2 sm:grid-cols-2">
          <Select value={action} onChange={(event) => setAction(event.target.value)}>
            <option value="all">Все действия · {entries.length}</option>
            {actions.map(([key, count]) => (
              <option key={key} value={key}>
                {actionLabel(key)} · {count}
              </option>
            ))}
          </Select>
          <Select value={entity} onChange={(event) => setEntity(event.target.value)}>
            <option value="all">Все сущности</option>
            {entities.map(([key, count]) => (
              <option key={key} value={key}>
                {entityLabel(key)} · {count}
              </option>
            ))}
          </Select>
        </div>
      </Card>

      {loading && !data ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, index) => (
            <Skeleton key={index} className="h-20" />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <Card>
          <EmptyState
            icon={entries.length ? "🔍" : "📜"}
            title={entries.length ? "Ничего не нашлось" : "Журнал пуст"}
            text={
              entries.length
                ? "Измените запрос, действие или сущность."
                : "Записи появятся, когда администраторы и учителя начнут работать с платформой."
            }
          />
        </Card>
      ) : (
        <Card className="divide-y divide-white/6 p-2">
          {visible.map((entry) => (
            <div
              key={entry.id}
              className="flex flex-col gap-3 rounded-xl px-3 py-3 transition hover:bg-white/[0.025] sm:flex-row sm:items-start"
            >
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/8 bg-white/[0.03] text-[10px] font-bold uppercase text-iris-200">
                {(entry.action || "?").slice(0, 2)}
              </span>

              <div className="flex min-w-0 flex-1 items-start gap-3">
                {entry.login ? (
                  <Avatar
                    emoji={entry.avatar || "🦊"}
                    size={32}
                    seed={entry.login}
                    className="hidden sm:flex"
                  />
                ) : null}
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={actionTone(entry.action)}>{actionLabel(entry.action)}</Badge>
                    {entry.entity && (
                      <span className="text-[11px] font-semibold text-mist-300">
                        {entityLabel(entry.entity)}
                        {entry.entity_id ? ` · ${entry.entity_id}` : ""}
                      </span>
                    )}
                    {entry.login ? (
                      <span className="inline-flex items-center gap-1 text-[10px] text-mist-500">
                        <ShieldCheck size={11} /> @{entry.login}
                        {entry.first_name ? ` · ${entry.first_name} ${entry.last_name || ""}` : ""}
                      </span>
                    ) : (
                      <span className="text-[10px] text-mist-600">система</span>
                    )}
                  </div>
                  {entry.details && (
                    <p className="mt-1 line-clamp-2 break-words text-[11px] leading-relaxed text-mist-400">
                      {text(entry.details)}
                    </p>
                  )}
                  <p className="mt-1 flex items-center gap-1 text-[10px] text-mist-600">
                    <Clock size={10} />
                    {formatDateTime(entry.created_at)}
                    <span className="opacity-50">·</span>
                    {relativeTime(entry.created_at)}
                  </p>
                </div>
              </div>

              <span className="shrink-0 text-[10px] font-mono text-mist-600">#{entry.id}</span>
            </div>
          ))}
        </Card>
      )}

      <Card className="flex items-start gap-3 p-4">
        <ClipboardList size={16} className="mt-0.5 shrink-0 text-iris-300" />
        <p className="text-[11px] leading-relaxed text-mist-500">
          Журнал хранит только факты изменений: действие, сущность и краткие детали. Пароли и
          содержимое ответов сюда не попадают. Записи не удаляются — история помогает разобраться,
          кто и когда поменял настройки.
        </p>
      </Card>
    </div>
  );
}
