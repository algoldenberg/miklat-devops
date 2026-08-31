#!/usr/bin/env python3
"""Фаза 4, шаг 4.4: минимальная валидация структуры репозитория и Dockerfile'ов
перед сборкой — сознательно без внешнего сканера (hadolint и т.п.): не хотим
добавлять ещё один образ в ci-agent ради одного шага, набор проверок ниже
покрывает то, что явно требует план (структура, Dockerfile lint) точечно.
Может быть расширен позже, если понадобится более полный lint.
"""
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = [
    "miklat-gateway",
    "miklat-service",
    "miklat-comments",
    "miklat-routes",
    "miklat-walking-routes",
    "miklat-photos",
]

errors = []


def check_dockerfile(path: pathlib.Path, name: str) -> None:
    if not path.exists():
        errors.append(f"{name}: Dockerfile не найден ({path})")
        return
    text = path.read_text()
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.upper().startswith("FROM "):
            image_ref = stripped.split()[1]
            base = image_ref.split("@")[0]
            if base.endswith(":latest") or ":" not in base:
                errors.append(
                    f"{name}:{lineno}: FROM без зафиксированного тега (или ':latest') — {stripped}"
                )
    if "USER " not in text:
        errors.append(f"{name}: нет директивы USER (сервис должен работать не от root)")


def check_dockerignore(dirpath: pathlib.Path, name: str) -> None:
    if not (dirpath / ".dockerignore").exists():
        errors.append(f"{name}: отсутствует .dockerignore")


for svc in SERVICES:
    svc_dir = REPO_ROOT / "services" / svc
    if not svc_dir.is_dir():
        errors.append(f"{svc}: директория services/{svc}/ не найдена")
        continue
    check_dockerfile(svc_dir / "Dockerfile", svc)
    check_dockerignore(svc_dir, svc)

frontend_dir = REPO_ROOT / "frontend"
if not frontend_dir.is_dir():
    errors.append("frontend: директория frontend/ не найдена")
else:
    check_dockerfile(frontend_dir / "Dockerfile", "frontend")
    check_dockerignore(frontend_dir, "frontend")

if errors:
    print("Validate FAILED:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

print(
    f"Validate OK — {len(SERVICES)} backend-сервисов + frontend, "
    "структура и Dockerfile'ы в порядке."
)
