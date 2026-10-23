"""Генераторы заданий для 3 класса."""
from __future__ import annotations

from .base import gen, plural, rnd, shuffle_options, task


# ---------------------------------------------------------------- числа до 1000
@gen("numbers_1000", "place_value")
def place_value(difficulty: int = 1) -> dict:
    number = rnd(101, 999)
    h, rem = divmod(number, 100)
    t, o = divmod(rem, 10)
    return task(
        question=f"Запиши число: {h} сотен, {t} десятков и {o} единиц.",
        answer=number,
        variables={"number": number, "hundreds": h, "tens": t, "ones": o},
        hints=[
            "Вспомни, сколько единиц в сотне и в десятке: 1 сотня = 100, 1 десяток = 10.",
            f"Начни с сотен: {h} · 100 = {h * 100}.",
            f"Складываем: {h * 100} + {t * 10} + {o} = ?",
        ],
        solution=f"{h} · 100 + {t} · 10 + {o} = {number}",
        difficulty=difficulty,
    )


@gen("numbers_1000", "compare")
def compare_numbers(difficulty: int = 1) -> dict:
    a = rnd(100, 999)
    b = rnd(100, 999)
    while a == b:
        b = rnd(100, 999)
    correct = f"{a}" if a > b else f"{b}"
    choices = shuffle_options([f"{a}", f"{b}", "Они равны"])
    return task(
        question=f"Что больше: {a} или {b}?",
        answer=correct,
        answer_type="choice",
        choices=choices,
        variables={"a": a, "b": b},
        hints=[
            "Сравнивай по разрядам: сначала сотни, потом десятки, потом единицы.",
            f"У числа {a} сотен — {a // 100}, а у числа {b} — {b // 100}.",
            "Если сотни равны, сравни десятки, а потом единицы.",
        ],
        solution=f"{correct} больше, потому что {a} и {b} сравниваются по разрядам.",
        widget={"type": "place_value", "number": a},
        difficulty=difficulty,
    )


@gen("numbers_1000", "order")
def order_numbers(difficulty: int = 1) -> dict:
    base = rnd(1, 9) * 100
    nums = sorted({base + rnd(0, 99) for _ in range(4)})
    while len(nums) < 4:
        nums.append(rnd(100, 999))
        nums = sorted(set(nums))
    nums = nums[:4]
    smallest = str(nums[0])
    choices = shuffle_options([str(n) for n in nums])
    return task(
        question="Расположи числа по возрастанию. Какое число будет первым (самым маленьким)?",
        answer=smallest,
        answer_type="choice",
        choices=choices,
        variables={"numbers": nums},
        hints=[
            "Сначала сравнивай сотни: у кого сотен больше, то число больше.",
            "Выпиши числа по порядку возрастания и посмотри на первое.",
            f"Наименьшее из {', '.join(map(str, nums))} — это {smallest}.",
        ],
        solution=f"По возрастанию: {', '.join(map(str, nums))}. Самое маленькое — {smallest}.",
        widget={"type": "number_line", "from": min(nums), "to": max(nums), "marks": nums},
        difficulty=difficulty,
    )


