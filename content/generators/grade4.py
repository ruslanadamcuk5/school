"""Генераторы заданий для 4 класса."""
from __future__ import annotations

from .base import gen, plural, rnd, shuffle_options, task


# ------------------------------------------- умножение и деление в столбик
@gen("mult_div_column", "mult")
def mult_column(difficulty: int = 1) -> dict:
    a = rnd(11, 49)
    b = rnd(11, 39)
    return task(
        question=f"Вычисли в столбик: {a} · {b} = ?",
        answer=a * b,
        variables={
            "a": a, "b": b, "product": a * b,
            "b_ones": b % 10, "b_tens": b // 10,
            "a_ones": a % 10, "a_tens": a // 10 % 10,
        },
        hints=[
            "Умножай на единицы: сначала умножь число на цифру единиц второго множителя.",
            f"Начни с {b % 10}: {a} · {b % 10} = {a * (b % 10)}.",
            f"Потом умножь на десятки: {a} · {b // 10} = {a * (b // 10)}. Сложи части.",
        ],
        solution=f"{a} · {b} = {a * b}",
        widget={"type": "column", "top": str(a), "bottom": str(b), "op": "·"},
        difficulty=difficulty,
    )


@gen("mult_div_column", "div")
def div_column(difficulty: int = 1) -> dict:
    b = rnd(11, 25)
    q = rnd(11, 40)
    a = b * q
    return task(
        question=f"Вычисли в столбик: {a} : {b} = ?",
        answer=q,
        variables={"a": a, "b": b, "q": q},
        hints=[
            "Отделяй по одной цифре делимого и подбирай частное.",
            f"Первую цифру делимого дели на {b} и запиши в частное.",
            f"Проверь умножением: {q} · {b} = {a}.",
        ],
        solution=f"{a} : {b} = {q}. Проверка: {q} · {b} = {a}.",
        widget={"type": "column", "top": str(a), "bottom": str(b), "op": ":"},
        difficulty=difficulty,
    )


@gen("mult_div_column", "mult_1000")
def mult_1000(difficulty: int = 1) -> dict:
    a = rnd(12, 999)
    return task(
        question=f"{a} · 1000 = ?",
        answer=a * 1000,
        variables={"a": a},
        hints=[
            "Умножение на 1000 — это приписывание трёх нулей.",
            f"К числу {a} припиши три нуля.",
            "Сколько получилось?",
        ],
        solution=f"{a} · 1000 = {a * 1000}",
        widget={"type": "shift", "number": a, "zeros": 3},
        difficulty=difficulty,
    )


@gen("mult_div_column", "estimate")
def estimate_product(difficulty: int = 1) -> dict:
    a = rnd(23, 98)
    b = rnd(12, 49)
    ra = (a + 5) // 10 * 10
    rb = (b + 5) // 10 * 10
    return task(
        question=f"Округли {a} и {b} до десятков и перемножь полученные числа.",
        answer=ra * rb,
        variables={"a": a, "b": b, "ra": ra, "rb": rb, "estimate": ra * rb},
        hints=[
            "Сначала округли оба числа до десятков.",
            f"{a} ≈ {ra}, {b} ≈ {rb}.",
            f"Теперь перемножь: {ra} · {rb}.",
        ],
        solution=f"{a} ≈ {ra}, {b} ≈ {rb} → {ra} · {rb} = {ra * rb}.",
        difficulty=difficulty,
    )


@gen("mult_div_column", "word")
def mult_word_big(difficulty: int = 1) -> dict:
    a = rnd(12, 40)
    b = rnd(5, 25)
    c = rnd(3, 20)
    total = (a + c) * b
    return task(
        question=(
            f"В {a} коробках по {b} карандашей, ещё в {c} коробках по {b} карандашей. "
            "Сколько всего карандашей?"
        ),
        answer=total,
        variables={"a": a, "b": b, "c": c, "total": total},
        hints=[
            "Сколько всего коробок?",
            f"Коробок: {a} + {c} = {a + c}.",
            f"Потом умножь на {b}: {a + c} · {b}.",
        ],
        solution=f"({a} + {c}) · {b} = {total}.",
        widget={"type": "packages", "boxes": a + c, "per_box": b, "split": c},
        difficulty=difficulty,
    )


