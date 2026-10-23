"""Учебная программа 3–4 класса (Республика Беларусь).

Каждая тема содержит несколько «способов объяснения» (методов) — ребёнок может
попросить объяснить иначе: визуальная модель, числовая прямая, таблица, схема,
разложение на части и т.д.
"""
from __future__ import annotations

from typing import Any

# Учебное пособие: Муравьёва Г.Л., Урбан М.А. «Математика» для 3 класса, в 2 частях.
# Часть 1 — основной учебник (стр. 4–137), часть 2 — «Повторение за класс» (стр. 5–143).
TOPICS: list[dict[str, Any]] = [
    # ------------------------------------------------------------- 3 класс
    {
        "slug": "numbers_1000",
        "title": "Числа до 1000",
        "grade": 3,
        "icon": "🔢",
        "color": "indigo",
        "part": 1,
        "page_start": 4,
        "page_end": 27,
        "min_level": 1,
        "description": "Разряды, десятки и сотни, сравнение чисел, округление, порядок следования.",
        "generators": [
            "numbers_1000.place_value",
            "numbers_1000.compare",
            "numbers_1000.order",
            "numbers_1000.round_hundred",
            "numbers_1000.digit_in_place",
        ],
        "methods": [
            {
                "slug": "place_value_blocks",
                "name": "Разрядные блоки",
                "widget": "place_value",
                "example": "numbers_1000.place_value",
                "explanation": (
                    "Каждое число складывается из разрядов. В числе {number} "
                    "{hundreds} сотен, {tens} десятков и {ones} единиц. "
                    "Большой кубик — это 1 сотня (100), средний — 1 десяток (10), "
                    "а маленький кубик — 1 единица."
                ),
                "steps": [
                    {"text": "Смотри на число по разрядам: сначала сотни, потом десятки, потом единицы.", "focus": "hundreds"},
                    {"text": "Сотня — это 100. Десяток — это 10. Единица — это 1.", "focus": "tens"},
                    {"text": "Всего получается {number}: {hundreds}·100 + {tens}·10 + {ones}·1 = {number}.", "focus": "ones"},
                ],
            },
            {
                "slug": "sum_of_terms",
                "name": "Сумма разрядных слагаемых",
                "widget": "place_value",
                "example": "numbers_1000.place_value",
                "explanation": (
                    "Число {number} можно записать как сумму разрядных слагаемых: "
                    "{hundreds}·100 + {tens}·10 + {ones} = {number}. "
                    "Так проще считать: 100, 10 и 1 — это удобные «круглые» числа."
                ),
                "steps": [
                    {"text": "Выпиши разрядные слагаемые: {hundreds}·100, {tens}·10, {ones}·1."},
                    {"text": "Сложи: {hundreds}·100 + {tens}·10 + {ones} = {number}.", "focus": "hundreds"},
                    {"text": "Получилось {number} — это и есть наше число."},
                ],
            },
            {
                "slug": "compare_by_place",
                "name": "Сравнение по разрядам",
                "widget": "number_line",
                "example": "numbers_1000.compare",
                "explanation": (
                    "Чтобы сравнить числа, смотри на разряды слева направо: сначала сотни. "
                    "Число {a} и число {b}. Если сотни разные — больше то, у кого сотен больше."
                ),
                "steps": [
                    {"text": "Сначала сравни сотни: у {a} и {b}."},
                    {"text": "Если сотни равны, сравни десятки."},
                    {"text": "Если и десятки равны, сравни единицы."},
                ],
            },
            {
                "slug": "number_line_place",
                "name": "Числовая прямая",
                "widget": "number_line",
                "example": "numbers_1000.order",
                "explanation": (
                    "Все числа живут на числовой прямой. Чем правее число, тем оно больше. "
                    "Расположи числа по возрастанию — и ты сразу увидишь порядок."
                ),
                "steps": [
                    {"text": "Найди на прямой каждое из чисел."},
                    {"text": "Иди слева направо — от меньшего к большему."},
                    {"text": "Самое левое число — самое маленькое."},
                ],
            },
        ],
    },
    {
        "slug": "add_sub_1000",
        "title": "Сложение и вычитание",
        "grade": 3,
        "icon": "➕",
        "color": "sky",
        "part": 1,
        "page_start": 4,
        "page_end": 27,
        "min_level": 1,
        "description": "Сложение и вычитание в пределах 1000: в столбик, по частям, проверка.",
        "generators": [
            "add_sub_1000.add_column",
            "add_sub_1000.sub_column",
            "add_sub_1000.missing_term",
            "add_sub_1000.check",
            "add_sub_1000.estimate_sum",
        ],
        "methods": [
            {
                "slug": "column",
                "name": "В столбик",
                "widget": "column",
                "example": "add_sub_1000.add_column",
                "explanation": (
                    "Выписываем числа друг под другом: единицы под единицами, десятки под десятками, "
                    "сотни под сотнями. Складываем справа налево. Если в столбце больше 9 — "
                    "переносим 1 десяток в следующий столбец."
                ),
                "steps": [
                    {"text": "Выпиши {a} и {b} в столбик.", "focus": "top"},
                    {"text": "Сложи единицы: {a_ones} + {b_ones}.", "focus": "ones"},
                    {"text": "Сложи десятки и сотни, не забудь перенос. Ответ: {sum}.", "focus": "tens"},
                ],
            },
            {
                "slug": "parts",
                "name": "По частям",
                "widget": "number_line",
                "example": "add_sub_1000.add_column",
                "explanation": (
                    "Сначала прибавь к {a} десятки числа {b}, потом единицы. "
                    "Так считать легче, потому что круглые числа считать проще."
                ),
                "steps": [
                    {"text": "Отдели у {b} десятки и единицы."},
                    {"text": "Прибавь десятки к {a}."},
                    {"text": "Прибавь единицы. Ответ: {sum}."},
                ],
            },
            {
                "slug": "check_back",
                "name": "Проверка обратным действием",
                "widget": "balance",
                "example": "add_sub_1000.check",
                "explanation": (
                    "Сложение проверяют вычитанием, а вычитание — сложением. "
                    "Если {c} + {b} = {a}, значит пример {a} − {b} = {c} решён верно."
                ),
                "steps": [
                    {"text": "Действие, обратное вычитанию, — сложение."},
                    {"text": "Сложи результат с вычитаемым: {c} + {b}."},
                    {"text": "Если получилось {a} — все верно!"},
                ],
            },
            {
                "slug": "estimate",
                "name": "Прикидка",
                "widget": "place_value",
                "example": "add_sub_1000.estimate_sum",
                "explanation": (
                    "Прикидка — это быстрая проверка. Округли числа до десятков: "
                    "{a} ≈ {ra}, {b} ≈ {rb}. Ответ должен быть рядом с {ra} + {rb}."
                ),
                "steps": [
                    {"text": "Округли {a} до десятков: {a} ≈ {ra}."},
                    {"text": "Округли {b} до десятков: {b} ≈ {rb}."},
                    {"text": "Сложи: {ra} + {rb} = {estimate}. Значит, ответ рядом."},
                ],
            },
        ],
    },
    {
        "slug": "mult_div_table",
        "title": "Умножение и деление",
        "grade": 3,
        "icon": "✖️",
        "color": "violet",
        "part": 1,
        "page_start": 28,
        "page_end": 78,
        "min_level": 1,
        "description": "Табличное умножение и деление, группы предметов, массив, числовая прямая.",
        "generators": [
            "mult_div_table.mult",
            "mult_div_table.div",
            "mult_div_table.word",
            "mult_div_table.replace",
            "mult_div_table.commutative",
        ],
        "methods": [
            {
                "slug": "groups",
                "name": "Группы предметов",
                "widget": "groups",
                "example": "mult_div_table.word",
                "explanation": (
                    "Представь: {a} коробок, в каждой по {b} конфет. "
                    "Чтобы узнать, сколько конфет всего, нужно {a} умножить на {b}. "
                    "Получится {product} конфет."
                ),
                "steps": [
                    {"text": "Посчитай группы: их {a}.", "focus": "rows"},
                    {"text": "В каждой группе по {b} конфет.", "focus": "cols"},
                    {"text": "Умножь: {a} · {b} = {product}.", "focus": "all"},
                ],
            },
            {
                "slug": "array",
                "name": "Прямоугольный массив",
                "widget": "array",
                "example": "mult_div_table.mult",
                "explanation": (
                    "Разложим на клетки: {a} рядов по {b} клеток. "
                    "Всего клеток {a} · {b} = {product}. Строки считаем сверху вниз, клетки — слева направо."
                ),
                "steps": [
                    {"text": "В массиве {a} рядов (строк).", "focus": "rows"},
                    {"text": "В каждом ряду {b} клеток.", "focus": "cols"},
                    {"text": "Всего {a} · {b} = {product} клеток.", "focus": "all"},
                ],
            },
            {
                "slug": "jumps",
                "name": "Прыжки по прямой",
                "widget": "number_line",
                "example": "mult_div_table.mult",
                "explanation": (
                    "Прыгай по числовой прямой: {a} прыжков по {b} шагов каждый. "
                    "{a} прыжков по {b} — это и есть {a} · {b} = {product}."
                ),
                "steps": [
                    {"text": "Начни с нуля."},
                    {"text": "Каждый прыжок — это {b} шагов, а прыжков {a}."},
                    {"text": "Приземлись в точку {product}.", "focus": "result"},
                ],
            },
            {
                "slug": "multiplication_table",
                "name": "Таблица умножения",
                "widget": "table_mult",
                "example": "mult_div_table.mult",
                "explanation": (
                    "Таблица умножения — это готовые ответы. Найди строку {a} и столбец {b}. "
                    "На пересечении стоит {product}."
                ),
                "steps": [
                    {"text": "Найди строку с числом {a}."},
                    {"text": "В этой строке найди число {b}."},
                    {"text": "На пересечении — {product}."},
                ],
            },
        ],
    },
    {
        "slug": "mult_div_100",
        "title": "Умножение на 10, 100, 1000",
        "grade": 3,
        "icon": "🔟",
        "color": "emerald",
        "part": 1,
        "page_start": 28,
        "page_end": 78,
        "min_level": 2,
        "description": "Умножение и деление на разрядные единицы, прикидка результата.",
        "generators": [
            "mult_div_100.mult",
            "mult_div_100.div",
            "mult_div_100.increase",
        ],
        "methods": [
            {
                "slug": "append_zeros",
                "name": "Приписываем нули",
                "widget": "shift",
                "example": "mult_div_100.mult",
                "explanation": (
                    "Умножение на 10, 100, 1000 — это приписывание нулей справа к числу. "
                    "{a} · {k} = {product}. А деление на 10 и 100 — наоборот, отбрасываем нули."
                ),
                "steps": [
                    {"text": "Посчитай, сколько нулей в множителе {k}."},
                    {"text": "Припиши столько же нулей справа к {a}."},
                    {"text": "Получилось {product}."},
                ],
            },
            {
                "slug": "by_place_value",
                "name": "Через разряды",
                "widget": "place_value",
                "example": "mult_div_100.mult",
                "explanation": (
                    "Умножение на 10 увеличивает каждую цифру на разряд: десятки становятся сотнями. "
                    "Поэтому {a} · {k} = {product}."
                ),
                "steps": [
                    {"text": "Представь {a} в виде разрядных слагаемых."},
                    {"text": "Умножь каждое слагаемое на {k}."},
                    {"text": "Сложи результаты: {product}."},
                ],
            },
            {
                "slug": "ten_groups",
                "name": "Группы по десять",
                "widget": "groups",
                "example": "mult_div_100.mult",
                "explanation": (
                    "Десять — это полная десятка. Умножение на {k} — это {k} полных десятков. "
                    "Сосчитай их по группам: {a} · {k} = {product}."
                ),
                "steps": [
                    {"text": "Составь {k} групп по {a} предметов."},
                    {"text": "В каждой группе {a} предметов — это {a} десятков."},
                    {"text": "Всего {product}."},
                ],
            },
        ],
    },
    {
        "slug": "remainder",
        "title": "Деление с остатком",
        "grade": 3,
        "icon": "🧩",
        "color": "amber",
        "part": 2,
        "page_start": 29,
        "page_end": 30,
        "min_level": 2,
        "description": "Остаток при делении, проверка условия, задачи на разложение по группам.",
        "generators": [
            "remainder.divide",
            "remainder.max_divisible",
            "remainder.word",
        ],
        "methods": [
            {
                "slug": "groups_remainder",
                "name": "Полные группы и остаток",
                "widget": "groups",
                "example": "remainder.divide",
                "explanation": (
                    "При делении {a} на {b} получается {q} полных групп по {b} и остаток {r}. "
                    "Остаток всегда меньше делителя!"
                ),
                "steps": [
                    {"text": "Разложи {a} предметов в группы по {b}.", "focus": "rows"},
                    {"text": "Полных групп получилось {q}.", "focus": "cols"},
                    {"text": "Осталось {r} — это и есть остаток.", "focus": "extra"},
                ],
            },
            {
                "slug": "jumps_remainder",
                "name": "Прыжки по прямой",
                "widget": "number_line",
                "example": "remainder.divide",
                "explanation": (
                    "Отсчитай прыжки по {b}: каждый прыжок — это {b}. "
                    "Сколько полных прыжков до {a}? Это {q}, а {r} осталось лишними."
                ),
                "steps": [
                    {"text": "Отмечай на прямой точки: 0, {b}, {b}·2 ..."},
                    {"text": "Сколько полных отрезков по {b} поместилось до {a}?"},
                    {"text": "Остаток — {r}."},
                ],
            },
            {
                "slug": "formula",
                "name": "Проверка формулой",
                "widget": "balance",
                "example": "remainder.divide",
                "explanation": (
                    "Главное правило деления с остатком: "
                    "если {a} : {b} = {q} (остаток {r}), то {b} · {q} + {r} = {a}."
                ),
                "steps": [
                    {"text": "Умножь делитель на частное: {b} · {q} = {product}."},
                    {"text": "Вычти из делимого: {a} − {product} = {r}."},
                    {"text": "Остаток {r} меньше делителя {b} — всё верно."},
                ],
            },
        ],
    },
    {
        "slug": "expressions",
        "title": "Порядок действий",
        "grade": 3,
        "icon": "🧮",
        "color": "rose",
        "part": 1,
        "page_start": 79,
        "page_end": 90,
        "min_level": 2,
        "description": "Выражения со скобками, порядок действий, сравнение выражений.",
        "generators": [
            "expressions.order",
            "expressions.brackets",
            "expressions.compare",
        ],
        "methods": [
            {
                "slug": "first_multiply",
                "name": "Сначала умножение",
                "widget": "expression",
                "example": "expressions.order",
                "explanation": (
                    "В выражении сначала выполняют умножение и деление, а потом сложение и вычитание. "
                    "Внутри скобок всегда выполняем всё первым."
                ),
                "steps": [
                    {"text": "Ищи скобки — если есть, делаем их первыми."},
                    {"text": "Потом умножение и деление."},
                    {"text": "В конце — сложение и вычитание. Ответ: {result}."},
                ],
            },
            {
                "slug": "brackets",
                "name": "Расставляем скобки",
                "widget": "expression",
                "example": "expressions.brackets",
                "explanation": (
                    "От скобок меняется порядок действий. Попробуй оба варианта и посчитай — "
                    "один из них даст нужный результат."
                ),
                "steps": [
                    {"text": "Посчитай вариант со скобками вокруг сложения."},
                    {"text": "Посчитай вариант со скобками вокруг умножения."},
                    {"text": "Выбери тот, где получилось {value}."},
                ],
            },
            {
                "slug": "by_parts",
                "name": "Разложение по частям",
                "widget": "number_line",
                "example": "expressions.order",
                "explanation": (
                    "Иногда выражение удобно посчитать по частям: сначала одно действие, "
                    "потом второе. Не спеши — главное не потерять порядок."
                ),
                "steps": [
                    {"text": "Выдели первый кусочек выражения."},
                    {"text": "Посчитай его."},
                    {"text": "Подставь результат и закончи."},
                ],
            },
        ],
    },
    {
        "slug": "equations",
        "title": "Уравнения",
        "grade": 3,
        "icon": "❓",
        "color": "cyan",
        "part": 1,
        "page_start": 79,
        "page_end": 90,
        "min_level": 2,
        "description": "Неизвестное слагаемое, уменьшаемое, вычитаемое, множитель, делитель.",
        "generators": [
            "equations.unknown_addend",
            "equations.unknown_subtrahend",
            "equations.unknown_minuend",
            "equations.unknown_factor",
            "equations.unknown_divisor",
        ],
        "methods": [
            {
                "slug": "balance",
                "name": "Весы",
                "widget": "balance",
                "example": "equations.unknown_addend",
                "explanation": (
                    "Уравнение — это весы, которые в равновесии. "
                    "Чтобы уравновесить чаши, нужно убрать одинаковое с обеих сторон. "
                    "Так и находится неизвестное число x."
                ),
                "steps": [
                    {"text": "Представь уравнение как равные весы."},
                    {"text": "Сделай одинаковые действия с обеими чашами."},
                    {"text": "На чаше с x останется ответ."},
                ],
            },
            {
                "slug": "undo",
                "name": "Обратное действие",
                "widget": "number_line",
                "example": "equations.unknown_addend",
                "explanation": (
                    "Сложение и вычитание — взаимно обратные действия. "
                    "Чтобы найти слагаемое, из суммы вычитаем известное слагаемое."
                ),
                "steps": [
                    {"text": "Определи, какое действие спрятано за знаком."},
                    {"text": "Сделай обратное действие."},
                    {"text": "Получишь x."},
                ],
            },
            {
                "slug": "check_solution",
                "name": "Проверка",
                "widget": "balance",
                "example": "equations.unknown_factor",
                "explanation": (
                    "Всегда проверяй: подставь найденное x в уравнение. "
                    "Если обе части равны — решение верное."
                ),
                "steps": [
                    {"text": "Возьми найденное значение x."},
                    {"text": "Подставь его в уравнение."},
                    {"text": "Сравни части — они должны совпасть."},
                ],
            },
        ],
    },
    {
        "slug": "fractions",
        "title": "Доли и дроби",
        "grade": 3,
        "icon": "🍕",
        "color": "orange",
        "part": 1,
        "page_start": 73,
        "page_end": 78,
        "min_level": 3,
        "description": "Образование долей, часть от целого, сравнение, равные дроби, сложение.",
        "generators": [
            "fractions.from_parts",
            "fractions.of_number",
            "fractions.compare",
            "fractions.equal",
            "fractions.sum_same",
        ],
        "methods": [
            {
                "slug": "circle",
                "name": "Круг с долями",
                "widget": "fraction_circle",
                "example": "fractions.from_parts",
                "explanation": (
                    "Целое разделили на {den} равных частей и взяли {num}. "
                    "Это записывается дробью {num}/{den}: сверху числитель (сколько взяли), "
                    "снизу знаменатель (на сколько разделили)."
                ),
                "steps": [
                    {"text": "Круг — это целое (1).", "focus": "all"},
                    {"text": "Разделили на {den} равных частей.", "focus": "parts"},
                    {"text": "Закрасили {num} частей — это {num}/{den}.", "focus": "num"},
                ],
            },
            {
                "slug": "bar",
                "name": "Полоска",
                "widget": "fraction_bar",
                "example": "fractions.of_number",
                "explanation": (
                    "Полоска разделена на {den} равных частей, закрашено {num}. "
                    "Чтобы найти {num}/{den} от числа {whole}, сначала делим: "
                    "{whole} : {den} = {part}, потом умножаем на {num}."
                ),
                "steps": [
                    {"text": "Сколько приходится на одну часть?"},
                    {"text": "{whole} : {den} = {part}."},
                    {"text": "{part} · {num} = {result}."},
                ],
            },
            {
                "slug": "number_line_fraction",
                "name": "Дробь на прямой",
                "widget": "number_line",
                "example": "fractions.compare",
                "explanation": (
                    "Отрезок от 0 до 1 — это целое. Раздели его на равные части: "
                    "каждая часть — это 1/{den}. Дробь показывает, сколько таких частей взяли."
                ),
                "steps": [
                    {"text": "Отметь на прямой 0 и 1 — это целое."},
                    {"text": "Раздели отрезок на равные части."},
                    {"text": "Отсчита нужное количество частей."},
                ],
            },
            {
                "slug": "words",
                "name": "Дробь словами",
                "widget": "fraction_bar",
                "example": "fractions.equal",
                "explanation": (
                    "Дробь можно увеличить: числитель и знаменатель умножаем на одно и то же число — "
                    "значение дроби не меняется. {num}/{den} = {num}·2/{den}·2."
                ),
                "steps": [
                    {"text": "Представь дробь на круге или полоске."},
                    {"text": "Раздели и целое и часть на столько же частей."},
                    {"text": "Получишь равную дробь."},
                ],
            },
        ],
    },
    {
        "slug": "units",
        "title": "Величины",
        "grade": 3,
        "icon": "📏",
        "color": "teal",
        "part": 1,
        "page_start": 100,
        "page_end": 120,
        "min_level": 1,
        "description": "Длина, масса, время, стоимость: перевод единиц и задачи.",
        "generators": [
            "units.length",
            "units.mass",
            "units.time",
            "units.money",
        ],
        "methods": [
            {
                "slug": "ruler",
                "name": "Линейка",
                "widget": "ruler",
                "example": "units.length",
                "explanation": (
                    "В 1 метре 100 сантиметров, в 1 сантиметре 10 миллиметров. "
                    "{m} м {cm} см — это {m}·100 + {cm} сантиметров."
                ),
                "steps": [
                    {"text": "Переведи метры в сантиметры: {m} м = {m_cm} см."},
                    {"text": "Прибавь оставшиеся сантиметры."},
                    {"text": "Ответ в сантиметрах."},
                ],
            },
            {
                "slug": "scale",
                "name": "Весы",
                "widget": "scale",
                "example": "units.mass",
                "explanation": (
                    "В 1 килограмме 1000 граммов, в 1 центнере 100 килограммов, в 1 тонне 1000 кг. "
                    "Масса {kg} кг {g} г — это {kg}·1000 + {g} граммов."
                ),
                "steps": [
                    {"text": "Килограммы переведи в граммы: {kg} кг = {kg_g} г."},
                    {"text": "Прибавь граммы."},
                    {"text": "Ответ в граммах."},
                ],
            },
            {
                "slug": "clock",
                "name": "Часы",
                "widget": "clock",
                "example": "units.time",
                "explanation": (
                    "В 1 часе 60 минут, в 1 сутках 24 часа, в 1 минуте 60 секунд. "
                    "{h} ч {m} мин — это {h}·60 + {m} минут."
                ),
                "steps": [
                    {"text": "Часы переведи в минуты: {h} ч = {h_min} мин."},
                    {"text": "Прибавь минуты."},
                    {"text": "Ответ в минутах."},
                ],
            },
            {
                "slug": "money",
                "name": "Деньги",
                "widget": "money",
                "example": "units.money",
                "explanation": (
                    "Деньги в Беларуси — в рублях и копейках: 1 р = 100 коп. "
                    "Стоимость = цена · количество: {price} · {qty} = {total} р."
                ),
                "steps": [
                    {"text": "Узнай цену одного товара."},
                    {"text": "Узнай количество товаров."},
                    {"text": "Цена · количество = {total} р."},
                ],
            },
        ],
    },
    {
        "slug": "perimeter_area",
        "title": "Периметр и площадь",
        "grade": 3,
        "icon": "🔷",
        "color": "blue",
        "part": 1,
        "page_start": 96,
        "page_end": 99,
        "min_level": 2,
        "description": "Периметр и площадь прямоугольника и многоугольника.",
        "generators": [
            "perimeter_area.perimeter",
            "perimeter_area.area",
            "perimeter_area.perimeter_sum",
            "perimeter_area.compare",
        ],
        "methods": [
            {
                "slug": "around",
                "name": "Обходим по кругу",
                "widget": "shapes",
                "example": "perimeter_area.perimeter",
                "explanation": (
                    "Периметр — это длина границы фигуры. Представь, что обходишь прямоугольник "
                    "по краю: {a} + {b} + {a} + {b} = {p} см."
                ),
                "steps": [
                    {"text": "Обойди фигуру по краю и выпиши длины сторон."},
                    {"text": "Сложи все стороны."},
                    {"text": "Периметр = {p} см.", "focus": "perimeter"},
                ],
            },
            {
                "slug": "grid",
                "name": "Квадратики",
                "widget": "area_grid",
                "example": "perimeter_area.area",
                "explanation": (
                    "Площадь — это сколько единичных квадратиков помещается в фигуру. "
                    "У прямоугольника {a} см и {b} см их будет {a} · {b} = {s}."
                ),
                "steps": [
                    {"text": "Мысленно раздели фигуру на квадратики 1 см × 1 см."},
                    {"text": "Сосчитай по рядам: {a} в ряду, рядов {b}."},
                    {"text": "Площадь = {s} см².", "focus": "area"},
                ],
            },
            {
                "slug": "formulas",
                "name": "Формулы",
                "widget": "shapes",
                "example": "perimeter_area.compare",
                "explanation": (
                    "У прямоугольника: P = 2 · (a + b), S = a · b. "
                    "Формулы помогают считать быстро, без рисунка."
                ),
                "steps": [
                    {"text": "Вспомни формулу периметра: P = 2 · (a + b)."},
                    {"text": "Вспомни формулу площади: S = a · b."},
                    {"text": "Подставь числа и посчитай."},
                ],
            },
        ],
    },
    {
        "slug": "word_problems",
        "title": "Задачи",
        "grade": 3,
        "icon": "📝",
        "color": "fuchsia",
        "part": 1,
        "page_start": 5,
        "page_end": 130,
        "min_level": 2,
        "description": "Цена, количество, стоимость; приведение к единице; составные задачи.",
        "generators": [
            "word_problems.price_quantity",
            "word_problems.unit_rate",
            "word_problems.two_step",
            "word_problems.inverse",
        ],
        "methods": [
            {
                "slug": "scheme",
                "name": "Схема «сначала — потом»",
                "widget": "table",
                "example": "word_problems.unit_rate",
                "explanation": (
                    "Любую задачу можно разложить на шаги. Сначала узнаём одно, потом другое. "
                    "Запиши, что известно и что нужно найти."
                ),
                "steps": [
                    {"text": "Что известно? Запиши в таблицу."},
                    {"text": "Что нужно найти?"},
                    {"text": "Какое действие поможет это узнать?"},
                ],
            },
            {
                "slug": "picture",
                "name": "Рисунок",
                "widget": "packages",
                "example": "word_problems.unit_rate",
                "explanation": (
                    "Нарисуй группы: в каждой коробке поровну предметов. "
                    "Так сразу видно, сколько предметов в одной коробке и сколько в нескольких."
                ),
                "steps": [
                    {"text": "Изобрази коробки и предметы в них."},
                    {"text": "Посчитай предметы в одной коробке."},
                    {"text": "Потом — в нужном количестве коробок."},
                ],
            },
            {
                "slug": "table_data",
                "name": "Таблица данных",
                "widget": "table",
                "example": "word_problems.price_quantity",
                "explanation": (
                    "Данные удобно записать в таблицу: что известно и что нужно найти. "
                    "Тогда нужное действие видно сразу."
                ),
                "steps": [
                    {"text": "Запиши в таблицу: цена и количество."},
                    {"text": "Какое действие применить?"},
                    {"text": "Посчитай и проверь ответ."},
                ],
            },
            {
                "slug": "check_answer",
                "name": "Проверка ответа",
                "widget": "balance",
                "example": "word_problems.inverse",
                "explanation": (
                    "Проверь себя: составь обратную задачу. Если ответ подходит — ты посчитал верно."
                ),
                "steps": [
                    {"text": "Составь обратную задачу."},
                    {"text": "Реши её."},
                    {"text": "Совпало — ответ верный!"},
                ],
            },
        ],
    },
    {
        "slug": "data",
        "title": "Таблицы и диаграммы",
        "grade": 3,
        "icon": "📊",
        "color": "lime",
        "part": 1,
        "page_start": 120,
        "page_end": 130,
        "min_level": 3,
        "description": "Чтение таблиц и диаграмм, сравнение данных.",
        "generators": [
            "data.table",
            "data.chart",
            "data.difference",
        ],
        "methods": [
            {
                "slug": "table_read",
                "name": "Читаем таблицу",
                "widget": "table",
                "example": "data.table",
                "explanation": (
                    "В таблице строки — это объекты (имена, дни), а столбцы — признаки. "
                    "Нужное значение стоит на пересечении строки и столбца."
                ),
                "steps": [
                    {"text": "Найди нужную строку."},
                    {"text": "В строке найди нужный столбец."},
                    {"text": "На пересечении — ответ."},
                ],
            },
            {
                "slug": "chart_read",
                "name": "Читаем диаграмму",
                "widget": "chart",
                "example": "data.chart",
                "explanation": (
                    "В столбиковой диаграмме чем выше столбик — тем больше значение. "
                    "Посмотри на подпись под столбиком, чтобы понять, о чём он."
                ),
                "steps": [
                    {"text": "Найди столбик с нужной подписью."},
                    {"text": "Посмотри на его высоту."},
                    {"text": "Прочитай значение."},
                ],
            },
            {
                "slug": "compare_data",
                "name": "Сравниваем данные",
                "widget": "chart",
                "example": "data.difference",
                "explanation": (
                    "Чтобы сравнить два столбика, найди их значения и вычти меньшее из большего."
                ),
                "steps": [
                    {"text": "Найди значения обоих столбиков."},
                    {"text": "Вычти меньшее из большего."},
                    {"text": "Запиши разность."},
                ],
            },
        ],
    },
    # ------------------------------------------------------------- 4 класс
    {
        "slug": "mult_div_column",
        "title": "Умножение в столбик",
        "grade": 4,
        "icon": "🧱",
        "color": "indigo",
        "part": 1,
        "page_start": 28,
        "page_end": 60,
        "min_level": 3,
        "description": "Умножение и деление на двузначные числа в столбик, прикидка.",
        "generators": [
            "mult_div_column.mult",
            "mult_div_column.div",
            "mult_div_column.mult_1000",
            "mult_div_column.estimate",
            "mult_div_column.word",
        ],
        "methods": [
            {
                "slug": "column",
                "name": "В столбик",
                "widget": "column",
                "example": "mult_div_column.mult",
                "explanation": (
                    "Умножаем по частям: сначала на цифру единиц, потом на десятки. "
                    "Каждую часть пишем под разрядом, а потом складываем. {a} · {b} = {product}."
                ),
                "steps": [
                    {"text": "Умножь {a} на цифру единиц: {a} · {b_ones}."},
                    {"text": "Умножь {a} на десятки: {a} · {b_tens}."},
                    {"text": "Сложи части со сдвигом. Ответ: {product}.", "focus": "result"},
                ],
            },
            {
                "slug": "decompose",
                "name": "Разложение множителя",
                "widget": "area_model",
                "example": "mult_div_column.mult",
                "explanation": (
                    "Замени второй множитель суммой разрядов: {b} = {b_tens}·10 + {b_ones}. "
                    "Тогда {a} · {b} = {a}·{b_tens}·10 + {a}·{b_ones}. Так понятнее!"
                ),
                "steps": [
                    {"text": "Разложи {b} на десятки и единицы."},
                    {"text": "Умножь {a} на каждую часть."},
                    {"text": "Сложи результаты: {product}."},
                ],
            },
            {
                "slug": "area_model",
                "name": "Модель площади",
                "widget": "area_model",
                "example": "mult_div_column.mult",
                "explanation": (
                    "Представь прямоугольник {a} на {b}. Раздели его на две части и посчитай "
                    "площадь каждой части — получится {product}."
                ),
                "steps": [
                    {"text": "Нарисуй прямоугольник со сторонами {a} и {b}."},
                    {"text": "Раздели его по разрядам второго множителя."},
                    {"text": "Посчитай обе части и сложи: {product}."},
                ],
            },
            {
                "slug": "estimate_check",
                "name": "Прикидка и проверка",
                "widget": "place_value",
                "example": "mult_div_column.estimate",
                "explanation": (
                    "Сначала прикинь: округли до десятков {a} ≈ {ra}, {b} ≈ {rb}, "
                    "ответ будет около {estimate}. Так можно сразу заметить грубую ошибку."
                ),
                "steps": [
                    {"text": "Округли оба числа до десятков."},
                    {"text": "Перемножь округлённые — получишь прикидку."},
                    {"text": "Проверь, похож ли твой ответ на прикидку."},
                ],
            },
        ],
    },
    {
        "slug": "divisibility",
        "title": "Признаки делимости",
        "grade": 4,
        "icon": "🔎",
        "color": "emerald",
        "part": 1,
        "page_start": 61,
        "page_end": 72,
        "min_level": 4,
        "description": "Делимость на 2, 3, 5, 9, 10, 25; чётные и нечётные числа.",
        "generators": [
            "divisibility.by_2_5_10",
            "divisibility.by_3_9",
            "divisibility.even_odd",
            "divisibility.by_25",
        ],
        "methods": [
            {
                "slug": "last_digit",
                "name": "По последней цифре",
                "widget": "place_value",
                "example": "divisibility.by_2_5_10",
                "explanation": (
                    "Делимость на 2, 5 и 10 определяется последней цифрой числа. "
                    "На 2 делятся числа, оканчивающиеся на 0, 2, 4, 6, 8; "
                    "на 5 — на 0 или 5; на 10 — на 0."
                ),
                "steps": [
                    {"text": "Выпиши последнюю цифру числа."},
                    {"text": "Вспомни, какие цифры подходят для делителя {divisor}."},
                    {"text": "Сделай вывод."},
                ],
            },
            {
                "slug": "digit_sum",
                "name": "По сумме цифр",
                "widget": "place_value",
                "example": "divisibility.by_3_9",
                "explanation": (
                    "На 3 и 9 делится число, у которого сумма цифр делится на 3 (соответственно на 9). "
                    "У числа {n} сумма цифр равна {sum}."
                ),
                "steps": [
                    {"text": "Сложи все цифры числа."},
                    {"text": "Раздели сумму на {divisor}."},
                    {"text": "Если без остатка — число делится на {divisor}."},
                ],
            },
            {
                "slug": "parity",
                "name": "Чётное или нечётное",
                "widget": "place_value",
                "example": "divisibility.even_odd",
                "explanation": (
                    "Чётное число делится на 2 без остатка. Значит, оно оканчивается "
                    "на чётную цифру: 0, 2, 4, 6 или 8. Нечётное заканчивается на 1, 3, 5, 7 или 9."
                ),
                "steps": [
                    {"text": "Посмотри на последнюю цифру."},
                    {"text": "Она чётная или нечётная?"},
                    {"text": "Такой же характер у всего числа."},
                ],
            },
        ],
    },
    {
        "slug": "fractions_ops",
        "title": "Действия с дробями",
        "grade": 4,
        "icon": "🍰",
        "color": "orange",
        "part": 1,
        "page_start": 73,
        "page_end": 78,
        "min_level": 4,
        "description": "Сложение и вычитание дробей, сравнение, смешанные числа.",
        "generators": [
            "fractions_ops.add_same",
            "fractions_ops.sub_same",
            "fractions_ops.compare",
            "fractions_ops.mixed",
            "fractions_ops.of_number",
        ],
        "methods": [
            {
                "slug": "bar",
                "name": "На полоске",
                "widget": "fraction_bar",
                "example": "fractions_ops.add_same",
                "explanation": (
                    "Складывать дроби удобно на полоске: она разделена на {den} равных частей. "
                    "Сложение — это когда ты занимаешь больше частей. "
                    "{num1}/{den} + {num2}/{den} = {total}/{den}."
                ),
                "steps": [
                    {"text": "Отметь на полоске {num1} частей."},
                    {"text": "Добавь ещё {num2} части."},
                    {"text": "Всего {total} частей из {den} — это {total}/{den}.", "focus": "num"},
                ],
            },
            {
                "slug": "common_denominator",
                "name": "К общему знаменателю",
                "widget": "fraction_bar",
                "example": "fractions_ops.compare",
                "explanation": (
                    "Чтобы сравнить или сложить разные дроби, приведи их к общему знаменателю — "
                    "к одному и тому же числу частей. Тогда сравнивать части легко."
                ),
                "steps": [
                    {"text": "Найди общий знаменатель."},
                    {"text": "Умножь числитель и знаменатель на одно и то же число."},
                    {"text": "Теперь знаменатели равны — сравнивай числители."},
                ],
            },
            {
                "slug": "mixed_numbers",
                "name": "Смешанные числа",
                "widget": "fraction_bar",
                "example": "fractions_ops.mixed",
                "explanation": (
                    "Если числитель больше знаменателя, дробь можно записать как смешанное число: "
                    "целая часть и остаток. {num}/{den} = {whole} {rem}/{den}."
                ),
                "steps": [
                    {"text": "Раздели числитель на знаменатель."},
                    {"text": "Запиши частное — это целая часть."},
                    {"text": "Остаток запиши над знаменателем."},
                ],
            },
            {
                "slug": "circle",
                "name": "На круге",
                "widget": "fraction_circle",
                "example": "fractions_ops.of_number",
                "explanation": (
                    "Круг — это удобная модель для дробей. Целое делят на {den} частей, "
                    "и каждая часть стоит {part} от числа {whole}."
                ),
                "steps": [
                    {"text": "Раздели круг на {den} равных частей."},
                    {"text": "Одна часть — это 1/{den} целого."},
                    {"text": "Зная общее число {whole}, найди одну часть и умножь на {num}."},
                ],
            },
        ],
    },
    {
        "slug": "motion",
        "title": "Движение",
        "grade": 4,
        "icon": "🚄",
        "color": "sky",
        "part": 1,
        "page_start": 84,
        "page_end": 95,
        "min_level": 4,
        "description": "Скорость, время, расстояние; встречное движение; задачи в два действия.",
        "generators": [
            "motion.speed",
            "motion.find_speed",
            "motion.find_time",
            "motion.meet",
            "motion.two_parts",
        ],
        "methods": [
            {
                "slug": "path",
                "name": "Схема пути",
                "widget": "path",
                "example": "motion.speed",
                "explanation": (
                    "Главные формулы движения: s = v · t, v = s : t, t = s : v. "
                    "При скорости {v} км/ч за {t} ч получится путь {s} км."
                ),
                "steps": [
                    {"text": "Запиши, что известно: скорость {v} км/ч, время {t} ч."},
                    {"text": "Что нужно найти? Путь."},
                    {"text": "Используй формулу s = v · t."},
                ],
            },
            {
                "slug": "table_svt",
                "name": "Таблица s, v, t",
                "widget": "table",
                "example": "motion.find_speed",
                "explanation": (
                    "Движение удобно записывать в таблицу: путь, скорость, время. "
                    "Что-то всегда можно найти делением или умножением."
                ),
                "steps": [
                    {"text": "Запиши путь и скорость в таблицу."},
                    {"text": "Найди время: t = s : v."},
                    {"text": "Проверь: s = v · t."},
                ],
            },
            {
                "slug": "meet",
                "name": "Встречное движение",
                "widget": "path",
                "example": "motion.meet",
                "explanation": (
                    "Когда два тела движутся навстречу, расстояние между ними каждый час "
                    "уменьшается на сумму их скоростей: {v1} + {v2} = {v_sum} км/ч."
                ),
                "steps": [
                    {"text": "Сложи скорости: {v1} + {v2} = {v_sum} км/ч."},
                    {"text": "Умножь на время встречи {t} ч."},
                    {"text": "Получишь расстояние между городами: {s} км."},
                ],
            },
            {
                "slug": "parts",
                "name": "По этапам",
                "widget": "path",
                "example": "motion.two_parts",
                "explanation": (
                    "Если движение описано в два этапа, считай путь по частям, а потом складывай."
                ),
                "steps": [
                    {"text": "Найди путь за первый этап."},
                    {"text": "Найди путь за второй этап."},
                    {"text": "Сложи результаты."},
                ],
            },
        ],
    },
    {
        "slug": "area_units",
        "title": "Площади",
        "grade": 4,
        "icon": "🌾",
        "color": "lime",
        "part": 1,
        "page_start": 96,
        "page_end": 99,
        "min_level": 4,
        "description": "Единицы площади, составные фигуры, перевод квадратных метров.",
        "generators": [
            "area_units.convert",
            "area_units.hectare",
            "area_units.composite",
            "area_units.square",
        ],
        "methods": [
            {
                "slug": "grid",
                "name": "Квадратики",
                "widget": "area_grid",
                "example": "area_units.composite",
                "explanation": (
                    "Площадь измеряется в квадратных единицах: см², м², км², га. "
                    "В 1 м² помещается 10 000 квадратиков со стороной 1 см."
                ),
                "steps": [
                    {"text": "Определи, в каких единицах считать."},
                    {"text": "Разбей фигуру на прямоугольники и квадраты."},
                    {"text": "Сложи их площади."},
                ],
            },
            {
                "slug": "decompose",
                "name": "Разложение фигуры",
                "widget": "shapes",
                "example": "area_units.composite",
                "explanation": (
                    "Любую фигуру можно разбить на прямоугольники. "
                    "Площадь прямоугольника {a}×{b} — это {ab}, площадь квадрата {c}×{c} — {cc}. "
                    "Итого {s} см²."
                ),
                "steps": [
                    {"text": "Проведи линии и разбей фигуру на части."},
                    {"text": "Найди площадь каждой части."},
                    {"text": "Сложи: {s} см²."},
                ],
            },
            {
                "slug": "units",
                "name": "Перевод единиц",
                "widget": "area_grid",
                "example": "area_units.convert",
                "explanation": (
                    "В 1 м² — 10 000 см², в 1 км² — 1 000 000 м², в 1 га — 10 000 м². "
                    "Чтобы перевести квадратные метры в сантиметры, умножь на 10 000."
                ),
                "steps": [
                    {"text": "Вспомни: 1 м = 100 см."},
                    {"text": "В квадрате: 1 м² = 100 · 100 = 10 000 см²."},
                    {"text": "Умножь на 10 000."},
                ],
            },
        ],
    },
    {
        "slug": "time_calc",
        "title": "Время и календарь",
        "grade": 4,
        "icon": "⏰",
        "color": "rose",
        "part": 1,
        "page_start": 100,
        "page_end": 110,
        "min_level": 4,
        "description": "Часы и минуты, сутки, недели, месяцы, вычисление времени.",
        "generators": [
            "time_calc.clock",
            "time_calc.minutes",
            "time_calc.day",
            "time_calc.month",
        ],
        "methods": [
            {
                "slug": "clock",
                "name": "Часы",
                "widget": "clock",
                "example": "time_calc.clock",
                "explanation": (
                    "Короткая стрелка показывает часы, длинная — минуты. "
                    "Маленькая стрелка (часовая) проходит между цифрами медленно."
                ),
                "steps": [
                    {"text": "Найди, где показывает короткая стрелка — это часы."},
                    {"text": "Посмотри на длинную стрелку — это минуты."},
                    {"text": "Запиши время так: {h}:{m:02d}."},
                ],
            },
            {
                "slug": "timeline",
                "name": "Лента времени",
                "widget": "timeline",
                "example": "time_calc.minutes",
                "explanation": (
                    "Чтобы посчитать, сколько времени прошло, переведи всё в минуты: "
                    "1 час = 60 минут, 1 сутки = 24 часа = 1440 минут."
                ),
                "steps": [
                    {"text": "Переведи начало в минуты."},
                    {"text": "Переведи конец в минуты."},
                    {"text": "Вычти — получишь прошедшее время."},
                ],
            },
            {
                "slug": "calendar",
                "name": "Календарь",
                "widget": "calendar",
                "example": "time_calc.month",
                "explanation": (
                    "В сутках 24 часа, в неделе 7 дней, в году 12 месяцев. "
                    "В месяцах бывает 30 или 31 день, а в феврале — 28 (29 в високосный год)."
                ),
                "steps": [
                    {"text": "Вспомни, сколько дней в неделе: {week_days}."},
                    {"text": "Вспомни, сколько часов в сутках: {day_hours}."},
                    {"text": "Смотри календарь и считай."},
                ],
            },
        ],
    },
]


