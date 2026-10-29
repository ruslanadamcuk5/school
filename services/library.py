"""Библиотека школы: книги учителя, доступ классам и ученикам, рекомендации.

Библиотека больше не «глобальная» и не онлайн:

* учитель загружает книгу (PDF) в библиотеку;
* после загрузки книга разбивается на темы по оглавлению;
* учитель отмечает, каким классам доступна книга — их ученики видят её
  в своей библиотеке;
* учитель выбирает тему книги (или книгу целиком) и рекомендует её
  классу либо отдельным ученикам — рекомендации появляются у учеников.
"""
from __future__ import annotations

import sqlite3
from typing import Any, Iterable

from database import execute, query_all, query_one
from services import textbooks as textbooks_service


def _contains(haystack: str | None, needle: str) -> bool:
    """Регистронезависимая проверка с учётом кириллицы."""
    return needle.casefold() in (haystack or "").casefold()


# --------------------------------------------------------------- книги
def find_book_for_textbook(owner_id: int, textbook_id: int) -> dict[str, Any] | None:
    """Книга библиотеки этого учителя для пособия (если уже добавлена)."""
    row = query_one(
        """SELECT id FROM library_books
            WHERE owner_id = ? AND textbook_id = ?
            ORDER BY id LIMIT 1""",
        (int(owner_id), int(textbook_id)),
    )
    return get_book(int(row["id"])) if row else None