# ------------------------------------------------------------ признаки делимости
@gen("divisibility", "by_2_5_10")
def div_by_2_5_10(difficulty: int = 1) -> dict:
    d = rnd(0, 2)
    divisor = [2, 5, 10][d]
    if rnd(0, 1):
        n = divisor * rnd(3, 40) + rnd(0, divisor - 1)
    else:
        n = divisor * rnd(3, 40)
    divisible = n % divisor == 0
    correct = "да" if divisible else "нет"
    choices = shuffle_options(["да", "нет"])
    return task(
        question=f"Делится ли число {n} на {divisor}?",
        answer=correct,
        answer_type="choice",
        choices=choices,
        variables={"n": n, "divisor": divisor},
        hints=[
            f"На {divisor} делятся числа, у которых ...",
            "Проверь последнюю цифру числа.",
            f"Последняя цифра числа {n} — {n % 10}.",
        ],
        solution=f"{n} : {divisor} = {'нацело' if divisible else 'с остатком'}.",
        widget={"type": "place_value", "number": n},
        difficulty=difficulty,
    )


@gen("divisibility", "by_3_9")
def div_by_3_9(difficulty: int = 1) -> dict:
    divisor = rnd(0, 1)
    divisor = [3, 9][divisor]
    n = rnd(101, 999)
    s = sum(int(d) for d in str(n))
    divisible = s % divisor == 0
    correct = "да" if divisible else "нет"
    choices = shuffle_options(["да", "нет"])
    return task(
        question=(
            f"Найди сумму цифр числа {n}. Делится ли {n} на {divisor}?"
        ),
        answer=correct,
        answer_type="choice",
        choices=choices,
        variables={"n": n, "sum": s, "divisor": divisor},
        hints=[
            "На 3 и 9 делится число, у которого сумма цифр делится на это число.",
            f"Сложи цифры: {' + '.join(str(n))} = ?",
            f"Раздели сумму цифр на {divisor}.",
        ],
        solution=f"Сумма цифр {n} равна {s}; {s} : {divisor} = "
        f"{'нацело' if divisible else 'с остатком'}.",
        widget={"type": "place_value", "number": n},
        difficulty=difficulty,
    )


@gen("divisibility", "even_odd")
def even_odd(difficulty: int = 1) -> dict:
    n = rnd(101, 999)
    correct = "чётное" if n % 2 == 0 else "нечётное"
    choices = shuffle_options(["чётное", "нечётное"])
    return task(
        question=f"Чётное или нечётное число {n}?",
        answer=correct,
        answer_type="choice",
        choices=choices,
        variables={"n": n},
        hints=[
            "Чётное число делится на 2 без остатка.",
            "Посмотри на последнюю цифру.",
            f"Последняя цифра числа {n} — {n % 10}.",
        ],
        solution=f"{n} — {correct} число.",
        difficulty=difficulty,
    )


@gen("divisibility", "by_25")
def div_by_25(difficulty: int = 1) -> dict:
    n = rnd(101, 999)
    divisible = n % 25 == 0
    correct = "да" if divisible else "нет"
    choices = shuffle_options(["да", "нет"])
    return task(
        question=f"Делится ли число {n} на 25?",
        answer=correct,
        answer_type="choice",
        choices=choices,
        variables={"n": n},
        hints=[
            "На 25 делятся числа, оканчивающиеся на 00, 25, 50 или 75.",
            f"Последние две цифры числа {n} — {n % 100}.",
            "Сравни с 00, 25, 50, 75.",
        ],
        solution=f"{n} : 25 = {'нацело' if divisible else 'с остатком'}.",
        difficulty=difficulty,
    )


# ------------------------------------------------------------- действия с дробями
@gen("fractions_ops", "add_same")
def add_same(difficulty: int = 1) -> dict:
    den = rnd(4, 12)
    num1 = rnd(1, den - 2)
    num2 = rnd(1, den - num1 - 1)
    total = num1 + num2
    return task(
        question=f"Найди сумму: {num1}/{den} + {num2}/{den} = ? (запиши дробь)",
        answer=f"{total}/{den}",
        answer_type="fraction",
        variables={"num1": num1, "num2": num2, "den": den, "total": total},
        hints=[
            "Знаменатель одинаковый — складываем только числители.",
            f"{num1} + {num2} = {total}.",
            f"Запиши ответ: {total}/{den}.",
        ],
        solution=f"{num1}/{den} + {num2}/{den} = {total}/{den}.",
        widget={"type": "fraction_bar", "den": den, "num": total},
        difficulty=difficulty,
    )


