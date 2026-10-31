"""Геолокация детей: точки GPS, трек за день и доступ родителей.

Передача местоположения работает всегда: родитель видит последнюю точку и
историю перемещений ребёнка на карте, настроенной администратором. Родитель
может отправить команду принудительного включения геолокации на устройстве
ребёнка (``force_requested_at``); приложение ребёнка подтверждает её, когда
служба геолокации запущена (``force_ack_at``). История хранится ограниченное
время и доступна только родителям этого ребёнка, администратору и самому
ребёнку.
"""
from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta, timezone

from database import connect, execute, query_all, query_one

RETENTION_DAYS = 3
MAX_POINTS_PER_BATCH = 300
MAX_ACCURACY_M = 5000
MAX_BACKDATE_DAYS = RETENTION_DAYS
FUTURE_SKEW = timedelta(minutes=10)
STALE_AFTER = timedelta(minutes=30)

# Чистка трека. Сырые точки GPS «дрожат» даже когда телефон лежит на столе:
# без фильтра за день набегают километры ложного пути. На трек попадают
# только достаточно точные точки, стояние на месте схлопывается в одну
# вершину, а невозможные скачки (телепорты) отбрасываются.
TRACK_MAX_ACCURACY_M = 150.0
TRACK_STATIONARY_MIN_M = 30.0
TRACK_STATIONARY_MAX_M = 120.0
TRACK_TELEPORT_MIN_M = 400.0
TRACK_TELEPORT_WINDOW_S = 20 * 60
TRACK_MAX_SPEED_MPS = 55.0          # ~198 км/ч
LATEST_MAX_ACCURACY_M = 150.0
LATEST_GOOD_WINDOW = timedelta(minutes=15)


class LocationError(Exception):
    """Ошибка геолокации с машинным кодом и текстом для пользователя."""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


# ------------------------------------------------------------------ время
def clamp_tz(minutes: int | None) -> int:
    try:
        value = int(minutes or 0)
    except (TypeError, ValueError):
        value = 0
    return max(-720, min(840, value))


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_day(value: str | None, tz_minutes: int = 0) -> date:
    raw = (value or "").strip()
    if raw:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            raise LocationError("bad_date", "Дата должна быть в формате ГГГГ-ММ-ДД")
    return today_for_tz(tz_minutes)


def today_for_tz(tz_minutes: int = 0) -> date:
    offset = timezone(timedelta(minutes=clamp_tz(tz_minutes)))
    return datetime.now(timezone.utc).astimezone(offset).date()


def day_bounds(day: date, tz_minutes: int = 0) -> tuple[str, str]:
    """Границы локального дня в UTC (для запросов к SQLite)."""
    offset = timezone(timedelta(minutes=clamp_tz(tz_minutes)))
    start = datetime.combine(day, time.min, tzinfo=offset).astimezone(timezone.utc)
    end = start + timedelta(days=1)
    return _sql(start), _sql(end)


def _sql(value: datetime) -> str:
    return _utc(value).strftime("%Y-%m-%d %H:%M:%S")


def _iso(value: str | None) -> str | None:
    if not value:
        return None
    return str(value).replace(" ", "T") + "Z"


def _local_label(value: str | None, tz_minutes: int) -> str:
    if not value:
        return ""
    try:
        parsed = datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return str(value)
    offset = timezone(timedelta(minutes=clamp_tz(tz_minutes)))
    return parsed.astimezone(offset).strftime("%H:%M")


def _parse_recorded(value, fallback: datetime | None = None) -> datetime:
    if value in (None, ""):
        return fallback or datetime.now(timezone.utc)
    if isinstance(value, (int, float)):
        stamp = float(value)
        if stamp > 1e11:  # миллисекунды
            stamp /= 1000.0
        return datetime.fromtimestamp(stamp, tz=timezone.utc)
    raw = str(value).strip()
    if raw.isdigit():
        return _parse_recorded(int(raw))
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00").replace("z", "+00:00"))
    except ValueError:
        raise LocationError("bad_time", "Не удалось разобрать время точки")
    return _utc(parsed).replace(microsecond=0)


