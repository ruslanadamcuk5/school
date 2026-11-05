"""API: учебное заведение в профиле — город, школа, классы и предметы.

Ученик выбирает одну связку «город → школа → класс». Учитель выбирает
город, школу и несколько классов, а для каждого класса — свои предметы.
Каталог отдаёт только справочники; привязка хранится в users,
class_students, teacher_classes и teacher_subjects.
"""
from __future__ import annotations

from typing import Any

from flask import jsonify, request

from services import orgs
from services import auth as auth_service

from . import bp
from .deps import current_user, fail, json_body, require_actor, row_dict


def _int_value(value: Any, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        fail(400, "bad_request", f"Выберите {field}")


def _int_list(value: Any) -> list[int]:
    if not isinstance(value, (list, tuple)):
        return []
    result: list[int] = []
    for item in value:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return list(dict.fromkeys(result))


def _subject_map(value: Any) -> dict[int, list[int]]:
    """Нормализовать JSON-объект «класс → предметы» (ключи часто строки)."""
    if not isinstance(value, dict):
        return {}
    result: dict[int, list[int]] = {}
    for class_id, subject_ids in value.items():
        try:
            key = int(class_id)
        except (TypeError, ValueError):
            continue
        result[key] = _int_list(subject_ids)
    return result


def _basic_payload(user) -> dict[str, Any]:
    city = orgs.get_city(int(user["city_id"])) if user["city_id"] else None
    school = orgs.get_school(int(user["school_id"])) if user["school_id"] else None
    return {
        "ok": True,
        "role": user["role"],
        "city_id": int(user["city_id"]) if user["city_id"] else None,
        "school_id": int(user["school_id"]) if user["school_id"] else None,
        "city_name": city["name"] if city else None,
        "school_name": school["name"] if school else None,
    }


def _student_payload(user) -> dict[str, Any]:
    payload = _basic_payload(user)
    payload.update(orgs.student_education(int(user["id"])))
    payload["ok"] = True
    payload["role"] = user["role"]
    return payload


def _teacher_payload(user) -> dict[str, Any]:
    payload = _basic_payload(user)
    subjects = [row_dict(row) for row in orgs.list_subjects(active_only=True)]
    subject_by_id = {int(subject["id"]): subject for subject in subjects}
    by_class = orgs.teacher_subjects_by_class(int(user["id"]))
    classes = []
    for klass in orgs.classes_of_teacher(int(user["id"])):
        class_id = int(klass["id"])
        class_subjects = [
            subject_by_id[subject_id]
            for subject_id in by_class.get(class_id, [])
            if subject_id in subject_by_id
        ]
        classes.append(
            {
                **row_dict(klass),
                "title": orgs.class_title(klass),
                "subjects": class_subjects,
            }
        )
    payload.update(
        {
            "classes": classes,
            "subjects": subjects,
            "subjects_by_class": {
                str(class_id): subject_ids
                for class_id, subject_ids in by_class.items()
            },
        }
    )
    return payload


@bp.get("/orgs/catalog")
@require_actor
def org_catalog():
    """Города, школы выбранного города, классы выбранной школы и предметы."""
    city_id = request.args.get("city_id", type=int)
    school_id = request.args.get("school_id", type=int)
    cities = [row_dict(row) for row in orgs.list_cities()]
    schools = [
        row_dict(row)
        for row in orgs.list_schools(city_id=city_id)
    ]
    classes = []
    if school_id:
        classes = [
            {
                **row_dict(row),
                "title": orgs.class_title(row),
            }
            for row in orgs.list_classes(school_id=school_id)
        ]
    subjects = [row_dict(row) for row in orgs.list_subjects(active_only=True)]
    return jsonify(
        {
            "ok": True,
            "cities": cities,
            "schools": schools,
            "classes": classes,
            "subjects": subjects,
        }
    )


@bp.get("/profile/education")
@require_actor
def get_education():
    user = current_user()
    if user is None:
        fail(401, "unauthorized", "Требуется вход")
    if user["role"] == auth_service.ROLE_STUDENT:
        return jsonify(_student_payload(user))
    if user["role"] == auth_service.ROLE_TEACHER:
        return jsonify(_teacher_payload(user))
    return jsonify(_basic_payload(user))


@bp.put("/profile/education")
@require_actor
def put_education():
    user = current_user()
    if user is None:
        fail(401, "unauthorized", "Требуется вход")
    role = user["role"]
    if role not in (auth_service.ROLE_STUDENT, auth_service.ROLE_TEACHER):
        fail(403, "forbidden", "Настройка обучения доступна ученику и учителю")

    data = json_body()
    city_id = _int_value(data.get("city_id"), "город")
    school_id = _int_value(data.get("school_id"), "школу")

    city = orgs.get_city(city_id)
    if city is None:
        fail(404, "not_found", "Город не найден")
    school = orgs.get_school(school_id)
    if school is None:
        fail(404, "not_found", "Школа не найдена")
    if int(school["city_id"]) != city_id:
        fail(400, "bad_school", "Школа не относится к выбранному городу")

    if role == auth_service.ROLE_STUDENT:
        class_id = _int_value(data.get("class_id"), "класс")
        klass = orgs.get_class(class_id)
        if klass is None:
            fail(404, "not_found", "Класс не найден")
        if int(klass["school_id"]) != school_id:
            fail(400, "bad_class", "Класс не относится к выбранной школе")
        orgs.set_student_education(int(user["id"]), city_id, school_id, class_id)
        return jsonify(_student_payload(auth_service.get_user(int(user["id"]))))

    # Учитель: несколько классов одной школы и предметы по каждому классу.
    # Старые классы учителя могли относиться к другой школе — их разрешаем
    # сохранить, иначе прежняя привязка потерялась бы при первом сохранении.
    class_ids = _int_list(data.get("class_ids") or data.get("classes"))
    by_class = _subject_map(
        data.get("subjects_by_class") or data.get("subjects") or {}
    )
    already_taught = {
        int(klass["id"]) for klass in orgs.classes_of_teacher(int(user["id"]))
    }
    selected: list[int] = []
    for class_id in class_ids:
        klass = orgs.get_class(class_id)
        if klass is None:
            fail(404, "not_found", f"Класс №{class_id} не найден")
        if int(klass["school_id"]) != school_id and class_id not in already_taught:
            fail(400, "bad_class", "Класс не относится к выбранной школе")
        selected.append(class_id)

    selected_set = set(selected)
    normalized: dict[int, list[int]] = {}
    for class_id, subject_ids in by_class.items():
        if class_id not in selected_set:
            continue
        for subject_id in subject_ids:
            if orgs.get_subject(subject_id) is None:
                fail(404, "not_found", f"Предмет №{subject_id} не найден")
        normalized[class_id] = list(dict.fromkeys(subject_ids))

    orgs.set_teacher_education(int(user["id"]), city_id, school_id)
    orgs.set_teacher_classes(int(user["id"]), selected)
    orgs.set_teacher_subjects(int(user["id"]), normalized)
    return jsonify(_teacher_payload(auth_service.get_user(int(user["id"]))))