@gen("fractions_ops", "sub_same")
def sub_same(difficulty: int = 1) -> dict:
    den = rnd(4, 12)
    num1 = rnd(3, den)
    num2 = rnd(1, num1 - 1)
    total = num1 - num2
    return task(
        question=f"Найди разность: {num1}/{den} − {num2}/{den} = ? (запиши дробь)",
        answer=f"{total}/{den}",
        answer_type="fraction",
        variables={"num1": num1, "num2": num2, "den": den, "total": total},
        hints=[
            "Знаменатель одинаковый — вычитаем только числители.",
            f"{num1} − {num2} = {total}.",
            f"Запиши ответ: {total}/{den}.",
        ],
        solution=f"{num1}/{den} − {num2}/{den} = {total}/{den}.",
        widget={"type": "fraction_bar", "den": den, "num": total},
        difficulty=difficulty,
    )


@gen("fractions_ops", "compare")
def compare_fractions_4(difficulty: int = 1) -> dict:
    den1, den2 = rnd(3, 12), rnd(3, 12)
    num1 = rnd(1, den1 - 1)
    num2 = rnd(1, den2 - 1)
    v1, v2 = num1 / den1, num2 / den2
    correct = "=" if abs(v1 - v2) < 1e-9 else (">" if v1 > v2 else "<")
    choices = shuffle_options([">", "<", "="])
    return task(
        question=f"Сравни дроби и поставь знак: {num1}/{den1} ... {num2}/{den2}",
        answer=correct,
        answer_type="choice",
        choices=choices,
        variables={"num1": num1, "den1": den1, "num2": num2, "den2": den2},
        hints=[
            "Приведи дроби к общему знаменателю.",
            f"Общий знаменатель: {den1 * den2}.",
            f"{num1}/{den1} = {num1 * den2}/{den1 * den2}, {num2}/{den2} = {num2 * den1}/{den1 * den2}.",
        ],
        solution=f"{num1}/{den1} = {v1:.3f}, {num2}/{den2} = {v2:.3f}.",
        widget={"type": "fraction_bar", "den": den1, "num": num1},
        difficulty=difficulty,
    )


@gen("fractions_ops", "mixed")
def improper_to_mixed(difficulty: int = 1) -> dict:
    den = rnd(2, 9)
    whole = rnd(1, 9)
    rem = rnd(1, den - 1)
    num = whole * den + rem
    return task(
        question=(
            f"Запиши дробь {num}/{den} как смешанное число (например: 2 1/2)."
        ),
        answer=f"{whole} {rem}/{den}",
        answer_type="mixed",
        variables={"num": num, "den": den, "whole": whole, "rem": rem},
        hints=[
            "Раздели числитель на знаменатель.",
            f"{num} : {den} = {whole}, остаток {rem}.",
            f"Смешанное число: {whole} {rem}/{den}.",
        ],
        solution=f"{num}/{den} = {whole} {rem}/{den}.",
        difficulty=difficulty,
    )


@gen("fractions_ops", "of_number")
def fraction_of_number_4(difficulty: int = 1) -> dict:
    den = rnd(3, 9)
    num = rnd(1, den - 1)
    part = rnd(4, 20)
    whole = den * part
    return task(
        question=(
            f"В школьном классе {whole} учеников. {num}/{den} из них занимаются в спортивной секции. "
            "Сколько это учеников?"
        ),
        answer=num * part,
        variables={"num": num, "den": den, "whole": whole, "part": part},
        hints=[
            "Узнай, сколько учеников приходится на одну часть.",
            f"{whole} : {den} = {part}.",
            f"Теперь умножь на {num}.",
        ],
        solution=f"{whole} : {den} = {part}; {part} · {num} = {num * part}.",
        widget={"type": "fraction_bar", "den": den, "num": num},
        difficulty=difficulty,
    )


# ------------------------------------------------------------------ движение
@gen("motion", "speed")
def speed(difficulty: int = 1) -> dict:
    v = rnd(30, 90)
    t = rnd(2, 8)
    s = v * t
    return task(
        question=f"Автобус ехал со скоростью {v} км/ч {t} ч. Какой путь он проехал?",
        answer=s,
        variables={"v": v, "t": t, "s": s},
        hints=[
            "Расстояние = скорость · время.",
            f"{v} · {t} = ?",
            "Проверь единицы: км/ч · ч = км.",
        ],
        solution=f"s = {v} · {t} = {s} км.",
        widget={"type": "path", "v": v, "t": t},
        difficulty=difficulty,
    )


