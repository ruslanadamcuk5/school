import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, CalendarDays, Clock, MapPin, Sparkles } from "lucide-react";
import { Badge, Card, EmptyState, ErrorState, PageHeader, SectionTitle, Skeleton } from "../components/ui";
import { useApi, useSession } from "../lib/hooks";

const TODAY = (() => {
  const day = new Date().getDay();
  return day === 0 ? 7 : day;
})();

export default function SchedulePage() {
  const { session } = useSession();
  const role = session?.user?.role;
  const path = role === "teacher" || role === "admin" ? "/teacher/schedule" : "/schedule";
  const { data, loading, error, refresh } = useApi(path);
  const [activeDay, setActiveDay] = useState(TODAY);

  const weekdays = data?.weekdays || ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
  const lessons = data?.schedule || [];

  const byDay = useMemo(() => {
    const map = {};
    lessons.forEach((lesson) => {
      map[lesson.weekday] = map[lesson.weekday] || [];
      map[lesson.weekday].push(lesson);
    });
    Object.values(map).forEach((items) => items.sort((a, b) => (a.lesson_no || 0) - (b.lesson_no || 0)));
    return map;
  }, [lessons]);

  const dayLessons = byDay[activeDay] || [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Расписание"
        subtitle={role === "teacher" || role === "admin" ? "Уроки ваших классов. Расписание можно изменить в разделе класса." : "Уроки на неделю с темами и материалами для подготовки."}
        actions={<Badge tone="iris"><CalendarDays size={12} /> {lessons.length} уроков</Badge>}
      />

      {error && <ErrorState error={error} onRetry={refresh} />}

      {loading && !data ? (
        <Skeleton className="h-72 w-full" />
      ) : (
        <>
          <Card className="p-2">
            <div className="grid grid-cols-7 gap-1">
              {weekdays.map((label, index) => {
                const day = index + 1;
                const count = (byDay[day] || []).length;
                const isToday = day === TODAY;
                return (
                  <button
                    key={label}
                    onClick={() => setActiveDay(day)}
                    className={`relative flex flex-col items-center gap-1 rounded-xl px-1 py-2.5 text-xs font-bold transition ${
                      activeDay === day
                        ? "bg-iris-500/20 text-white shadow-[inset_0_0_0_1px_rgba(167,139,250,.3)]"
                        : "text-mist-500 hover:bg-white/5 hover:text-white"
                    }`}
                  >
                    <span>{label}</span>
                    <span className={`flex h-6 min-w-6 items-center justify-center rounded-lg px-1.5 text-[10px] ${count ? "bg-white/8 text-white" : "text-mist-600"}`}>
                      {count || "—"}
                    </span>
                    {isToday && <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" />}
                  </button>
                );
              })}
            </div>
          </Card>

          <div className="grid gap-5 lg:grid-cols-[1.15fr_0.85fr]">
            <div className="space-y-3">
              {dayLessons.length === 0 && (
                <Card>
                  <EmptyState icon="☀️" title="Уроков нет" text="Свободный день — хорошее время для тренировки или чтения." />
                </Card>
              )}
              {dayLessons.map((lesson, index) => (
                <Card key={lesson.id || index} className="p-4 sm:p-5">
                  <div className="flex items-start gap-4">
                    <div className="w-14 shrink-0 text-center">
                      <p className="font-display text-sm font-semibold text-white">{lesson.time_start || "—"}</p>
                      <p className="text-[10px] text-mist-600">{lesson.time_end || ""}</p>
                      <span className="mt-1.5 inline-flex h-5 min-w-5 items-center justify-center rounded-md bg-white/6 text-[10px] font-bold text-mist-500">
                        {lesson.lesson_no || index + 1}
                      </span>
                    </div>
                    <span className="h-14 w-px bg-white/8" />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-lg">{lesson.subject_icon || "📘"}</span>
                        <h3 className="font-display text-sm font-semibold text-white">{lesson.subject_name}</h3>
                        {lesson.topic_slug && <Badge tone="iris">тема</Badge>}
                      </div>
                      <p className="mt-1 text-xs text-mist-500">
                        {lesson.topic_title || lesson.note || "Урок по программе"}
                      </p>
                      {lesson.class_id && (
                        <p className="mt-1 inline-flex items-center gap-1 text-[10px] font-semibold text-mist-600">
                          <MapPin size={10} /> класс {lesson.grade}{lesson.letter ? ` «${lesson.letter}»` : ""}
                        </p>
                      )}
                    </div>
                    {lesson.topic_slug && (
                      <Link to={`/app/learn/${lesson.topic_slug}`} className="icon-btn h-9 w-9 shrink-0">
                        <ArrowRight size={15} />
                      </Link>
                    )}
                  </div>
                </Card>
              ))}
            </div>

            <div className="space-y-5">
              <Card className="p-5">
                <SectionTitle eyebrow="Неделя" title="Загруженность" subtitle="Сколько уроков в каждый день." />
                <div className="mt-4 space-y-2">
                  {weekdays.map((label, index) => {
                    const count = (byDay[index + 1] || []).length;
                    const max = Math.max(1, ...weekdays.map((_, i) => (byDay[i + 1] || []).length));
                    return (
                      <div key={label} className="flex items-center gap-3">
                        <span className="w-7 text-[11px] font-bold text-mist-500">{label}</span>
                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/6">
                          <div
                            className={`h-full rounded-full ${index + 1 === TODAY ? "bg-gradient-to-r from-iris-400 to-cyan-400" : "bg-white/15"}`}
                            style={{ width: `${Math.round((count / max) * 100)}%` }}
                          />
                        </div>
                        <span className="w-4 text-right text-[11px] font-bold text-white">{count}</span>
                      </div>
                    );
                  })}
                </div>
              </Card>

              <Card className="p-5">
                <SectionTitle eyebrow="Совет" title="Готовьтесь заранее" />
                <div className="mt-4 space-y-2 text-[11px] leading-relaxed text-mist-500">
                  <p className="flex gap-2"><Clock size={13} className="mt-0.5 shrink-0 text-iris-300" /> Просмотрите тему вечером — на уроке будет легче.</p>
                  <p className="flex gap-2"><Sparkles size={13} className="mt-0.5 shrink-0 text-amber-300" /> Короткая тренировка перед сном закрепляет материал.</p>
                </div>
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
