"""Проверка синтаксиса всех Jinja-шаблонов."""
import glob
import io

import jinja2

env = jinja2.Environment()
errors = 0
for path in sorted(glob.glob("templates/**/*.html", recursive=True)):
    source = io.open(path, encoding="utf-8").read()
    try:
        env.parse(source)
    except Exception as exc:
        errors += 1
        print(f"!! {path}: {exc}")
        lines = source.split("\n")
        number = getattr(exc, "lineno", 0)
        if number and number <= len(lines):
            print("   >", lines[number - 1].strip()[:120])
print(f"Проверено шаблонов: {len(glob.glob('templates/**/*.html', recursive=True))}, ошибок: {errors}")