@gen("motion", "find_speed")
def find_speed(difficulty: int = 1) -> dict:
    v = rnd(30, 90)
    t = rnd(2, 8)
    s = v * t
    return task(
        question=f"Автобус проехал {s} км за {t} ч. С какой скоростью он ехал?",
        answer=v,
        variables={"v": v, "t": t, "s": s},
        hints=[
            "Скорость = расстояние : время.",
            f"{s} : {t} = ?",
            "Проверь: скорость · время = расстояние.",
        ],
        solution=f"v = {s} : {t} = {v} км/ч.",
        widget={"type": "path", "t": t, "s": s},
        difficulty=difficulty,
    )


@gen("motion", "find_time")
def find_time(difficulty: int = 1) -> dict:
    v = rnd(30, 90)
    t = rnd(2, 8)
    s = v * t
    return task(
        question=f"Поезд проехал {s} км со скоростью {v} км/ч. Сколько времени он был в пути?",
        answer=t,
        variables={"v": v, "t": t, "s": s},
        hints=[
            "Время = расстояние : скорость.",
            f"{s} : {v} = ?",
            "Проверь: скорость · время = расстояние.",
        ],
        solution=f"t = {s} : {v} = {t} ч.",
        widget={"type": "path", "v": v, "s": s},
        difficulty=difficulty,
    )


@gen("motion", "meet")
def meet_motion(difficulty: int = 1) -> dict:
    v1 = rnd(30, 80)
    v2 = rnd(30, 80)
    t = rnd(2, 6)
    s = (v1 + v2) * t
    return task(
        question=(
            f"Два поезда выехали навстречу друг другу одновременно. Скорость первого — {v1} км/ч, "
            f"второго — {v2} км/ч. Они ехали {t} ч. Какое расстояние между городами?"
        ),
        answer=s,
        variables={"v1": v1, "v2": v2, "t": t, "s": s, "v_sum": v1 + v2},
        hints=[
            "За каждое время они вместе проезжают сумму скоростей.",
            f"Вместе они движутся со скоростью {v1} + {v2} = {v1 + v2} км/ч.",
            f"Потом умножь на {t} ч.",
        ],
        solution=f"s = ({v1} + {v2}) · {t} = {s} км.",
        widget={"type": "path", "v": v1, "t": t, "v2": v2},
        difficulty=difficulty,
    )


@gen("motion", "two_parts")
def motion_two_parts(difficulty: int = 1) -> dict:
    v1 = rnd(8, 20)
    t1 = rnd(2, 5)
    v2 = rnd(15, 30)
    t2 = rnd(2, 5)
    s = v1 * t1 + v2 * t2
    return task(
        question=(
            f"Велосипедист ехал {t1} ч со скоростью {v1} км/ч, а потом ещё {t2} ч "
            f"со скоростью {v2} км/ч. Какой путь он проехал?"
        ),
        answer=s,
        variables={"v1": v1, "t1": t1, "v2": v2, "t2": t2, "s": s},
        hints=[
            "Найди путь за каждую часть отдельно.",
            f"Сначала: {v1} · {t1} = {v1 * t1} км.",
            f"Потом: {v2} · {t2} = {v2 * t2} км. Сложи результаты.",
        ],
        solution=f"{v1 * t1} + {v2 * t2} = {s} км.",
        widget={"type": "path", "v": v1, "t": t1},
        difficulty=difficulty,
    )


# ------------------------------------------------------------------- площади
@gen("area_units", "convert")
def area_convert(difficulty: int = 1) -> dict:
    a = rnd(2, 40)
    return task(
        question=f"Сколько квадратных сантиметров в {a} м²? Впиши только число.",
        answer=a * 10000,
        variables={"a": a},
        hints=[
            "В 1 м² — 100 · 100 = 10 000 см².",
            f"{a} м² = {a} · 10 000 см².",
            "Посчитай произведение.",
        ],
        solution=f"{a} · 10 000 = {a * 10000} см².",
        widget={"type": "area_grid", "n": a},
        difficulty=difficulty,
    )


@gen("area_units", "hectare")
def hectare(difficulty: int = 1) -> dict:
    a = rnd(1, 20)
    return task(
        question=f"Сколько квадратных метров в {a} гектаре? Впиши только число.",
        answer=a * 10000,
        variables={"a": a},
        hints=[
            "1 гектар — это 100 м · 100 м.",
            "1 га = 10 000 м².",
            f"{a} · 10 000 = ?",
        ],
        solution=f"{a} га = {a * 10000} м².",
        difficulty=difficulty,
    )


