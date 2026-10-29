import React, { useEffect, useMemo, useState } from "react";
import { getJSON, postJSON } from "./api.js";

const FILTERS = [
  ["all", "Все"],
  ["unread", "Непрочитанные"],
  ["assignment", "Задания"],
  ["message", "Сообщения"],
  ["library", "Литература"],
];

function matches(item, filter) {
  if (filter === "all") return true;
  if (filter === "unread") return !item.is_read;
  if (filter === "assignment") return item.kind.startsWith("assignment");
  if (filter === "library") return item.kind.startsWith("library");
  return item.kind === filter;
}

export default function NotificationCenter() {
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    try {
      const data = await getJSON("/notifications/feed?limit=100");
      setItems(data.items || []);
      setUnread(data.unread || 0);
      setError("");
    } catch (err) {
      setError("Не удалось загрузить уведомления. Обновите страницу.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 90000);
    return () => window.clearInterval(timer);
  }, []);

  const visible = useMemo(
    () => items.filter((item) => matches(item, filter)),
    [items, filter]
  );

  async function markRead(item) {
    if (item.is_read) return;
    setItems((list) =>
      list.map((row) => (row.id === item.id ? { ...row, is_read: true } : row))
    );
    try {
      const data = await postJSON("/notifications/feed/read", { id: item.id });
      setUnread(data.unread || 0);
    } catch (err) {
      setItems((list) =>
        list.map((row) => (row.id === item.id ? { ...row, is_read: false } : row))
      );
    }
  }

  async function readAll() {
    try {
      await postJSON("/notifications/feed/read-all", {});
      setUnread(0);
      setItems((list) => list.map((row) => ({ ...row, is_read: true })));
    } catch (err) {
      setError("Не удалось отметить уведомления");
    }
  }

  return (
    <div className="react-notifications">
      <div className="react-notifications__bar">
        <div className="react-notifications__tabs" role="tablist">
          {FILTERS.map(([key, label]) => (
            <button
              type="button"
              role="tab"
              key={key}
              aria-selected={filter === key}
              className={"chip" + (filter === key ? " chip--blue" : "")}
              onClick={() => setFilter(key)}
            >
              {label}
              {key === "unread" && unread > 0 ? ` · ${unread}` : ""}
            </button>
          ))}
        </div>
        {unread ? (
          <button type="button" className="btn btn--small" onClick={readAll}>
            Прочитать все
          </button>
        ) : null}
      </div>

      {error ? <div className="flash flash--error">{error}</div> : null}

      {loading ? (
        <div className="card skeleton-card" aria-busy="true">
          <div className="skeleton skeleton--line" />
          <div className="skeleton skeleton--line short" />
        </div>
      ) : visible.length === 0 ? (
        <div className="card empty-state">
          <div className="empty-state__art" aria-hidden="true">📭</div>
          <p className="muted">
            {filter === "unread"
              ? "Непрочитанных уведомлений нет."
              : "Здесь появятся задания, сообщения и рекомендации литературы."}
          </p>
        </div>
      ) : (
        <div className="react-notifications__list">
          {visible.map((item) => (
            <article
              key={item.id}
              className={"notification-item" + (item.is_read ? "" : " is-new")}
            >
              <div className="notification-item__icon" aria-hidden="true">
                {item.icon}
              </div>
              <div className="notification-item__body">
                <div className="row row--between" style={{ gap: 8, alignItems: "baseline" }}>
                  <b>{item.title}</b>
                  <time className="muted small">{String(item.created_at).slice(0, 16)}</time>
                </div>
                <p className="notification-item__text">{item.body}</p>
                <div className="row small" style={{ gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  {kindChip(item.kind)}
                  {item.is_read && item.read_at ? (
                    <span className="muted">прочитано {String(item.read_at).slice(0, 16)}</span>
                  ) : null}
                  {item.link ? (
                    <a className="btn btn--ghost btn--small" href={item.link} onClick={() => markRead(item)}>
                      Открыть
                    </a>
                  ) : null}
                  {!item.is_read ? (
                    <button type="button" className="btn btn--ghost btn--small" onClick={() => markRead(item)}>
                      Прочитано
                    </button>
                  ) : null}
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function kindChip(kind) {
  const map = {
    reminder: ["chip--amber", "напоминание"],
    message: ["chip--blue", "сообщение"],
    assignment_deadline: ["chip--amber", "срок близко"],
    assignment_missed: ["chip--gray", "просрочено"],
    library_new: ["chip--purple", "литература"],
    library_unread: ["chip--purple", "напоминание"],
  };
  const entry = map[kind];
  if (!entry) return null;
  return <span className={"chip " + entry[0]}>{entry[1]}</span>;
}