def topics_for_grade(grade: int) -> list[dict[str, Any]]:
    return [t for t in TOPICS if t["grade"] == grade]


def topic_by_slug(slug: str) -> dict[str, Any] | None:
    for t in TOPICS:
        if t["slug"] == slug:
            return t
    return None


def method_by_slug(topic_slug: str, method_slug: str) -> dict[str, Any] | None:
    topic = topic_by_slug(topic_slug)
    if not topic:
        return None
    for m in topic["methods"]:
        if m["slug"] == method_slug:
            return m
    return None


def all_methods() -> list[dict[str, Any]]:
    out = []
    for topic in TOPICS:
        for method in topic["methods"]:
            out.append({"topic": topic["slug"], **method})
    return out


# ------------------------------------------------- параметры визуальных моделей
WIDGET_KEYS: dict[str, list[str]] = {
    "place_value": ["number"],
    "number_line": ["from", "to", "marks", "jumps", "result"],
    "groups": ["rows", "cols", "emoji", "extra", "extra_emoji"],
    "array": ["rows", "cols"],
    "column": ["top", "bottom", "op", "result"],
    "fraction_circle": ["den", "num"],
    "fraction_bar": ["den", "num"],
    "balance": ["left", "right", "unknown"],
    "clock": ["h", "m"],
    "ruler": ["cm"],
    "scale": ["kg", "g"],
    "shapes": ["kind", "a", "b", "c", "sides", "area"],
    "area_grid": ["n"],
    "table": ["headers", "rows"],
    "chart": ["labels", "values"],
    "money": ["coins"],
    "packages": ["boxes", "per_box", "target_boxes", "extra"],
    "path": ["v", "t", "s", "v2"],
    "shift": ["number", "zeros"],
    "table_mult": ["a", "b"],
    "expression": ["a", "b", "c"],
    "timeline": ["h", "m", "add"],
    "calendar": ["month", "days"],
}

