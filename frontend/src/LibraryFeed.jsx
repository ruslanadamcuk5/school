import React, { useEffect, useState } from "react";
import { getJSON, postJSON } from "./api.js";

function progress(items) {
  const done = items.filter((item) => item.done).length;
  return { done, total: items.length, percent: items.length ? Math.round((done / items.length) * 100) : 0 };
}

export default function LibraryFeed() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getJSON("/library/feed")
      .then((data) => setItems(data.items || []))
      .catch(() => setError("Не удалось загрузить рекомендации"))
      .finally(() => setLoading(false));
  }, []);

  async function markDone(item) {
    setItems((list) =>
      list.map((row) => (row.id === item.id ? { ...row, done: true } : row))
    );
    try {
      await postJSON(`/library/feed/${item.id}/done`, {});
    } catch (err) {
      setItems((list) =>
        list.map((row) => (row.id === item.id ? { ...row, done: false } : row))
      );
      setError("Не удалось сохранить отметку");
    }
  }

  if (loading) {
    return (
      <div className="card skeleton-card" aria-busy="true">
        <div className="skeleton skeleton--line" />
        <div className="skeleton skeleton--line short" />
      </div>
    );
  }
  if (error) return <div className="flash flash--error">{error}</div>;
  if (!items.length) return null;

  const stats = progress(items);
  return (
    <section className="library-feed">
      <div className="row row--between">
        <h2 className="section-title" style={{ margin: 0 }}>
          📖 Рекомендации учителя
        </h2>
        <div className="library-feed__progress" title="Прочитано рекомендаций">
          <span>
            {stats.done} / {stats.total}
          </span>
          <div className="library-feed__bar">
            <div style={{ width: stats.percent + "%" }} />
          </div>
        </div>
      </div>
      <div className="book-grid mt-2">
        {items.map((item, index) => (
          <article
            key={item.id}
            className={"recommend-card react-in" + (item.done ? " is-done" : "")}
            style={{ animationDelay: Math.min(index * 60, 360) + "ms" }}
          >
            <div className="recommend-card__cover" aria-hidden="true">
              {item.done ? "✅" : "📖"}
            </div>
            <div className="recommend-card__body">
              <div className="recommend-card__title">
                {item.topic_title || item.title}
              </div>
              <div className="recommend-card__meta">
                {item.title}
                {item.teacher ? ` · ${item.teacher}` : ""}
                {item.page
                  ? ` · стр. ${item.page}${item.page_end && item.page_end !== item.page ? "–" + item.page_end : ""}`
                  : ""}
              </div>
              {item.note ? <div className="recommend-card__note">{item.note}</div> : null}
              <div className="row mt-1" style={{ gap: 8, flexWrap: "wrap" }}>
                <a
                  className="btn btn--small btn--ghost"
                  target="_blank"
                  rel="noopener"
                  href={`/library/open/${item.book_id}` + (item.page ? `#page=${item.page}` : "")}
                >
                  Читать
                </a>
                {!item.done ? (
                  <button type="button" className="btn btn--small" onClick={() => markDone(item)}>
                    ✅ Прочитано
                  </button>
                ) : (
                  <span className="chip chip--gray">прочитано</span>
                )}
              </div>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