@gen("area_units", "composite")
def composite_area(difficulty: int = 1) -> dict:
    a = rnd(4, 15)
    b = rnd(3, 12)
    c = rnd(3, 12)
    s = a * b + c * c
    return task(
        question=(
            f"Фигура состоит из прямоугольника {a} см × {b} см и квадрата {c} см × {c} см. "
            "Найди площадь всей фигуры."
        ),
        answer=s,
        variables={"a": a, "b": b, "c": c, "s": s, "ab": a * b, "cc": c * c},
        hints=[
            "Раздели фигуру на прямоугольник и квадрат.",
            f"Площадь прямоугольника: {a} · {b} = {a * b}.",
            f"Площадь квадрата: {c} · {c} = {c * c}. Сложи.",
        ],
        solution=f"{a * b} + {c * c} = {s} см².",
        widget={"type": "shapes", "kind": "composite", "a": a, "b": b, "c": c},
        difficulty=difficulty,
    )


@gen("area_units", "square")
def square_area(difficulty: int = 1) -> dict:
    a = rnd(3, 30)
    return task(
        question=f"Квадрат со стороной {a} см. Найди его площадь.",
        answer=a * a,
        variables={"a": a},
        hints=[
            "У квадрата все стороны равны.",
            "Площадь = сторона · сторона.",
            f"{a} · {a} = ?",
        ],
        solution=f"S = {a} · {a} = {a * a} см².",
        widget={"type": "shapes", "kind": "square", "a": a},
        difficulty=difficulty,
    )


# --------------------------------------------------------------------- время
@gen("time_calc", "clock")
def clock_read(difficulty: int = 1) -> dict:
    h = rnd(1, 12)
    m = rnd(0, 59)
    return task(
        question="Какое время показывают часы? Ответь в формате ЧЧ:ММ (например, 3:05).",
        answer=f"{h}:{m:02d}",
        answer_type="time",
        variables={"h": h, "m": m},
        hints=[
            "Посмотри на короткую стрелку — это часы, на длинную — минуты.",
            f"Часов: {h}.",
            f"Минут: {m}. Запиши как {h}:{m:02d}.",
        ],
        solution=f"На часах {h}:{m:02d}.",
        widget={"type": "clock", "h": h, "m": m},
        difficulty=difficulty,
    )


@gen("time_calc", "minutes")
def minutes_between(difficulty: int = 1) -> dict:
    h = rnd(6, 18)
    m = rnd(0, 50)
    add = rnd(10, 90)
    total = (h * 60 + m + add) % (24 * 60)
    return task(
        question=(
            f"Сейчас {h}:{m:02d}. Через сколько минут будет {total // 60}:{total % 60:02d}? "
            "Впиши только число минут."
        ),
        answer=add,
        variables={"h": h, "m": m, "add": add},
        hints=[
            "Переведи время в минуты.",
            f"{h}:{m:02d} — это {h * 60 + m} минут.",
            f"Вычти из {total // 60 * 60 + total % 60}.",
        ],
        solution=f"{h * 60 + m} + {add} = {h * 60 + m + add} минут.",
        widget={"type": "clock", "h": h, "m": m},
        difficulty=difficulty,
    )


@gen("time_calc", "day")
def day_units(difficulty: int = 1) -> dict:
    return task(
        question="Сколько часов в сутках? Впиши только число.",
        answer=24,
        variables={},
        hints=[
            "В сутках есть день и ночь.",
            "День — это 12 часов, ночь — тоже 12 часов.",
            "12 + 12 = ?",
        ],
        solution="В сутках 24 часа.",
        widget={"type": "clock", "h": 12, "m": 0},
        difficulty=difficulty,
    )


@gen("time_calc", "month")
def month_days(difficulty: int = 1) -> dict:
    months = [
        ("января", 31), ("февраля", 28), ("марта", 31), ("апреля", 30),
        ("мая", 31), ("июня", 30), ("июля", 31), ("августа", 31),
        ("сентября", 30), ("октября", 31), ("ноября", 30), ("декабря", 31),
    ]
    name, days = months[rnd(0, 11)]
    return task(
        question=f"Сколько дней в {name}? Впиши только число.",
        answer=days,
        variables={"month": name, "days": days, "day_hours": 24, "week_days": 7},
        hints=[
            "Вспомни календарь: в месяцах 30 или 31 день.",
            "В феврале 28 дней (в високосный год 29).",
            f"В {name} — {'31' if days == 31 else '30'} дней.",
        ],
        solution=f"В {name} {days} {plural(days, 'день', 'дня', 'дней')}.",
        difficulty=difficulty,
    )
