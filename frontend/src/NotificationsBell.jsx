import React, { useCallback, useEffect, useRef, useState } from "react";
import { csrf, getJSON, postJSON } from "./api.js";

function Badge({ value }) {
  if (!value) return null;
  return <span className="react-bell__badge">{value > 99 ? "99+" : value}</span>;
}

function when(value) {
  if (!value) return "";
  const text = String(value).replace("T", " ");
  return text.slice(0, 16);
}

export default function NotificationsBell({ feedUrl }) {
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const box = useRef(null);

  const load = useCallback(async () => {
    try {
      const data = await getJSON(feedUrl + "?limit=8");
      setItems(data.items || []);
      setUnread(data.unread || 0);
    } catch (error) {
      /* уведомления не должны ломать страницу */
    }
  }, [feedUrl]);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 60000);
    return () => window.clearInterval(timer);
  }, [load]);

  useEffect(() => {
    function onDoc(event) {
      if (box.current && !box.current.contains(event.target)) setOpen(false);
    }
    function onKey(event) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, []);

  async function openItem(item) {
    if (!item.is_read) {
      try {
        const data = await postJSON("/notifications/feed/read", { id: item.id });
        setUnread(data.unread || 0);
        setItems((list) =>
          list.map((row) => (row.id === item.id ? { ...row, is_read: true } : row))
        );
      } catch (error) {
        /* переход всё равно полезнее ошибки */
      }
    }
    setOpen(false);
    window.location.href = item.link || "/notifications";
  }

  async function readAll() {
    setBusy(true);
    try {
      await postJSON("/notifications/feed/read-all", {});
      setUnread(0);
      setItems((list) => list.map((row) => ({ ...row, is_read: true })));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="react-bell" ref={box} data-csrf={csrf()}>
      <button
        type="button"
        className={"btn btn--ghost btn--small react-bell__btn" + (open ? " is-open" : "")}
        aria-label={"Уведомления" + (unread ? `, непрочитанных ${unread}` : "")}
        aria-expanded={open}
        onClick={() => {
          setOpen(!open);
          if (!open) load();
        }}
      >
        <span aria-hidden="true">🔔</span>
        <Badge value={unread} />
      </button>
      {open ? (
        <div className="react-bell__panel" role="dialog" aria-label="Уведомления">
          <div className="react-bell__head">
            <b>Уведомления</b>
            {unread ? (
              <button type="button" className="link-btn" disabled={busy} onClick={readAll}>
                Прочитать все
              </button>
            ) : null}
          </div>
          <div className="react-bell__list">
            {items.length === 0 ? (
              <p className="muted small" style={{ padding: "14px" }}>
                Пока пусто. Новые задания, сообщения и рекомендации появятся здесь.
              </p>
            ) : (
              items.map((item) => (
                <button
                  type="button"
                  key={item.id}
                  className={"react-bell__item" + (item.is_read ? "" : " is-new")}
                  onClick={() => openItem(item)}
                >
                  <span className="react-bell__icon" aria-hidden="true">
                    {item.icon}
                  </span>
                  <span className="react-bell__text">
                    <b>{item.title}</b>
                    <span>{item.body}</span>
                    <time>{when(item.created_at)}</time>
                  </span>
                </button>
              ))
            )}
          </div>
          <a className="react-bell__all" href="/notifications">
            Все уведомления →
          </a>
        </div>
      ) : null}
    </div>
  );
}