# ------------------------------------------------------------------ состояние
def ensure_settings(learner_id: int) -> None:
    execute(
        "INSERT OR IGNORE INTO location_sharing (learner_id, enabled) VALUES (?, 1)",
        (int(learner_id),),
    )


def settings(learner_id: int) -> dict:
    ensure_settings(learner_id)
    row = query_one("SELECT * FROM location_sharing WHERE learner_id = ?", (int(learner_id),))
    force_requested_at = row["force_requested_at"] if row else None
    force_ack_at = row["force_ack_at"] if row else None
    force_pending = bool(force_requested_at and not force_ack_at)
    return {
        # Передача больше не выключается ребёнком: значение всегда true.
        "enabled": True,
        "updated_at": _iso(row["updated_at"]) if row else None,
        "last_point_at": _iso(row["last_point_at"]) if row else None,
        "retention_days": RETENTION_DAYS,
        "force_pending": force_pending,
        "force_requested_at": _iso(force_requested_at),
        "force_requested_by": row["force_requested_by"] if row else None,
        "force_ack_at": _iso(force_ack_at),
    }


def sharing_enabled(learner_id: int) -> bool:
    """Совместимость со старым кодом: передача включена всегда."""
    return True


def set_sharing(learner_id: int, enabled: bool = True,
                by_user_id: int | None = None) -> dict:
    """Оставить передачу включённой (старый клиент мог прислать enabled=false)."""
    ensure_settings(learner_id)
    execute(
        """UPDATE location_sharing
              SET enabled = 1, updated_by = ?, updated_at = datetime('now')
            WHERE learner_id = ?""",
        (by_user_id, int(learner_id)),
    )
    return settings(learner_id)


def force_request(learner_id: int, sender_id: int = 0) -> dict:
    """Принудительно включить геолокацию на устройстве ребёнка."""
    ensure_settings(learner_id)
    execute(
        """UPDATE location_sharing
              SET enabled = 1, force_requested_at = datetime('now'),
                  force_requested_by = ?, force_ack_at = NULL,
                  updated_at = datetime('now')
            WHERE learner_id = ?""",
        (int(sender_id or 0), int(learner_id)),
    )
    _notify_force(learner_id, sender_id)
    if sender_id:
        execute(
            "INSERT INTO audit_log (user_id, action, entity, entity_id, details) "
            "VALUES (?, 'location_force', 'learner', ?, '')",
            (int(sender_id), str(int(learner_id))),
        )
    return settings(learner_id)


def ack_force(learner_id: int) -> dict:
    """Подтвердить, что устройство ребёнка получило команду включения."""
    ensure_settings(learner_id)
    execute(
        """UPDATE location_sharing
              SET force_ack_at = datetime('now'), updated_at = datetime('now')
            WHERE learner_id = ?""",
        (int(learner_id),),
    )
    return settings(learner_id)


def _notify_force(learner_id: int, sender_id: int) -> None:
    from services import notifications as notifications_service

    title = "📍 Родитель включил геолокацию"
    body = (
        "Передача местоположения включена родителем и запускается автоматически. "
        "Если Android или браузер ещё не дал доступ к GPS, разреши его один раз."
    )
    dedup_key = (
        "location_force:" + str(int(learner_id)) + ":"
        + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    )
    linked = query_one(
        "SELECT user_id FROM learner_accounts WHERE learner_id = ?", (int(learner_id),)
    )
    try:
        notifications_service.push(
            int(linked["user_id"]) if linked and linked["user_id"] else 0,
            "location_force", title, body,
            learner_id=int(learner_id), sender_id=int(sender_id or 0),
            link="/location/",
            dedup_key=dedup_key,
        )
    except Exception:  # pragma: no cover - уведомление не должно ломать запрос
        pass


def request_sharing(learner_id: int, sender_id: int = 0) -> dict:
    """Старое имя команды: теперь это принудительное включение геолокации."""
    return force_request(learner_id, sender_id)