@gen("numbers_1000", "round_hundred")
def round_hundred(difficulty: int = 1) -> dict:
    number = rnd(101, 999)
    rounded = ((number + 50) // 100) * 100
    return task(
        question=f"Округли число {number} до сотен.",
        answer=rounded,
        variables={"number": number, "rounded": rounded},
        hints=[
            "Посмотри на цифру десятков.",
            "Если десятки ≥ 5, сотни увеличиваем на 1 и пишем 00.",
            f"Десятков у {number} — {number // 10 % 10}.",
        ],
        solution=f"{number} ≈ {rounded} (десятков {number // 10 % 10}).",
        widget={"type": "place_value", "number": number},
        difficulty=difficulty,
    )


@gen("numbers_1000", "digit_in_place")
def digit_in_place(difficulty: int = 1) -> dict:
    number = rnd(101, 999)
    places = [("сотнях", number // 100), ("десятках", number // 10 % 10), ("единицах", number % 10)]
    name, value = places[rnd(0, 2)]
    return task(
        question=f"Какая цифра стоит в разряде {name} числа {number}?",
        answer=value,
        variables={"number": number, "place": name, "value": value},
        hints=[
            "Запиши число в разрядные слагаемые.",
            f"{number} = ? · 100 + ? · 10 + ?",
            "Найди нужное слагаемое.",
        ],
        solution=f"{number} = {number // 100} · 100 + {number // 10 % 10} · 10 + {number % 10}.",
        widget={"type": "place_value", "number": number, "focus": name},
        difficulty=difficulty,
    )


# ------------------------------------------------- сложение и вычитание 1000
@gen("add_sub_1000", "add_column")
def add_column(difficulty: int = 1) -> dict:
    a = rnd(105, 899)
    b = rnd(105, 899)
    return task(
        question=f"Вычисли в столбик: {a} + {b}",
        answer=a + b,
        variables={
            "a": a, "b": b, "sum": a + b,
            "a_ones": a % 10, "b_ones": b % 10,
            "a_tens": a // 10 % 10, "b_tens": b // 10 % 10,
        },
        hints=[
            "Выпиши числа друг под другом: единицы под единицами, десятки под десятками.",
            "Складывай справа налево, начиная с единиц. Если получилось больше 9 — перенеси 1 десяток.",
            f"Сложи отдельно единицы: {a % 10} + {b % 10}.",
        ],
        solution=f"{a} + {b} = {a + b}",
        widget={
            "type": "column",
            "top": str(a),
            "bottom": str(b),
            "op": "+",
        },
        difficulty=difficulty,
    )


@gen("add_sub_1000", "sub_column")
def sub_column(difficulty: int = 1) -> dict:
    a = rnd(300, 999)
    b = rnd(105, a - 1)
    return task(
        question=f"Вычисли в столбик: {a} − {b}",
        answer=a - b,
        variables={"a": a, "b": b, "diff": a - b},
        hints=[
            "Выпиши числа друг под другом и вычитай справа налево.",
            "Если единиц не хватает — займи 1 десяток (это «займ»).",
            f"Сначала единицы: {a % 10} − {b % 10}.",
        ],
        solution=f"{a} − {b} = {a - b}. Проверка: {a - b} + {b} = {a}.",
        widget={"type": "column", "top": str(a), "bottom": str(b), "op": "−"},
        difficulty=difficulty,
    )


@gen("add_sub_1000", "missing_term")
def missing_term(difficulty: int = 1) -> dict:
    a = rnd(120, 700)
    c = a + rnd(30, 299)
    return task(
        question=f"Заполни пропуск: {a} + ☐ = {c}",
        answer=c - a,
        variables={"a": a, "c": c},
        hints=[
            "Чтобы найти слагаемое, из суммы вычти известное слагаемое.",
            f"Посчитай: {c} − {a} = ?",
            "Действие, обратное сложению, — это вычитание.",
        ],
        solution=f"{c} − {a} = {c - a}, значит {a} + {c - a} = {c}.",
        widget={"type": "column", "top": str(a), "bottom": "?", "op": "+", "result": str(c)},
        difficulty=difficulty,
    )


@gen("add_sub_1000", "check")
def check_subtraction(difficulty: int = 1) -> dict:
    a = rnd(400, 999)
    b = rnd(120, a - 1)
    c = a - b
    return task(
        question=f"Реши пример {a} − {b} = {c}. Для проверки сложи {c} и {b}. Сколько получится?",
        answer=a,
        variables={"a": a, "b": b, "c": c},
        hints=[
            "Проверяют вычитание сложением.",
            f"Посчитай {c} + {b}.",
            "Ответ должен совпасть с уменьшаемым.",
        ],
        solution=f"{c} + {b} = {a} — пример верен.",
        widget={"type": "column", "top": str(c), "bottom": str(b), "op": "+"},
        difficulty=difficulty,
    )


@gen("add_sub_1000", "estimate_sum")
def estimate_sum(difficulty: int = 1) -> dict:
    a = rnd(105, 899)
    b = rnd(105, 899)
    ra = (a + 5) // 10 * 10
    rb = (b + 5) // 10 * 10
    return task(
        question=f"Округли {a} и {b} до десятков и сложи полученные числа.",
        answer=ra + rb,
        variables={"a": a, "b": b, "ra": ra, "rb": rb, "estimate": ra + rb},
        hints=[
            "Округли каждое число до десятков.",
            f"{a} ≈ {ra}, {b} ≈ {rb}.",
            "Теперь сложи округлённые числа.",
        ],
        solution=f"{a} ≈ {ra}, {b} ≈ {rb}, значит сумма ≈ {ra + rb}.",
        difficulty=difficulty,
    )


# ------------------------------------------------- табличное умножение/деление
@gen("mult_div_table", "mult")
def mult(difficulty: int = 1) -> dict:
    a = rnd(2, 9)
    b = rnd(2, 9)
    return task(
        question=f"{a} · {b} = ?",
        answer=a * b,
        variables={"a": a, "b": b, "product": a * b},
        hints=[
            "Вспомни таблицу умножения.",
            f"Считай по {b}: {b}, {b * 2}, {b * 3} ...",
            f"Нужно взять {a} {plural(a, 'раз', 'раза', 'раз')}.",
        ],
        solution=f"{a} · {b} = {a * b}",
        widget={"type": "array", "rows": a, "cols": b},
        difficulty=difficulty,
    )


@gen("mult_div_table", "div")
def div(difficulty: int = 1) -> dict:
    a = rnd(2, 9)
    b = rnd(2, 9)
    product = a * b
    return task(
        question=f"{product} : {a} = ?",
        answer=b,
        variables={"a": a, "b": b, "product": product},
        hints=[
            "Раздели на равные части: найди, сколько будет в одной части.",
            f"Проверь умножением: b · {a} = {product}.",
            "Подбери число, которое при умножении на " + str(a) + " даёт " + str(product) + ".",
        ],
        solution=f"{product} : {a} = {b}, потому что {b} · {a} = {product}.",
        difficulty=difficulty,
    )


@gen("mult_div_table", "word")
def mult_word(difficulty: int = 1) -> dict:
    a = rnd(3, 9)
    b = rnd(2, 9)
    thing = rnd(0, 3)
    things = ["конфет", "карандашей", "мячей", "книг"][thing]
    return task(
        question=f"В {a} коробках лежит по {b} {things}. Сколько всего {things} во всех коробках?",
        answer=a * b,
        variables={"a": a, "b": b, "product": a * b},
        hints=[
            "Сколько всего одинаковых групп?",
            f"Коробок {a}, в каждой {b}. Нужно умножить.",
            f"{a} · {b} = ?",
        ],
        solution=f"{a} коробок по {b} — это {a} · {b} = {a * b} {things}.",
        widget={"type": "groups", "rows": a, "cols": b, "emoji": "🍬"},
        difficulty=difficulty,
    )


@gen("mult_div_table", "replace")
def replace_mult(difficulty: int = 1) -> dict:
    a = rnd(3, 9)
    b = rnd(2, 9)
    return task(
        question=f"Замени умножение сложением и вычисли: {a} · {b} = ?",
        answer=a * b,
        variables={"a": a, "b": b, "product": a * b},
        hints=[
            f"Умножение на {b} — это {b} раз взять число {a}.",
            f"Запиши: {' + '.join([str(a)] * b)}.",
            "Посчитай сумму.",
        ],
        solution=f"{' + '.join([str(a)] * b)} = {a * b}.",
        widget={"type": "groups", "rows": b, "cols": 1, "emoji": "🔵"},
        difficulty=difficulty,
    )


@gen("mult_div_table", "commutative")
def commutative(difficulty: int = 1) -> dict:
    a = rnd(2, 9)
    b = rnd(2, 9)
    return task(
        question=f"Известно, что {a} · {b} = {a * b}. Чему равно {b} · {a}?",
        answer=a * b,
        variables={"a": a, "b": b, "product": a * b},
        hints=[
            "От перестановки множителей произведение не меняется.",
            f"{a} · {b} = {b} · {a}.",
            "Ответ такой же, как в известном примере.",
        ],
        solution=f"{b} · {a} = {a * b} — переместительное свойство умножения.",
        difficulty=difficulty,
    )


# ----------------------------------------------------- умножение на 10, 100
@gen("mult_div_100", "mult")
def mult_by_100(difficulty: int = 1) -> dict:
    a = rnd(2, 99)
    k = rnd(2, 9) * 10
    return task(
        question=f"{a} · {k} = ?",
        answer=a * k,
        variables={"a": a, "k": k, "product": a * k},
        hints=[
            "Умножение на 10, 100, 1000 — это приписывание нулей справа.",
            f"Допиши к {a} столько нулей, сколько их у множителя {k}.",
            f"{a} · {k} = {a} и столько нулей.",
        ],
        solution=f"{a} · {k} = {a * k}",
        widget={"type": "shift", "number": a, "zeros": len(str(k)) - 1},
        difficulty=difficulty,
    )


@gen("mult_div_100", "div")
def div_by_100(difficulty: int = 1) -> dict:
    a = rnd(2, 99) * 10
    k = rnd(2, 9) * 10
    return task(
        question=f"{a} : {k} = ?",
        answer=a // k,
        variables={"a": a, "k": k, "quotient": a // k},
        hints=[
            "Деление на 10, 100 — это отбрасывание нулей справа (если делится нацело).",
            f"Убери столько нулей справа, сколько их у {k}.",
            f"{a} : {k} = ?",
        ],
        solution=f"{a} : {k} = {a // k}",
        widget={"type": "shift", "number": a, "zeros": -(len(str(k)) - 1)},
        difficulty=difficulty,
    )


@gen("mult_div_100", "increase")
def increase_times(difficulty: int = 1) -> dict:
    a = rnd(12, 99)
    k = rnd(2, 9)
    return task(
        question=f"Число {a} увеличили в {k} раз. Чему равно новое число?",
        answer=a * k,
        variables={"a": a, "k": k, "product": a * k},
        hints=[
            "«Увеличили в несколько раз» — значит умножили.",
            f"Увеличили в {k} раз — это {k} умножений.",
            f"{a} · {k} = ?",
        ],
        solution=f"{a} · {k} = {a * k}.",
        difficulty=difficulty,
    )


# ------------------------------------------------------------ деление с остатком
@gen("remainder", "divide")
def divide_remainder(difficulty: int = 1) -> dict:
    b = rnd(3, 9)
    q = rnd(2, 9)
    r = rnd(1, b - 1)
    a = b * q + r
    return task(
        question=f"Какой остаток получится при делении {a} на {b}?",
        answer=r,
        variables={"a": a, "b": b, "q": q, "r": r, "product": b * q},
        hints=[
            "Найди самое большое число, которое делится на {b} без остатка.".format(b=b),
            f"{b} · {q} = {b * q}, а {a} больше на {a - b * q}.",
            "Остаток — это то, что осталось после деления.",
        ],
        solution=f"{a} : {b} = {q} (остаток {r}), потому что {b} · {q} + {r} = {a}.",
        widget={"type": "groups", "rows": q, "cols": b, "emoji": "🟢",
                "extra": r, "extra_emoji": "🔴", "hide_extra_label": True, "hide_count": True},
        difficulty=difficulty,
    )


@gen("remainder", "max_divisible")
def max_divisible(difficulty: int = 1) -> dict:
    b = rnd(3, 9)
    q = rnd(3, 12)
    a = b * q + rnd(1, b - 1)
    return task(
        question=f"Какое наибольшее число, не большее {a}, делится на {b} без остатка?",
        answer=b * q,
        variables={"a": a, "b": b, "q": q},
        hints=[
            "Ищи число, которое делится на {b} без остатка.".format(b=b),
            f"Попробуй {b} · {q} и сравни с {a}.",
            "Оно должно быть ≤ данного числа.",
        ],
        solution=f"{b} · {q} = {b * q} — наибольшее такое число.",
        difficulty=difficulty,
    )


@gen("remainder", "word")
def remainder_word(difficulty: int = 1) -> dict:
    b = rnd(3, 9)
    q = rnd(3, 9)
    r = rnd(1, b - 1)
    a = b * q + r
    return task(
        question=f"{a} конфет разложили по {b} в коробки. Сколько полных коробок получится?",
        answer=q,
        variables={"a": a, "b": b, "q": q, "r": r},
        hints=[
            "Раздели нацело и посмотри на остаток.",
            f"Если бы коробок было больше, конфет не хватило бы. {b} · {q} = {b * q}.",
            f"Останется {r} {plural(r, 'конфета', 'конфеты', 'конфет')}.",
        ],
        solution=f"{a} : {b} = {q} (остаток {r}).",
        difficulty=difficulty,
    )


# ------------------------------------------------------ порядок действий
@gen("expressions", "order")
def order_of_operations(difficulty: int = 1) -> dict:
    a, b, c = rnd(2, 9), rnd(2, 9), rnd(2, 9)
    first = a + b * c
    second = (a + b) * c
    use_brackets = difficulty >= 2
    if use_brackets:
        question = f"Вычисли: ({a} + {b}) · {c} = ?"
        answer = second
        solution = f"Сначала в скобках: {a} + {b} = {a + b}. Потом {a + b} · {c} = {second}."
        hints = [
            "Сначала вычисляй то, что в скобках.",
            f"{a} + {b} = {a + b}.",
            f"Потом умножь: {a + b} · {c}.",
        ]
    else:
        question = f"Вычисли: {a} + {b} · {c} = ?"
        answer = first
        solution = f"Сначала умножение: {b} · {c} = {b * c}. Потом сложение: {a} + {b * c} = {first}."
        hints = [
            "Сначала выполняй умножение, потом сложение.",
            f"{b} · {c} = {b * c}.",
            f"Теперь сложи: {a} + {b * c}.",
        ]
    return task(
        question=question,
        answer=answer,
        variables={"a": a, "b": b, "c": c, "result": answer},
        hints=hints,
        solution=solution,
        difficulty=difficulty,
    )


@gen("expressions", "brackets")
def brackets(difficulty: int = 1) -> dict:
    a, b, c = rnd(2, 8), rnd(2, 9), rnd(2, 9)
    correct = f"({a} + {b}) · {c}"
    wrong = f"{a} + ({b} · {c})"
    value = (a + b) * c
    choices = shuffle_options([correct, wrong])
    return task(
        question=f"Расставь скобки так, чтобы получилось {value}: {a} + {b} · {c} = {value}",
        answer=correct,
        answer_type="choice",
        choices=choices,
        variables={"a": a, "b": b, "c": c, "value": value},
        hints=[
            "Попробуй по очереди оба варианта и посчитай.",
            f"({a} + {b}) · {c} = ({a + b}) · {c} = {value}.",
            "Сравни с вариантом, где скобки вокруг умножения.",
        ],
        solution=f"Правильно: {correct}, потому что {a} + {b} = {a + b}, а {a + b} · {c} = {value}.",
        difficulty=difficulty,
    )


@gen("expressions", "compare")
def compare_expressions(difficulty: int = 1) -> dict:
    a = rnd(3, 9)
    b = rnd(3, 9)
    c = rnd(3, 9)
    left, right = a * b, a * c
    correct = "=" if b == c else (">" if left > right else "<")
    choices = shuffle_options([">", "<", "="])
    return task(
        question=f"Сравни, что больше: {a} · {b} или {a} · {c}?",
        answer=correct,
        answer_type="choice",
        choices=choices,
        variables={"a": a, "b": b, "c": c},
        hints=[
            "В первом множителе одинаково — сравни вторые.",
            f"{a} · {b} = {left}, {a} · {c} = {right}.",
            "Что больше: " + str(left) + " или " + str(right) + "?",
        ],
        solution=f"{a} · {b} = {left}, {a} · {c} = {right}. Значит {correct}.",
        difficulty=difficulty,
    )


# ------------------------------------------------------------------ уравнения
@gen("equations", "unknown_addend")
def unknown_addend(difficulty: int = 1) -> dict:
    a = rnd(20, 300)
    x = rnd(20, 400)
    return task(
        question=f"Реши уравнение: {a} + x = {a + x}",
        answer=x,
        variables={"a": a, "x": x, "sum": a + x},
        hints=[
            "Чтобы найти слагаемое, из суммы вычти известное слагаемое.",
            f"{a + x} − {a} = ?",
            "Сумма минус слагаемое = другое слагаемое.",
        ],
        solution=f"x = {a + x} − {a} = {x}. Проверка: {a} + {x} = {a + x}.",
        widget={"type": "balance", "left": a, "right": a + x, "unknown": "x"},
        difficulty=difficulty,
    )


@gen("equations", "unknown_subtrahend")
def unknown_subtrahend(difficulty: int = 1) -> dict:
    a = rnd(200, 900)
    x = rnd(20, a - 10)
    return task(
        question=f"Реши уравнение: {a} − x = {a - x}",
        answer=x,
        variables={"a": a, "x": x, "diff": a - x},
        hints=[
            "Чтобы найти вычитаемое, из уменьшаемого вычти разность.",
            f"{a} − {a - x} = ?",
            "Уменьшаемое минус разность = вычитаемое.",
        ],
        solution=f"x = {a} − {a - x} = {x}. Проверка: {a} − {x} = {a - x}.",
        widget={"type": "balance", "left": a, "right": a - x, "unknown": "x"},
        difficulty=difficulty,
    )


@gen("equations", "unknown_minuend")
def unknown_minuend(difficulty: int = 1) -> dict:
    x = rnd(200, 900)
    b = rnd(20, 300)
    return task(
        question=f"Реши уравнение: x − {b} = {x - b}",
        answer=x,
        variables={"b": b, "x": x, "diff": x - b},
        hints=[
            "Чтобы найти уменьшаемое, к разности прибавь вычитаемое.",
            f"{x - b} + {b} = ?",
            "Разность + вычитаемое = уменьшаемое.",
        ],
        solution=f"x = {x - b} + {b} = {x}. Проверка: {x} − {b} = {x - b}.",
        widget={"type": "balance", "left": x, "right": x - b, "unknown": "x"},
        difficulty=difficulty,
    )


@gen("equations", "unknown_factor")
def unknown_factor(difficulty: int = 1) -> dict:
    a = rnd(2, 9)
    x = rnd(2, 9)
    return task(
        question=f"Реши уравнение: {a} · x = {a * x}",
        answer=x,
        variables={"a": a, "x": x, "product": a * x},
        hints=[
            "Чтобы найти множитель, произведение раздели на известный множитель.",
            f"{a * x} : {a} = ?",
            "Произведение : множитель = другой множитель.",
        ],
        solution=f"x = {a * x} : {a} = {x}. Проверка: {a} · {x} = {a * x}.",
        widget={"type": "balance", "left": a * x, "right": a, "unknown": "x"},
        difficulty=difficulty,
    )


@gen("equations", "unknown_divisor")
def unknown_divisor(difficulty: int = 1) -> dict:
    b = rnd(2, 9)
    x = rnd(2, 9)
    return task(
        question=f"Реши уравнение: {b * x} : x = {b}",
        answer=x,
        variables={"b": b, "x": x},
        hints=[
            "Чтобы найти делитель, делимое раздели на частное.",
            f"{b * x} : {b} = ?",
            "Делимое : частное = делитель.",
        ],
        solution=f"x = {b * x} : {b} = {x}. Проверка: {b * x} : {x} = {b}.",
        difficulty=difficulty,
    )


# ---------------------------------------------------------------------- дроби
@gen("fractions", "from_parts")
def fraction_from_parts(difficulty: int = 1) -> dict:
    den = rnd(2, 12)
    num = rnd(1, den - 1)
    return task(
        question=f"Целое разделили на {den} равных частей и взяли {num}. Запиши эту дробь.",
        answer=f"{num}/{den}",
        answer_type="fraction",
        variables={"num": num, "den": den},
        hints=[
            "Знаменатель — на сколько частей разделили целое.",
            f"Знаменатель {den}, числитель {num}.",
            f"Дробь записывается так: {num}/{den}.",
        ],
        solution=f"Дробь {num}/{den}.",
        widget={"type": "fraction_circle", "den": den, "num": num},
        difficulty=difficulty,
    )


@gen("fractions", "of_number")
def fraction_of_number(difficulty: int = 1) -> dict:
    den = rnd(2, 8)
    num = rnd(1, den - 1)
    part = rnd(2, 12)
    whole = den * part
    return task(
        question=f"Сколько будет {num}/{den} от числа {whole}?",
        answer=num * part,
        variables={"num": num, "den": den, "whole": whole, "part": part, "result": num * part},
        hints=[
            "Сначала узнай, сколько приходится на одну часть.",
            f"Раздели {whole} на {den}: {whole} : {den} = {part}.",
            f"Потом возьми {num} частей: {part} · {num}.",
        ],
        solution=f"{whole} : {den} = {part}; {part} · {num} = {num * part}.",
        widget={"type": "fraction_bar", "den": den, "num": num},
        difficulty=difficulty,
    )


@gen("fractions", "compare")
def compare_fractions(difficulty: int = 1) -> dict:
    den1, den2 = rnd(2, 9), rnd(2, 9)
    num1, num2 = rnd(1, den1 - 1), rnd(1, den2 - 1)
    v1, v2 = num1 / den1, num2 / den2
    correct = "=" if abs(v1 - v2) < 1e-9 else (">" if v1 > v2 else "<")
    choices = shuffle_options([">", "<", "="])
    return task(
        question=f"Сравни дроби: {num1}/{den1} и {num2}/{den2}. Поставь знак >, < или =.",
        answer=correct,
        answer_type="choice",
        choices=choices,
        variables={
            "num1": num1, "den1": den1, "num2": num2, "den2": den2,
            "num": num1, "den": den1,
        },
        hints=[
            "Сравнивай дроби с одинаковым знаменателем: больше та, у которой больше числитель.",
            "С одинаковым числителем: больше та, у которой меньше знаменатель.",
            "Попробуй привести к общему знаменателю.",
        ],
        solution=f"{num1}/{den1} = {v1:.2f}, {num2}/{den2} = {v2:.2f}.",
        widget={"type": "fraction_bar", "den": den1, "num": num1},
        difficulty=difficulty,
    )


@gen("fractions", "equal")
def equal_fraction(difficulty: int = 1) -> dict:
    den = rnd(2, 6)
    num = rnd(1, den - 1)
    k = rnd(2, 4)
    correct = f"{num * k}/{den * k}"
    wrong_options = [f"{num}/{den * k}", f"{num * k}/{den}", f"{num + 1}/{den * k}"]
    choices = shuffle_options([correct] + wrong_options[:2])
    return task(
        question=f"Какая дробь равна {num}/{den}?",
        answer=correct,
        answer_type="choice",
        choices=choices,
        variables={"num": num, "den": den},
        hints=[
            "Увеличивай числитель и знаменатель в одинаковое число раз.",
            f"Попробуй умножить и числитель, и знаменатель на {k}.",
            f"{num} · {k} = {num * k}, {den} · {k} = {den * k}.",
        ],
        solution=f"{num}/{den} = {num * k}/{den * k}.",
        widget={"type": "fraction_circle", "den": den, "num": num},
        difficulty=difficulty,
    )


@gen("fractions", "sum_same")
def sum_same_denominator(difficulty: int = 1) -> dict:
    den = rnd(3, 12)
    num1 = rnd(1, den - 2)
    num2 = rnd(1, den - num1 - 1)
    total = num1 + num2
    return task(
        question=f"Сложи дроби с одинаковым знаменателем: {num1}/{den} + {num2}/{den} = ?",
        answer=f"{total}/{den}",
        answer_type="fraction",
        variables={"num1": num1, "num2": num2, "den": den, "total": total},
        hints=[
            "Знаменатель не меняется — складываем только числители.",
            f"{num1} + {num2} = {total}.",
            f"Ответ: {total}/{den}.",
        ],
        solution=f"{num1}/{den} + {num2}/{den} = {total}/{den}.",
        widget={"type": "fraction_bar", "den": den, "num": total},
        difficulty=difficulty,
    )


# ------------------------------------------------------------------ величины
@gen("units", "length")
def length_units(difficulty: int = 1) -> dict:
    m = rnd(1, 9)
    cm = rnd(1, 99)
    return task(
        question=f"Сколько сантиметров в {m} м {cm} см? Впиши только число.",
        answer=m * 100 + cm,
        variables={"m": m, "cm": cm, "m_cm": m * 100},
        hints=[
            "В 1 метре 100 сантиметров.",
            f"{m} м = {m * 100} см.",
            f"{m * 100} + {cm} = ?",
        ],
        solution=f"{m} · 100 + {cm} = {m * 100 + cm} см.",
        widget={"type": "ruler", "cm": m * 100 + cm},
        difficulty=difficulty,
    )


@gen("units", "mass")
def mass_units(difficulty: int = 1) -> dict:
    kg = rnd(1, 9)
    g = rnd(1, 99) * 10
    return task(
        question=f"Сколько граммов в {kg} кг {g} г? Впиши только число.",
        answer=kg * 1000 + g,
        variables={"kg": kg, "g": g, "kg_g": kg * 1000},
        hints=[
            "В 1 килограмме 1000 граммов.",
            f"{kg} кг = {kg * 1000} г.",
            f"{kg * 1000} + {g} = ?",
        ],
        solution=f"{kg} · 1000 + {g} = {kg * 1000 + g} г.",
        widget={"type": "scale", "kg": kg, "g": g},
        difficulty=difficulty,
    )


@gen("units", "time")
def time_units(difficulty: int = 1) -> dict:
    h = rnd(1, 5)
    m = rnd(1, 59)
    return task(
        question=f"Сколько минут в {h} ч {m} мин? Впиши только число.",
        answer=h * 60 + m,
        variables={"h": h, "m": m, "h_min": h * 60},
        hints=[
            "В 1 часе 60 минут.",
            f"{h} ч = {h * 60} мин.",
            f"{h * 60} + {m} = ?",
        ],
        solution=f"{h} · 60 + {m} = {h * 60 + m} мин.",
        widget={"type": "clock", "h": h, "m": m},
        difficulty=difficulty,
    )


@gen("units", "money")
def money_units(difficulty: int = 1) -> dict:
    price = rnd(2, 25)
    qty = rnd(2, 9)
    return task(
        question=f"Цена одного товара — {price} р. Купили {qty} таких товаров. Сколько заплатили?",
        answer=price * qty,
        variables={"price": price, "qty": qty, "total": price * qty},
        hints=[
            "Чтобы найти стоимость, цену умножь на количество.",
            f"{price} · {qty} = ?",
            "Посчитай произведение.",
        ],
        solution=f"{price} · {qty} = {price * qty} р.",
        widget={"type": "money", "coins": price},
        difficulty=difficulty,
    )


# ------------------------------------------------------- периметр и площадь
@gen("perimeter_area", "perimeter")
def perimeter_rect(difficulty: int = 1) -> dict:
    a = rnd(3, 30)
    b = rnd(3, 30)
    return task(
        question=f"Прямоугольник имеет стороны {a} см и {b} см. Найди его периметр.",
        answer=2 * (a + b),
        variables={"a": a, "b": b, "p": 2 * (a + b)},
        hints=[
            "Периметр — это сумма длин всех сторон.",
            "У прямоугольника две пары равных сторон.",
            f"P = {a} + {b} + {a} + {b} = ?",
        ],
        solution=f"P = 2 · ({a} + {b}) = {2 * (a + b)} см.",
        widget={"type": "shapes", "kind": "rect", "a": a, "b": b},
        difficulty=difficulty,
    )


@gen("perimeter_area", "area")
def area_rect(difficulty: int = 1) -> dict:
    a = rnd(2, 25)
    b = rnd(2, 25)
    return task(
        question=f"Прямоугольник имеет стороны {a} см и {b} см. Найди его площадь.",
        answer=a * b,
        variables={"a": a, "b": b, "s": a * b},
        hints=[
            "Площадь прямоугольника — это произведение сторон.",
            "Представь, что прямоугольник разбит на квадратики со стороной 1 см.",
            f"{a} · {b} = ?",
        ],
        solution=f"S = {a} · {b} = {a * b} см².",
        widget={"type": "shapes", "kind": "rect", "a": a, "b": b, "area": True},
        difficulty=difficulty,
    )


@gen("perimeter_area", "perimeter_sum")
def perimeter_sum(difficulty: int = 1) -> dict:
    sides = [rnd(2, 15) for _ in range(rnd(3, 6))]
    return task(
        question="Найди периметр многоугольника со сторонами: " + ", ".join(f"{s} см" for s in sides) + ".",
        answer=sum(sides),
        variables={"sides": sides},
        hints=[
            "Периметр — сумма всех сторон.",
            "Сложи длины всех сторон по очереди.",
            "Помни, что складываем сантиметры.",
        ],
        solution=" + ".join(map(str, sides)) + f" = {sum(sides)} см.",
        widget={"type": "shapes", "kind": "polygon", "sides": sides},
        difficulty=difficulty,
    )


@gen("perimeter_area", "compare")
def compare_perimeter(difficulty: int = 1) -> dict:
    a1, b1 = rnd(4, 20), rnd(4, 20)
    a2, b2 = rnd(4, 20), rnd(4, 20)
    p1, p2 = 2 * (a1 + b1), 2 * (a2 + b2)
    if p1 == p2:
        p2 += 2
    correct = "Первый" if p1 > p2 else "Второй"
    choices = shuffle_options(["Первый", "Второй"])
    return task(
        question=(
            f"У первого прямоугольника стороны {a1} см и {b1} см, у второго — {a2} см и {b2} см. "
            "У кого периметр больше?"
        ),
        answer=correct,
        answer_type="choice",
        choices=choices,
        variables={"a1": a1, "b1": b1, "a2": a2, "b2": b2},
        hints=[
            "Сначала найди периметр каждого прямоугольника.",
            f"P₁ = 2 · ({a1} + {b1}) = {p1}, P₂ = 2 · ({a2} + {b2}) = {p2}.",
            "Сравни полученные значения.",
        ],
        solution=f"Периметр первого {p1} см, второго {p2} см.",
        widget={"type": "shapes", "kind": "rect", "a": a1, "b": b1},
        difficulty=difficulty,
    )


# ------------------------------------------------------------------- задачи
@gen("word_problems", "price_quantity")
def price_quantity(difficulty: int = 1) -> dict:
    price = rnd(3, 30)
    qty = rnd(3, 12)
    item = rnd(0, 3)
    items = ["тетрадь", "карандаш", "ручка", "краска"][item]
    return task(
        question=f"Одна {items} стоит {price} р. Сколько стоят {qty} таких {items}?",
        answer=price * qty,
        variables={"price": price, "qty": qty, "total": price * qty, "item": items},
        hints=[
            "Это задача на умножение: цена × количество.",
            f"Цена {price} р, количество {qty}.",
            f"{price} · {qty} = ?",
        ],
        solution=f"{price} · {qty} = {price * qty} р.",
        widget={"type": "money", "coins": price},
        difficulty=difficulty,
    )


@gen("word_problems", "unit_rate")
def unit_rate(difficulty: int = 1) -> dict:
    per = rnd(3, 12)
    boxes = rnd(3, 8)
    target = rnd(2, 9)
    total = per * boxes
    return task(
        question=(
            f"В {boxes} одинаковых коробках {total} карандашей. Сколько карандашей в {target} таких же коробках?"
        ),
        answer=per * target,
        variables={"per": per, "boxes": boxes, "target": target, "total": total},
        hints=[
            "Сначала узнай, сколько карандашей в одной коробке.",
            f"{total} : {boxes} = ?",
            f"Потом умножь на {target}: {per} · {target}.",
        ],
        solution=f"{total} : {boxes} = {per}; {per} · {target} = {per * target}.",
        widget={"type": "packages", "boxes": boxes, "per_box": per, "target_boxes": target},
        difficulty=difficulty,
    )


@gen("word_problems", "two_step")
def two_step(difficulty: int = 1) -> dict:
    per = rnd(4, 10)
    boxes = rnd(3, 6)
    extra = rnd(2, 20)
    total = per * boxes + extra
    return task(
        question=(
            f"В коробке {per} конфет. Коробок было {boxes}, и ещё {extra} конфет добавили сверху. "
            "Сколько всего конфет?"
        ),
        answer=total,
        variables={"per": per, "boxes": boxes, "extra": extra, "total": total},
        hints=[
            "Сначала узнай, сколько конфет в коробках.",
            f"{per} · {boxes} = ?",
            f"Потом прибавь {extra}.",
        ],
        solution=f"{per} · {boxes} + {extra} = {total}.",
        widget={"type": "packages", "boxes": boxes, "per_box": per, "extra": extra},
        difficulty=difficulty,
    )


@gen("word_problems", "inverse")
def inverse_problem(difficulty: int = 1) -> dict:
    per = rnd(3, 12)
    boxes = rnd(3, 9)
    total = per * boxes
    return task(
        question=(
            f"{total} конфет разложили по {per} в коробку. Сколько получилось коробок?"
        ),
        answer=boxes,
        variables={"per": per, "total": total, "boxes": boxes},
        hints=[
            "Обратная задача к умножению — деление.",
            f"{total} : {per} = ?",
            "Сколько раз по {per} помещается в {total}?",
        ],
        solution=f"{total} : {per} = {boxes}.",
        widget={"type": "packages", "boxes": boxes, "per_box": per, "highlight": "boxes"},
        difficulty=difficulty,
    )


# ------------------------------------------------------ таблицы и диаграммы
@gen("data", "table")
def table_read(difficulty: int = 1) -> dict:
    names = ["Аня", "Борис", "Вера", "Глеб"]
    values = [rnd(3, 20) for _ in names]
    rows = [[n, str(v)] for n, v in zip(names, values)]
    idx = rnd(0, len(names) - 1)
    return task(
        question=f"По таблице узнай: сколько очков набрал(а) {names[idx]}?",
        answer=values[idx],
        variables={"rows": rows, "headers": ["Имя", "Очки"], "target": names[idx]},
        hints=[
            "Найди в таблице строку с нужным именем.",
            f"Строка {names[idx]}: во втором столбце стоит число.",
            "Это и есть ответ.",
        ],
        solution=f"{names[idx]} — {values[idx]}.",
        widget={"type": "table", "headers": ["Имя", "Очки"], "rows": rows},
        difficulty=difficulty,
    )


@gen("data", "chart")
def chart_read(difficulty: int = 1) -> dict:
    labels = ["Пн", "Вт", "Ср", "Чт", "Пт"]
    values = [rnd(2, 15) for _ in labels]
    idx = rnd(0, len(labels) - 1)
    return task(
        question=f"Сколько задач решено в {labels[idx]}?",
        answer=values[idx],
        variables={"labels": labels, "values": values},
        hints=[
            "Посмотри на столбик нужного дня.",
            "Высота столбика — это число.",
            f"Найди столбик {labels[idx]}.",
        ],
        solution=f"В {labels[idx]} решено {values[idx]} задач.",
        widget={"type": "chart", "labels": labels, "values": values},
        difficulty=difficulty,
    )


@gen("data", "difference")
def chart_difference(difficulty: int = 1) -> dict:
    labels = ["Пн", "Вт", "Ср", "Чт", "Пт"]
    values = [rnd(2, 15) for _ in labels]
    i, j = rnd(0, 4), rnd(0, 4)
    while i == j:
        j = rnd(0, 4)
    hi, lo = (i, j) if values[i] > values[j] else (j, i)
    return task(
        question=f"На сколько больше задач решено в {labels[hi]}, чем в {labels[lo]}?",
        answer=values[hi] - values[lo],
        variables={"labels": labels, "values": values},
        hints=[
            "Найди оба столбика и вычти из большего меньшее.",
            f"{labels[hi]}: {values[hi]}, {labels[lo]}: {values[lo]}.",
            "Вычти второе из первого.",
        ],
        solution=f"{values[hi]} − {values[lo]} = {values[hi] - values[lo]}.",
        widget={"type": "chart", "labels": labels, "values": values},
        difficulty=difficulty,
    )
