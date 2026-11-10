import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bell,
  BookOpen,
  CheckCheck,
  ClipboardList,
  Compass,
  Gift,
  Info,
  Sparkles,
  Trophy,
} from "lucide-react";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, Skeleton, Tabs } from "../components/ui";
import { useAction, useApi, toast } from "../lib/hooks";
import { api, invalidate } from "../lib/api";
import { formatDateTime, relativeTime } from "../lib/format";

const KIND = {
  assignment_new: { icon: ClipboardList, tone: "iris", label: "Задание" },
  assignment_due: { icon: Bell, tone: "gold", label: "Срок" },
  assignment_result: { icon: Trophy, tone: "green", label: "Результат" },
  library_recommendation: { icon: BookOpen, tone: "cyan", label: "Книга" },
  gift: { icon: Gift, tone: "gold", label: "Подарок" },
  badge: { icon: Trophy, tone: "gold", label: "Награда" },
  message: { icon: Info, tone: "iris", label: "Сообщение" },
  psych_result: { icon: Sparkles, tone: "iris", label: "Психология" },
  psych_recommendation: { icon: Compass, tone: "gold", label: "Рекомендации" },
};

function targetLink(item) {
  if (item.kind === "psych_result" || item.kind === "psych_recommendation") {
    return item.link && String(item.link).startsWith("/app/") ? item.link : null;
  }
  if (item.assignment_id) return `/app/assignments/${item.assignment_id}`;
  if (item.kind === "library_recommendation") return "/app/library";
  if (item.kind === "gift") return "/app/shop";
  if (item.kind === "badge") return "/app/profile";
  if (item.link && String(item.link).includes("/works/")) {
    const id = String(item.link).split("/").pop();
    return `/app/assignments/${id}`;
  }
  return null;
}

export default function NotificationsPage() {
  const { data, loading, error, refresh } = useApi("/notifications", { ttl: 10_000 });
  const [tab, setTab] = useState("unread");
  const { pending, run } = useAction();

  const all = data?.notifications || [];
  const unread = data?.unread || 0;
  const shown = useMemo(() => (tab === "unread" ? all.filter((item) => !item.is_read) : all), [all, tab]);

  const markRead = async (item) => {
    if (item.is_read) return;
    try {
      await run(() => api.post(`/notifications/${item.id}/read`, {}));
      invalidate("/notifications");
      await refresh();
    } catch (err) {
      toast(err.message || "Не удалось отметить", "error");
    }
  };

  const markAll = async () => {
    try {
      await run(() => api.post("/notifications/read-all", {}));
      invalidate("/notifications");
      await refresh();
      toast("Все уведомления прочитаны", "success");
    } catch (err) {
      toast(err.message || "Не удалось обновить", "error");
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Уведомления"
        subtitle="Новые задания, сроки, результаты и подарки — в одном потоке."
        actions={
          <>
            {unread > 0 && <Badge tone="rose">{unread} новых</Badge>}
            <Button variant="ghost" icon={CheckCheck} loading={pending} disabled={unread === 0} onClick={markAll}>
              Прочитать все
            </Button>
          </>
        }
      />

      <Tabs
        tabs={[
          { key: "unread", label: "Непрочитанные", count: unread },
          { key: "all", label: "Все", count: all.length },
        ]}
        value={tab}
        onChange={setTab}
      />

      {error && <ErrorState error={error} onRetry={refresh} />}

      {loading && !data && (
        <div className="space-y-2.5">
          {Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-20" />)}
        </div>
      )}

      {!loading && shown.length === 0 && (
        <Card>
          <EmptyState
            icon={tab === "unread" ? "🎉" : "🔔"}
            title={tab === "unread" ? "Всё прочитано" : "Уведомлений пока нет"}
            text={tab === "unread" ? "Новые события появятся здесь и в колокольчике сверху." : "Когда появятся задания или подарки, вы узнаете первыми."}
          />
        </Card>
      )}

      <div className="space-y-2.5">
        {shown.map((item) => {
          const meta = KIND[item.kind] || { icon: Bell, tone: "iris", label: "Событие" };
          const Icon = meta.icon;
          const to = targetLink(item);
          return (
            <div
              key={item.id}
              className={`relative flex items-start gap-3.5 rounded-2xl border px-4 py-3.5 transition ${
                item.is_read ? "border-white/7 bg-white/[0.02]" : "border-iris-400/20 bg-iris-500/[0.055]"
              } ${to ? "hover:border-iris-400/35" : ""}`}
            >
              <span className={`mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/5 ${
                meta.tone === "gold" ? "text-amber-300" : meta.tone === "green" ? "text-emerald-300" : meta.tone === "cyan" ? "text-cyan-300" : "text-iris-300"
              }`}>
                <Icon size={18} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  {to ? (
                    <Link
                      to={to}
                      onClick={() => markRead(item)}
                      className={`text-sm font-bold after:absolute after:inset-0 after:rounded-2xl ${
                        item.is_read ? "text-mist-300" : "text-white"
                      }`}
                    >
                      {item.title}
                    </Link>
                  ) : (
                    <button
                      type="button"
                      onClick={() => markRead(item)}
                      className={`text-left text-sm font-bold ${item.is_read ? "text-mist-300" : "text-white"}`}
                    >
                      {item.title}
                    </button>
                  )}
                  <Badge tone={meta.tone}>{meta.label}</Badge>
                  {!item.is_read && <span className="h-1.5 w-1.5 rounded-full bg-iris-400" />}
                </div>
                <p className="mt-1 text-xs leading-relaxed text-mist-500">{item.body}</p>
                <p className="mt-1.5 text-[10px] font-semibold text-mist-600" title={formatDateTime(item.created_at)}>
                  {relativeTime(item.created_at) || formatDateTime(item.created_at)}
                </p>
              </div>
              {!item.is_read && (
                <button
                  type="button"
                  onClick={(event) => { event.preventDefault(); event.stopPropagation(); markRead(item); }}
                  className="icon-btn relative z-10 h-8 w-8 shrink-0"
                  title="Отметить прочитанным"
                >
                  <CheckCheck size={14} />
                </button>
              )}
            </div>
          );
        })}
      </div>

      {all.length > 0 && (
        <Card className="p-5">
          <div className="flex items-start gap-2.5 text-[11px] leading-relaxed text-mist-500">
            <Sparkles size={15} className="mt-0.5 shrink-0 text-iris-300" />
            Уведомления приходят и на телефон, если приложение установлено. Здесь — та же лента, без потерь.
          </div>
        </Card>
      )}
    </div>
  );
}