# ------------------------------------------------------------------ точки
def _number(value, *, code: str, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise LocationError(code, "Координаты должны быть числами")
    if not math.isfinite(number) or number < minimum or number > maximum:
        raise LocationError(code, "Координаты вне допустимого диапазона")
    return number


def _optional(value, *, minimum: float, maximum: float) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return max(minimum, min(maximum, number))


def _normalize_point(raw: dict, now: datetime) -> tuple | None:
    if not isinstance(raw, dict):
        raise LocationError("bad_point", "Точка должна быть объектом")
    lat = _number(raw.get("lat", raw.get("latitude")), code="bad_lat",
                  minimum=-90, maximum=90)
    lon = _number(raw.get("lon", raw.get("lng", raw.get("longitude"))), code="bad_lon",
                  minimum=-180, maximum=180)
    recorded = _parse_recorded(raw.get("recorded_at", raw.get("time")), now)
    if recorded > now + FUTURE_SKEW:
        raise LocationError("future_point", "Время точки из будущего")
    if recorded < now - timedelta(days=MAX_BACKDATE_DAYS):
        return None
    accuracy = _optional(raw.get("accuracy"), minimum=0, maximum=MAX_ACCURACY_M)
    altitude = _optional(raw.get("altitude"), minimum=-500, maximum=10000)
    speed = _optional(raw.get("speed"), minimum=0, maximum=150)
    battery = _optional(raw.get("battery"), minimum=0, maximum=100)
    source = str(raw.get("source") or "gps")[:16]
    return (
        int(raw.get("_learner_id") or 0),
        round(lat, 7),
        round(lon, 7),
        round(accuracy, 1) if accuracy is not None else None,
        round(altitude, 1) if altitude is not None else None,
        round(speed, 2) if speed is not None else None,
        int(battery) if battery is not None else None,
        source,
        _sql(recorded),
    )


def record_points(learner_id: int, points, battery: int | None = None) -> dict:
    """Принять пачку точек. Возвращает число сохранённых и последнюю точку."""
    ensure_settings(learner_id)
    if not isinstance(points, list) or not points:
        raise LocationError("no_points", "Нет точек для сохранения")
    if len(points) > MAX_POINTS_PER_BATCH:
        raise LocationError("too_many_points",
                            f"За один раз можно передать не больше {MAX_POINTS_PER_BATCH} точек")
    now = datetime.now(timezone.utc)
    rows = []
    for raw in points:
        if isinstance(raw, dict):
            raw = dict(raw)
            raw["_learner_id"] = learner_id
        prepared = _normalize_point(raw, now)
        if prepared is not None:
            rows.append(prepared)
    if not rows:
        raise LocationError("no_points", "Нет актуальных точек для сохранения")

    conn = connect()
    try:
        before = conn.total_changes
        conn.executemany(
            """INSERT OR IGNORE INTO learner_locations
                   (learner_id, lat, lon, accuracy, altitude, speed, battery,
                    source, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        added = conn.total_changes - before
        last = max(row[-1] for row in rows)
        conn.execute(
            """UPDATE location_sharing
                  SET enabled = 1, last_point_at = ?,
                      force_ack_at = CASE
                          WHEN force_requested_at IS NOT NULL THEN datetime('now')
                          ELSE force_ack_at
                      END,
                      updated_at = datetime('now')
                WHERE learner_id = ?""",
            (last, int(learner_id)),
        )
        conn.execute(
            "DELETE FROM learner_locations "
            "WHERE learner_id = ? AND recorded_at < datetime('now', ?)",
            (int(learner_id), f"-{RETENTION_DAYS} days"),
        )
    finally:
        conn.close()
    return {
        "saved": int(added),
        "received": len(points),
        "last_point_at": _iso(last),
        "settings": settings(learner_id),
    }


def _point_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _good_accuracy(row) -> bool:
    """Точка достаточно точная, чтобы показывать её как местоположение."""
    accuracy = row["accuracy"]
    return accuracy is None or float(accuracy) <= LATEST_MAX_ACCURACY_M


def latest_point(learner_id: int, tz_minutes: int = 0) -> dict | None:
    """Последняя точка, но без грубых сетевых «приблизительно здесь».

    Если последняя точка пришла от сотовой вышки с точностью в километры,
    показываем более раннюю точную точку (не старше 15 минут). Иначе лучше
    честно показать свежую, но неточную позицию.
    """
    rows = query_all(
        "SELECT * FROM learner_locations WHERE learner_id = ? "
        "ORDER BY recorded_at DESC, id DESC LIMIT 20",
        (int(learner_id),),
    )
    if not rows:
        return None
    chosen = rows[0]
    if not _good_accuracy(chosen):
        for row in rows[1:]:
            if _good_accuracy(row):
                latest_at = _point_time(chosen["recorded_at"])
                good_at = _point_time(row["recorded_at"])
                if latest_at and good_at and latest_at - good_at <= LATEST_GOOD_WINDOW:
                    chosen = row
                break
    return point_payload(chosen, tz_minutes)


def point_payload(row, tz_minutes: int = 0) -> dict:
    return {
        "id": int(row["id"]),
        "lat": float(row["lat"]),
        "lon": float(row["lon"]),
        "accuracy": row["accuracy"],
        "altitude": row["altitude"],
        "speed": row["speed"],
        "battery": row["battery"],
        "source": row["source"],
        "recorded_at": _iso(row["recorded_at"]),
        "time": _local_label(row["recorded_at"], tz_minutes),
    }


def _distance_m(a: dict, b: dict) -> float:
    radius = 6371000.0
    lat1 = math.radians(a["lat"])
    lat2 = math.radians(b["lat"])
    dlat = lat2 - lat1
    dlon = math.radians(b["lon"] - a["lon"])
    h = (math.sin(dlat / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
    return 2 * radius * math.asin(min(1.0, math.sqrt(h)))


def _clean_track(points: list[dict]) -> list[dict]:
    """Убрать из трека шум GPS, стояние на месте и невозможные скачки.

    Возвращает вершины, по которым можно честно посчитать расстояние и
    нарисовать маршрут. Если ребёнок весь день дома, останется одна точка
    (плюс финальная точка с актуальным временем) и нулевой путь.
    """
    accepted: list[dict] = []
    last_stationary: dict | None = None
    for point in points:
        accuracy = point.get("accuracy")
        if accuracy is not None and float(accuracy) > TRACK_MAX_ACCURACY_M:
            continue
        if not accepted:
            accepted.append(dict(point))
            continue
        anchor = accepted[-1]
        distance = _distance_m(anchor, point)
        radius = max(
            TRACK_STATIONARY_MIN_M,
            min(TRACK_STATIONARY_MAX_M, float(accuracy or 0) * 1.5),
        )
        if distance <= radius:
            # Телефон лежит на столе, а GPS «гуляет» вокруг дома. Новую
            # вершину не добавляем, но запоминаем время последнего визита.
            last_stationary = point
            continue
        previous_at = _point_time(anchor.get("recorded_at"))
        current_at = _point_time(point.get("recorded_at"))
        if previous_at and current_at:
            seconds = (current_at - previous_at).total_seconds()
            if seconds <= 0:
                continue
            if (
                distance >= TRACK_TELEPORT_MIN_M
                and seconds <= TRACK_TELEPORT_WINDOW_S
                and distance / seconds > TRACK_MAX_SPEED_MPS
            ):
                # 2 км за минуту пешком не пройти — это глюк GPS.
                continue
        accepted.append(dict(point))
        last_stationary = None
    if accepted and last_stationary is not None:
        tail_at = _point_time(last_stationary.get("recorded_at"))
        anchor_at = _point_time(accepted[-1].get("recorded_at"))
        if tail_at and anchor_at and tail_at > anchor_at:
            tail = dict(accepted[-1])
            tail.update(
                {
                    "recorded_at": last_stationary["recorded_at"],
                    "time": last_stationary.get("time", tail.get("time")),
                    "battery": last_stationary.get("battery", tail.get("battery")),
                    "id": last_stationary.get("id", tail.get("id")),
                }
            )
            accepted.append(tail)
    return accepted


def _summary(points: list[dict]) -> dict:
    if not points:
        return {
            "points": 0, "distance_m": 0, "duration_min": 0,
            "first_at": None, "last_at": None, "max_speed": 0, "accuracy": None,
        }
    distance = 0.0
    max_speed = 0.0
    accuracy_values = []
    for index, point in enumerate(points):
        if index:
            step = _distance_m(points[index - 1], point)
            # Телепорт на многие километры — почти всегда плохая точка.
            if step < 5000:
                distance += step
        if point.get("speed"):
            max_speed = max(max_speed, float(point["speed"]))
        if point.get("accuracy") is not None:
            accuracy_values.append(float(point["accuracy"]))
    first = points[0]["recorded_at"]
    last = points[-1]["recorded_at"]
    try:
        start = datetime.fromisoformat(str(first).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
        duration = int((end - start).total_seconds() // 60)
    except (TypeError, ValueError):
        duration = 0
    return {
        "points": len(points),
        "distance_m": round(distance),
        "duration_min": max(0, duration),
        "first_at": first,
        "last_at": last,
        "max_speed": round(max_speed, 1),
        "accuracy": round(sum(accuracy_values) / len(accuracy_values)) if accuracy_values else None,
    }


def trail(learner_id: int, day: date, tz_minutes: int = 0) -> dict:
    tz_minutes = clamp_tz(tz_minutes)
    start, end = day_bounds(day, tz_minutes)
    rows = query_all(
        """SELECT * FROM learner_locations
            WHERE learner_id = ? AND recorded_at >= ? AND recorded_at < ?
            ORDER BY recorded_at, id""",
        (int(learner_id), start, end),
    )
    raw_points = [point_payload(row, tz_minutes) for row in rows]
    points = _clean_track(raw_points)
    summary = _summary(points)
    summary["raw_points"] = len(raw_points)
    summary["hidden_points"] = max(0, len(raw_points) - len(points))
    return {
        "day": day.isoformat(),
        "sharing": settings(learner_id),
        "points": points,
        "summary": summary,
        "latest": latest_point(learner_id, tz_minutes),
    }


def overview(learners, tz_minutes: int = 0) -> list[dict]:
    """Последняя точка и статус для списка детей родителя."""
    tz_minutes = clamp_tz(tz_minutes)
    day = today_for_tz(tz_minutes)
    start, end = day_bounds(day, tz_minutes)
    result = []
    for learner in learners:
        learner_id = int(learner["id"])
        info = settings(learner_id)
        last = latest_point(learner_id, tz_minutes)
        count = query_one(
            "SELECT COUNT(*) AS c FROM learner_locations "
            "WHERE learner_id = ? AND recorded_at >= ? AND recorded_at < ?",
            (learner_id, start, end),
        )
        stale = True
        if last and last.get("recorded_at"):
            try:
                seen = datetime.fromisoformat(last["recorded_at"].replace("Z", "+00:00"))
                stale = datetime.now(timezone.utc) - seen > STALE_AFTER
            except ValueError:
                stale = True
        result.append(
            {
                "learner": {
                    "id": learner_id,
                    "name": learner["name"],
                    "avatar": learner["avatar"],
                    "grade": int(learner["grade"] or 1),
                },
                "sharing": info,
                "last_point": last,
                "points_today": int(count["c"] or 0),
                "stale": stale,
            }
        )
    return result


def can_parent_see(parent_id: int, learner_id: int) -> bool:
    row = query_one(
        """SELECT 1 AS ok FROM parent_children pc
             JOIN learner_accounts la ON la.user_id = pc.child_id
            WHERE pc.parent_id = ? AND la.learner_id = ?""",
        (int(parent_id), int(learner_id)),
    )
    if row:
        return True
    return bool(
        query_one(
            """SELECT 1 AS ok FROM parent_children pc
                 JOIN learners l ON l.user_id = pc.child_id
                WHERE pc.parent_id = ? AND l.id = ?""",
            (int(parent_id), int(learner_id)),
        )
    )