WIDGET_DEFAULTS: dict[str, dict[str, Any]] = {
    "number_line": {"from": 0, "to": 100},
    "groups": {"rows": 3, "cols": 4, "emoji": "🔵"},
    "array": {"rows": 3, "cols": 4},
    "place_value": {"number": 245},
    "fraction_circle": {"den": 4, "num": 1},
    "fraction_bar": {"den": 4, "num": 1},
    "balance": {"left": 12, "right": 20, "unknown": "x"},
    "clock": {"h": 3, "m": 0},
    "ruler": {"cm": 10},
    "scale": {"kg": 2, "g": 500},
    "shapes": {"kind": "rect", "a": 8, "b": 5},
    "area_grid": {"n": 4},
    "money": {"coins": 12},
    "packages": {"boxes": 4, "per_box": 5},
    "path": {"v": 60, "t": 3, "s": 180},
    "shift": {"number": 24, "zeros": 2},
    "table_mult": {"a": 4, "b": 5},
    "expression": {"a": 3, "b": 4, "c": 5},
    "timeline": {"h": 9, "m": 0, "add": 45},
    "calendar": {"month": "январь", "days": 31},
}


def widget_spec(widget_type: str, variables: dict[str, Any], fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    """Собрать параметры визуальной модели из переменных задания."""
    spec: dict[str, Any] = dict(fallback or {})
    if spec.get("type") != widget_type:
        spec = {"type": widget_type}
    defaults = WIDGET_DEFAULTS.get(widget_type, {})
    for key in WIDGET_KEYS.get(widget_type, []):
        if key in variables and variables[key] is not None:
            spec[key] = variables[key]
        elif key not in spec and key in defaults:
            spec[key] = defaults[key]
    for key, value in defaults.items():
        spec.setdefault(key, value)
    return spec