def create_book(
    owner_id: int,
    textbook_id: int,
    subject_id: int | None,
    grade: int | None,
    title: str,
    author: str = "",
    description: str = "",
    class_ids: Iterable[int] = (),
) -> int:
    """Зарегистрировать загруженную книгу и выдать доступ классам.

    Повторное добавление того же пособия не создаёт дубль: книга учителя
    находится по ``textbook_id``, к ней лишь добавляются новые классы.
    """
    class_ids = list(class_ids)
    existing = query_one(
        """SELECT id FROM library_books
            WHERE owner_id = ? AND textbook_id = ?
            ORDER BY id LIMIT 1""",
        (int(owner_id), int(textbook_id)),
    )
    if existing:
        book_id = int(existing["id"])
        if class_ids:
            add_book_classes(book_id, class_ids)
        return book_id
    book_id = execute(
        """INSERT INTO library_books
           (owner_id, textbook_id, subject_id, grade, title, author, description)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            owner_id,
            textbook_id,
            subject_id,
            grade,
            title.strip()[:200],
            (author or "").strip()[:200] or None,
            (description or "").strip()[:1000] or None,
        ),
    )
    set_book_classes(book_id, class_ids)
    return int(book_id)


def get_book(book_id: int) -> dict[str, Any] | None:
    row = query_one(
        """SELECT lb.*, t.title AS textbook_title, t.filename, t.pages,
                  t.original_name, t.author AS textbook_author,
                  s.name AS subject_name, s.icon AS subject_icon, s.slug AS subject_slug,
                  u.first_name AS owner_first, u.last_name AS owner_last,
                  (SELECT COUNT(*) FROM library_book_classes c WHERE c.book_id = lb.id)
                      AS classes_count,
                  (SELECT COUNT(*) FROM textbook_topics tt WHERE tt.textbook_id = lb.textbook_id)
                      AS topics_count
             FROM library_books lb
             JOIN textbooks t ON t.id = lb.textbook_id
        LEFT JOIN subjects s ON s.id = lb.subject_id
        LEFT JOIN users u ON u.id = lb.owner_id
            WHERE lb.id = ?""",
        (book_id,),
    )
    return dict(row) if row else None


def update_book(book_id: int, **fields: Any) -> None:
    allowed = {"title", "author", "description", "subject_id", "grade"}
    data = {k: v for k, v in fields.items() if k in allowed}
    if not data:
        return
    sets = ", ".join(f"{k} = ?" for k in data)
    execute(f"UPDATE library_books SET {sets} WHERE id = ?", (*data.values(), book_id))


def list_books(
    owner_id: int | None = None,
    search: str = "",
    grade: int | None = None,
    subject_id: int | None = None,
) -> list[dict[str, Any]]:
    """Книги библиотеки: учитель видит свои, администратор — все."""
    sql = """SELECT lb.*, t.filename, t.pages, s.name AS subject_name, s.icon AS subject_icon,
                    u.first_name AS owner_first, u.last_name AS owner_last,
                    (SELECT COUNT(*) FROM library_book_classes c WHERE c.book_id = lb.id)
                        AS classes_count,
                    (SELECT COUNT(*) FROM textbook_topics tt WHERE tt.textbook_id = lb.textbook_id)
                        AS topics_count
               FROM library_books lb
               JOIN textbooks t ON t.id = lb.textbook_id
          LEFT JOIN subjects s ON s.id = lb.subject_id
          LEFT JOIN users u ON u.id = lb.owner_id"""
    params: list[Any] = []
    where: list[str] = []
    if owner_id:
        where.append("lb.owner_id = ?")
        params.append(owner_id)
    if grade:
        where.append("lb.grade = ?")
        params.append(grade)
    if subject_id:
        where.append("lb.subject_id = ?")
        params.append(subject_id)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY s.name, lb.grade, lb.title"
    out: list[dict[str, Any]] = []
    for row in query_all(sql, params):
        item = dict(row)
        if search and not (
            _contains(item.get("title"), search)
            or _contains(item.get("author"), search)
            or _contains(item.get("description"), search)
        ):
            continue
        item["class_ids"] = book_class_ids(int(item["id"]))
        out.append(item)
    return out


def delete_book(book_id: int) -> dict[str, Any]:
    """Удалить книгу из библиотеки вместе с загруженным файлом и её темами."""
    book = get_book(book_id)
    if not book:
        return {"ok": False, "error": "Книга не найдена"}
    textbook_id = int(book["textbook_id"])
    execute("DELETE FROM library_books WHERE id = ?", (book_id,))
    textbooks_service.purge_textbook_topics(textbook_id)
    textbooks_service.delete_textbook(textbook_id)
    return {"ok": True, "title": book["title"]}


# --------------------------------------------------------------- доступ к классам
def book_class_ids(book_id: int) -> list[int]:
    return [
        int(row["class_id"])
        for row in query_all(
            "SELECT class_id FROM library_book_classes WHERE book_id = ?", (book_id,)
        )
    ]


def book_classes(book_id: int) -> list[dict[str, Any]]:
    """Классы, которым доступна книга (с названием школы и учителем)."""
    rows = query_all(
        """SELECT sc.id, sc.grade, sc.letter, sc.title AS class_title,
                  s.name AS school_name, c.name AS city_name,
                  u.first_name AS teacher_first, u.last_name AS teacher_last,
                  (SELECT COUNT(*) FROM class_students cs WHERE cs.class_id = sc.id)
                      AS students_count
             FROM library_book_classes bc
             JOIN school_classes sc ON sc.id = bc.class_id
             JOIN schools s ON s.id = sc.school_id
             JOIN cities c ON c.id = s.city_id
        LEFT JOIN users u ON u.id = sc.teacher_id
            WHERE bc.book_id = ?
            ORDER BY sc.grade, sc.letter""",
        (book_id,),
    )
    return [dict(row) for row in rows]


def set_book_classes(book_id: int, class_ids: Iterable[int]) -> None:
    execute("DELETE FROM library_book_classes WHERE book_id = ?", (book_id,))
    add_book_classes(book_id, class_ids)


def add_book_classes(book_id: int, class_ids: Iterable[int]) -> None:
    """Добавить классы, не убирая уже открытые."""
    for class_id in dict.fromkeys(int(c) for c in class_ids if c):
        execute(
            "INSERT OR IGNORE INTO library_book_classes (book_id, class_id) VALUES (?, ?)",
            (book_id, class_id),
        )


def ensure_book_for_textbook(
    owner_id: int,
    textbook_id: int,
    class_ids: Iterable[int] = (),
) -> dict[str, Any] | None:
    """Найти книгу библиотеки для пособия или создать её.

    Так учитель может рекомендовать тему из любого загруженного пособия, даже
    если оно ещё не добавлено в его библиотеку. После рекомендации пособие
    автоматически открывается выбранным классам.
    """
    textbook = textbooks_service.get_textbook(textbook_id)
    if not textbook:
        return None
    row = query_one(
        """SELECT id FROM library_books
            WHERE owner_id = ? AND textbook_id = ?
            ORDER BY id LIMIT 1""",
        (int(owner_id), int(textbook_id)),
    )
    if row:
        book_id = int(row["id"])
        add_book_classes(book_id, class_ids)
    else:
        book_id = create_book(
            owner_id=owner_id,
            textbook_id=textbook_id,
            subject_id=textbook["subject_id"],
            grade=textbook["grade"],
            title=textbook["title"],
            author=textbook["author"] or "",
            description=textbook["description"] or "",
            class_ids=class_ids,
        )
    return get_book(book_id)


def textbooks_with_topics(
    subject_id: int | None = None,
    grade: int | None = None,
    search: str = "",
) -> list[dict[str, Any]]:
    """Все загруженные пособия с темами — источник рекомендаций учителя."""
    out: list[dict[str, Any]] = []
    for row in textbooks_service.list_textbooks(
        subject_id=subject_id, grade=grade, search=search
    ):
        topics = [dict(topic) for topic in textbooks_service.textbook_topics(row["id"])]
        if not topics:
            continue
        item = dict(row)
        item["topics"] = topics
        book = query_one(
            "SELECT id FROM library_books WHERE textbook_id = ? ORDER BY id LIMIT 1",
            (row["id"],),
        )
        item["book_id"] = int(book["id"]) if book else None
        out.append(item)
    return out


# --------------------------------------------------------------- книги ученика
def list_books_for_student(student_id: int, search: str = "") -> list[dict[str, Any]]:
    """Книги, которые учитель открыл классам ученика."""
    rows = query_all(
        """SELECT DISTINCT lb.*, t.filename, t.pages, s.name AS subject_name,
                  s.icon AS subject_icon,
                  u.first_name AS owner_first, u.last_name AS owner_last,
                  (SELECT COUNT(*) FROM textbook_topics tt WHERE tt.textbook_id = lb.textbook_id)
                      AS topics_count
             FROM library_books lb
             JOIN textbooks t ON t.id = lb.textbook_id
        LEFT JOIN subjects s ON s.id = lb.subject_id
        LEFT JOIN users u ON u.id = lb.owner_id
            WHERE lb.id IN (
                  SELECT bc.book_id FROM library_book_classes bc
                   WHERE bc.class_id IN (
                         SELECT class_id FROM class_students WHERE student_id = ?
                   )
            )
            ORDER BY s.name, lb.grade, lb.title""",
        (student_id,),
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        if search and not (
            _contains(item.get("title"), search)
            or _contains(item.get("author"), search)
            or _contains(item.get("subject_name"), search)
        ):
            continue
        out.append(item)
    return out


def can_access_book(user: sqlite3.Row | dict | None, book_id: int) -> bool:
    """Может ли пользователь открыть книгу библиотеки."""
    if not user:
        return False
    role = user["role"]
    user_id = int(user["id"])
    if role == "admin":
        return True
    if role == "teacher":
        book = get_book(book_id)
        if book and int(book["owner_id"]) == user_id:
            return True
        row = query_one(
            """SELECT 1 AS x FROM library_book_classes bc
                 JOIN school_classes sc ON sc.id = bc.class_id
                WHERE bc.book_id = ? AND sc.teacher_id = ? LIMIT 1""",
            (book_id, user_id),
        )
        return bool(row)
    if role == "student":
        row = query_one(
            """SELECT 1 AS x FROM library_book_classes bc
                 JOIN class_students cs ON cs.class_id = bc.class_id
                WHERE bc.book_id = ? AND cs.student_id = ? LIMIT 1""",
            (book_id, user_id),
        )
        if row:
            return True
        return bool(
            query_one(
                """SELECT 1 AS x FROM library_recommendations r
                    WHERE r.book_id = ? AND (r.student_id = ?
                       OR r.class_id IN (SELECT class_id FROM class_students
                                          WHERE student_id = ?)) LIMIT 1""",
                (book_id, user_id, user_id),
            )
        )
    if role == "parent":
        row = query_one(
            """SELECT 1 AS x FROM library_book_classes bc
                 JOIN class_students cs ON cs.class_id = bc.class_id
                 JOIN parent_children pc ON pc.child_id = cs.student_id
                WHERE bc.book_id = ? AND pc.parent_id = ? LIMIT 1""",
            (book_id, user_id),
        )
        return bool(row)
    return False


# --------------------------------------------------------------- темы книги
def book_topics(book_id: int) -> list[dict[str, Any]]:
    """Темы книги (из оглавления) со страницами."""
    rows = query_all(
        """SELECT tt.topic_slug, tt.page, tt.page_end,
                  tp.title, tp.icon, tp.description, tp.grade,
                  tp.subject_id
             FROM library_books lb
             JOIN textbook_topics tt ON tt.textbook_id = lb.textbook_id
        LEFT JOIN topics tp ON tp.slug = tt.topic_slug
            WHERE lb.id = ?
            ORDER BY tt.page, tp.title""",
        (book_id,),
    )
    return [dict(row) for row in rows]


def remove_book_topic(book_id: int, topic_slug: str) -> bool:
    """Убрать тему из книги (например, если оглавление распознано неверно)."""
    book = get_book(book_id)
    if not book:
        return False
    execute(
        "DELETE FROM textbook_topics WHERE textbook_id = ? AND topic_slug = ?",
        (book["textbook_id"], topic_slug),
    )
    return True


def teacher_students(teacher_id: int) -> list[dict[str, Any]]:
    """Ученики классов учителя — из них выбираются адресаты рекомендаций."""
    rows = query_all(
        """SELECT DISTINCT u.id, u.first_name, u.last_name, u.login,
                  sc.id AS class_id, sc.grade, sc.letter
             FROM school_classes sc
             JOIN class_students cs ON cs.class_id = sc.id
             JOIN users u ON u.id = cs.student_id
            WHERE sc.teacher_id = ?
            ORDER BY sc.grade, sc.letter, u.last_name, u.first_name""",
        (teacher_id,),
    )
    return [dict(row) for row in rows]


# --------------------------------------------------------------- рекомендации
def _recommendation_exists(
    book_id: int, topic_slug: str | None, target_kind: str,
    student_id: int | None = None, class_id: int | None = None,
) -> bool:
    row = query_one(
        """SELECT 1 AS x FROM library_recommendations
            WHERE book_id = ? AND IFNULL(topic_slug, '') = IFNULL(?, '')
              AND target_kind = ?
              AND IFNULL(student_id, 0) = IFNULL(?, 0)
              AND IFNULL(class_id, 0) = IFNULL(?, 0)""",
        (book_id, topic_slug or "", target_kind, student_id, class_id),
    )
    return bool(row)


def _library_recipients(class_id: int = 0, student_id: int = 0) -> set[int]:
    """Кому показать рекомендацию: ученики класса/ученик и их родители."""
    from services import auth

    students: set[int] = set()
    if student_id:
        students.add(int(student_id))
    if class_id:
        for row in query_all(
            "SELECT student_id FROM class_students WHERE class_id = ?",
            (int(class_id),),
        ):
            students.add(int(row["student_id"]))
    recipients = set(students)
    for child_id in students:
        try:
            for parent in auth.parents_of(child_id):
                recipients.add(int(parent["id"]))
        except Exception:  # pragma: no cover - связи родителей не критичны
            continue
    return recipients


def _notify_recommendation(
    teacher_id: int,
    book: dict[str, Any],
    topic_slug: str | None,
    note: str,
    class_id: int = 0,
    student_id: int = 0,
) -> int:
    """Сообщить ученику (и родителям) о новой рекомендации литературы."""
    from services import notifications as notifications_service

    recipients = _library_recipients(class_id=class_id, student_id=student_id)
    recipients.discard(int(teacher_id))
    if not recipients:
        return 0
    topic_title = ""
    if topic_slug:
        row = query_one("SELECT title FROM topics WHERE slug = ?", (topic_slug,))
        topic_title = row["title"] if row else ""
    body = f"«{book['title']}»"
    if topic_title:
        body += f" — тема «{topic_title}»"
    if note:
        body += f". {note}"
    body += ". Откройте библиотеку, чтобы читать."
    sent = 0
    for user_id in recipients:
        notifications_service.push(
            user_id,
            notifications_service.KIND_LIBRARY_NEW,
            "📚 Рекомендована литература",
            body,
            class_id=int(class_id or 0),
            sender_id=int(teacher_id or 0),
            link="/library/",
            dedup_key=f"library_new:{class_id or 0}:{student_id or 0}:{user_id}:{book['id']}:{topic_slug or ''}",
        )
        sent += 1
    return sent


def recommend(
    teacher_id: int,
    book_id: int,
    topic_slug: str | None = None,
    class_ids: Iterable[int] = (),
    student_ids: Iterable[int] = (),
    note: str = "",
) -> dict[str, Any]:
    """Рекомендовать тему книги (или книгу целиком) классам и ученикам."""
    book = get_book(book_id)
    if not book:
        return {"ok": False, "created": 0, "skipped": 0, "error": "Книга не найдена"}
    if topic_slug:
        topic = query_one(
            """SELECT 1 AS x FROM textbook_topics
                WHERE textbook_id = ? AND topic_slug = ?""",
            (book["textbook_id"], topic_slug),
        )
        if not topic:
            return {"ok": False, "created": 0, "skipped": 0,
                    "error": "Эта тема не относится к выбранной книге"}
    note = (note or "").strip()[:500]
    created = skipped = 0
    for class_id in dict.fromkeys(int(c) for c in class_ids if c):
        if _recommendation_exists(book_id, topic_slug, "class", class_id=class_id):
            skipped += 1
            continue
        execute(
            """INSERT INTO library_recommendations
               (teacher_id, book_id, topic_slug, target_kind, class_id, note)
               VALUES (?, ?, ?, 'class', ?, ?)""",
            (teacher_id, book_id, topic_slug or None, class_id, note or None),
        )
        _notify_recommendation(
            teacher_id, book, topic_slug, note, class_id=class_id
        )
        created += 1
    for student_id in dict.fromkeys(int(s) for s in student_ids if s):
        if _recommendation_exists(book_id, topic_slug, "student", student_id=student_id):
            skipped += 1
            continue
        execute(
            """INSERT INTO library_recommendations
               (teacher_id, book_id, topic_slug, target_kind, student_id, note)
               VALUES (?, ?, ?, 'student', ?, ?)""",
            (teacher_id, book_id, topic_slug or None, student_id, note or None),
        )
        _notify_recommendation(
            teacher_id, book, topic_slug, note, student_id=student_id
        )
        created += 1
    return {"ok": created > 0 or skipped > 0, "created": created, "skipped": skipped}


def recommend_textbook_topic(
    teacher_id: int,
    textbook_id: int,
    topic_slug: str | None = None,
    class_ids: Iterable[int] = (),
    student_ids: Iterable[int] = (),
    note: str = "",
) -> dict[str, Any]:
    """Рекомендовать тему из любого пособия, создав книгу при необходимости."""
    class_ids = list(dict.fromkeys(int(c) for c in class_ids if c))
    student_ids = list(dict.fromkeys(int(s) for s in student_ids if s))
    # Если рекомендация адресована конкретному ученику, книгу всё равно нужно
    # открыть его классу: доступ к пособиям в библиотеке классный, а не личный.
    if student_ids:
        placeholders = ",".join("?" for _ in student_ids)
        rows = query_all(
            f"""SELECT DISTINCT class_id FROM class_students
                 WHERE student_id IN ({placeholders})""",
            student_ids,
        )
        class_ids.extend(int(row["class_id"]) for row in rows)
        class_ids = list(dict.fromkeys(class_ids))
    book = ensure_book_for_textbook(teacher_id, textbook_id, class_ids)
    if not book:
        return {"ok": False, "created": 0, "skipped": 0, "error": "Пособие не найдено"}
    return recommend(
        teacher_id,
        int(book["id"]),
        topic_slug=topic_slug,
        class_ids=class_ids,
        student_ids=student_ids,
        note=note,
    )


def recommendations_for_student(student_id: int) -> list[dict[str, Any]]:
    """Все рекомендации ученику (классу и лично), с отметкой о прочтении."""
    rows = query_all(
        """SELECT r.*, lb.title, lb.textbook_id, lb.grade, lb.subject_id,
                  t.pages, tp.title AS topic_title, tp.icon AS topic_icon,
                  tt.page AS page, tt.page_end AS page_end,
                  u.first_name AS teacher_first, u.last_name AS teacher_last,
                  CASE WHEN d.rec_id IS NULL THEN 0 ELSE 1 END AS done
             FROM library_recommendations r
             JOIN library_books lb ON lb.id = r.book_id
             JOIN textbooks t ON t.id = lb.textbook_id
        LEFT JOIN topics tp ON tp.slug = r.topic_slug
        LEFT JOIN textbook_topics tt ON tt.textbook_id = lb.textbook_id
                                    AND tt.topic_slug = r.topic_slug
        LEFT JOIN users u ON u.id = r.teacher_id
        LEFT JOIN library_recommendation_done d ON d.rec_id = r.id AND d.student_id = :me
            WHERE r.student_id = :me
               OR r.class_id IN (SELECT class_id FROM class_students WHERE student_id = :me)
            ORDER BY done ASC, r.created_at DESC""",
        {"me": student_id},
    )
    return [dict(row) for row in rows]


def recommendations_by_teacher(teacher_id: int) -> list[dict[str, Any]]:
    """Рекомендации, отправленные учителем, с прогрессом выполнения."""
    rows = query_all(
        """SELECT r.*, lb.title, lb.textbook_id, lb.grade,
                  tp.title AS topic_title, tt.page AS page, tt.page_end,
                  s.first_name AS student_first, s.last_name AS student_last,
                  sc.grade AS class_grade, sc.letter AS class_letter,
                  (SELECT COUNT(*) FROM library_recommendation_done d
                    WHERE d.rec_id = r.id) AS done_count,
                  CASE WHEN r.target_kind = 'class'
                       THEN (SELECT COUNT(*) FROM class_students cs WHERE cs.class_id = r.class_id)
                       ELSE 1 END AS total_count
             FROM library_recommendations r
             JOIN library_books lb ON lb.id = r.book_id
        LEFT JOIN topics tp ON tp.slug = r.topic_slug
        LEFT JOIN textbook_topics tt ON tt.textbook_id = lb.textbook_id
                                    AND tt.topic_slug = r.topic_slug
        LEFT JOIN users s ON s.id = r.student_id
        LEFT JOIN school_classes sc ON sc.id = r.class_id
            WHERE r.teacher_id = ?
            ORDER BY r.created_at DESC, r.id DESC""",
        (teacher_id,),
    )
    return [dict(row) for row in rows]


def recommendation_visible_to(rec_id: int, student_id: int) -> bool:
    row = query_one(
        """SELECT 1 AS x FROM library_recommendations r
            WHERE r.id = ? AND (r.student_id = ?
               OR r.class_id IN (SELECT class_id FROM class_students WHERE student_id = ?))""",
        (rec_id, student_id, student_id),
    )
    return bool(row)


def mark_recommendation_done(rec_id: int, student_id: int) -> bool:
    if not recommendation_visible_to(rec_id, student_id):
        return False
    execute(
        "INSERT OR IGNORE INTO library_recommendation_done (rec_id, student_id) VALUES (?, ?)",
        (rec_id, student_id),
    )
    return True


def revoke_recommendation(rec_id: int, teacher_id: int) -> bool:
    row = query_one(
        "SELECT id FROM library_recommendations WHERE id = ? AND teacher_id = ?",
        (rec_id, teacher_id),
    )
    if not row:
        return False
    execute("DELETE FROM library_recommendations WHERE id = ?", (rec_id,))
    return True


def unread_for_student(student_id: int) -> list[dict[str, Any]]:
    """Непрочитанные рекомендации ученика — для подсказки на главной."""
    return [rec for rec in recommendations_for_student(student_id) if not rec["done"]]


def sync_library_unread(hours: int = 24) -> int:
    """Напомнить про рекомендованную литературу, которую ещё не открыли."""
    from services import notifications as notifications_service

    rows = query_all(
        """SELECT r.*, lb.title AS book_title, tp.title AS topic_title
             FROM library_recommendations r
             JOIN library_books lb ON lb.id = r.book_id
        LEFT JOIN topics tp ON tp.slug = r.topic_slug
            WHERE r.created_at <= datetime('now', ?)""",
        (f"-{int(hours)} hours",),
    )
    sent = 0
    for rec in rows:
        students: set[int] = set()
        if rec["student_id"]:
            students.add(int(rec["student_id"]))
        if rec["class_id"]:
            for row in query_all(
                "SELECT student_id FROM class_students WHERE class_id = ?",
                (int(rec["class_id"]),),
            ):
                students.add(int(row["student_id"]))
        for student_id in students:
            done = query_one(
                "SELECT 1 FROM library_recommendation_done WHERE rec_id = ? AND student_id = ?",
                (rec["id"], student_id),
            )
            if done:
                continue
            key = f"library_unread:{rec['id']}:{student_id}"
            if query_one("SELECT 1 FROM app_notifications WHERE dedup_key = ?", (key,)):
                continue
            body = f"«{rec['book_title']}»"
            if rec["topic_title"]:
                body += f" — тема «{rec['topic_title']}»"
            body += ". Прочитайте, когда будет удобно, и отметьте в библиотеке."
            targets = _library_recipients(student_id=student_id)
            for user_id in targets:
                notifications_service.push(
                    user_id,
                    notifications_service.KIND_LIBRARY_READ,
                    "📖 Напоминание: рекомендованная литература",
                    body,
                    sender_id=int(rec["teacher_id"] or 0),
                    link="/library/",
                    dedup_key=f"{key}:{user_id}",
                )
                sent += 1
    return sent


# --------------------------------------------------------------- сводка
def teacher_stats(teacher_id: int) -> dict[str, int]:
    books = query_one(
        "SELECT COUNT(*) AS n FROM library_books WHERE owner_id = ?", (teacher_id,)
    )["n"]
    classes = query_one(
        """SELECT COUNT(DISTINCT bc.class_id) AS n FROM library_book_classes bc
             JOIN library_books lb ON lb.id = bc.book_id
            WHERE lb.owner_id = ?""",
        (teacher_id,),
    )["n"]
    recommendations = query_one(
        "SELECT COUNT(*) AS n FROM library_recommendations WHERE teacher_id = ?",
        (teacher_id,),
    )["n"]
    return {"books": books, "classes": classes, "recommendations": recommendations}


def student_stats(student_id: int) -> dict[str, int]:
    books = len(list_books_for_student(student_id))
    recommendations = recommendations_for_student(student_id)
    active = sum(1 for rec in recommendations if not rec["done"])
    done = sum(1 for rec in recommendations if rec["done"])
    return {"books": books, "active": active, "done": done}
