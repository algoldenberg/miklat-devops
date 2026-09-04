#!/usr/bin/env python3
"""Фаза 5, Задание 5, п.7: валидация файлов мониторинга (PrometheusRule,
ServiceMonitor/PodMonitor, JSON-дашборды Grafana внутри ConfigMap) —
синтаксис/схема, без обращения к кластеру. Сам деплой дашбордов через CI не
делается (см. план, п.7 и п.9 "Observability as Code") — они попадают в
кластер только через Git -> kubectl apply -> Grafana sidecar provisioning,
эта проверка — только gate ДО того, как файл вообще попадёт в git history
как валидный.

Намеренно не обращается к живому кластеру/Prometheus — только статический
разбор YAML/JSON, чтобы стадия могла идти в python-tools контейнере CI-агента
без прав на кластер (тот же принцип, что и у остальных CI-стадий).
"""
import json
import pathlib
import sys

import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

PROMETHEUS_RULE_FILES = [
    REPO_ROOT / "monitoring" / "slo-recording-rules.yaml",
    REPO_ROOT / "monitoring" / "alerts" / "miklat-alerts.yaml",
]
SERVICE_MONITOR_FILES = [
    REPO_ROOT / "monitoring" / "service-monitors" / "miklat-app-services.yaml",
]
DASHBOARD_CONFIGMAP_FILES = sorted((REPO_ROOT / "monitoring" / "dashboards").glob("*.yaml"))

REQUIRED_ALERT_LABELS = ["severity"]
REQUIRED_ALERT_ANNOTATIONS = ["summary", "description", "runbook_url"]

errors = []


def load_yaml_docs(path: pathlib.Path):
    if not path.exists():
        errors.append(f"{path.relative_to(REPO_ROOT)}: файл не найден")
        return []
    try:
        with path.open() as f:
            docs = [d for d in yaml.safe_load_all(f) if d is not None]
    except yaml.YAMLError as e:
        errors.append(f"{path.relative_to(REPO_ROOT)}: невалидный YAML — {e}")
        return []
    if not docs:
        errors.append(f"{path.relative_to(REPO_ROOT)}: файл пуст или не содержит документов")
    return docs


def check_prometheus_rule(path: pathlib.Path, doc: dict) -> None:
    rel = path.relative_to(REPO_ROOT)
    if doc.get("apiVersion") != "monitoring.coreos.com/v1":
        errors.append(f"{rel}: apiVersion должен быть monitoring.coreos.com/v1, найдено {doc.get('apiVersion')}")
    if doc.get("kind") != "PrometheusRule":
        errors.append(f"{rel}: kind должен быть PrometheusRule, найдено {doc.get('kind')}")
        return
    groups = doc.get("spec", {}).get("groups")
    if not groups:
        errors.append(f"{rel}: spec.groups отсутствует или пуст")
        return
    for g in groups:
        gname = g.get("name", "<без имени>")
        rules = g.get("rules")
        if not rules:
            errors.append(f"{rel}: группа '{gname}' не содержит правил")
            continue
        for r in rules:
            is_record = "record" in r
            is_alert = "alert" in r
            if is_record == is_alert:
                errors.append(f"{rel}: группа '{gname}': правило должно иметь ровно одно из 'record'/'alert' — {r}")
                continue
            if not r.get("expr"):
                name = r.get("record") or r.get("alert")
                errors.append(f"{rel}: группа '{gname}', правило '{name}': отсутствует expr")
            if is_alert:
                alert_name = r.get("alert")
                if not r.get("for"):
                    errors.append(f"{rel}: alert '{alert_name}': отсутствует 'for' (окно устойчивости)")
                labels = r.get("labels", {})
                for req in REQUIRED_ALERT_LABELS:
                    if req not in labels:
                        errors.append(f"{rel}: alert '{alert_name}': отсутствует обязательный label '{req}'")
                annotations = r.get("annotations", {})
                for req in REQUIRED_ALERT_ANNOTATIONS:
                    if req not in annotations:
                        errors.append(f"{rel}: alert '{alert_name}': отсутствует обязательная annotation '{req}' (план Фазы 5 п.6 требует severity/summary/description/runbook)")


def check_service_monitor(path: pathlib.Path, doc: dict) -> None:
    rel = path.relative_to(REPO_ROOT)
    if doc.get("apiVersion") != "monitoring.coreos.com/v1":
        errors.append(f"{rel}: apiVersion должен быть monitoring.coreos.com/v1, найдено {doc.get('apiVersion')}")
    kind = doc.get("kind")
    if kind not in ("ServiceMonitor", "PodMonitor"):
        errors.append(f"{rel}: kind должен быть ServiceMonitor или PodMonitor, найдено {kind}")
        return
    name = doc.get("metadata", {}).get("name", "<без имени>")
    spec = doc.get("spec", {})
    if not spec.get("selector", {}).get("matchLabels"):
        errors.append(f"{rel}: {kind} '{name}': spec.selector.matchLabels отсутствует")
    endpoints_key = "endpoints" if kind == "ServiceMonitor" else "podMetricsEndpoints"
    endpoints = spec.get(endpoints_key)
    if not endpoints:
        errors.append(f"{rel}: {kind} '{name}': spec.{endpoints_key} отсутствует или пуст")
        return
    for ep in endpoints:
        if "targetPort" not in ep and "port" not in ep:
            errors.append(f"{rel}: {kind} '{name}': endpoint без targetPort/port — {ep}")


def check_dashboard_configmap(path: pathlib.Path, doc: dict) -> None:
    rel = path.relative_to(REPO_ROOT)
    if doc.get("kind") != "ConfigMap":
        errors.append(f"{rel}: kind должен быть ConfigMap (dashboard provisioning), найдено {doc.get('kind')}")
        return
    labels = doc.get("metadata", {}).get("labels", {})
    if labels.get("grafana_dashboard") != "1":
        errors.append(f"{rel}: ConfigMap должен иметь label grafana_dashboard: \"1\" (иначе sidecar Grafana его не подхватит)")
    data = doc.get("data", {})
    json_keys = [k for k in data if k.endswith(".json")]
    if len(json_keys) != 1:
        errors.append(f"{rel}: ожидается ровно один ключ *.json в data, найдено {len(json_keys)}")
        return
    raw_json = data[json_keys[0]]
    try:
        dashboard = json.loads(raw_json)
    except json.JSONDecodeError as e:
        errors.append(f"{rel}: содержимое {json_keys[0]} — невалидный JSON: {e}")
        return
    for req in ("uid", "title", "panels"):
        if req not in dashboard:
            errors.append(f"{rel}: JSON-дашборд: отсутствует обязательное поле '{req}'")
    panels = dashboard.get("panels", [])
    if not panels:
        errors.append(f"{rel}: JSON-дашборд '{dashboard.get('title', '?')}': panels пуст")
    for p in panels:
        pid = p.get("id", "?")
        for req in ("id", "type", "title", "targets"):
            if req not in p:
                errors.append(f"{rel}: панель id={pid}: отсутствует обязательное поле '{req}'")
        for t in p.get("targets", []):
            if not t.get("expr"):
                errors.append(f"{rel}: панель id={pid}: target без expr — {t}")


for path in PROMETHEUS_RULE_FILES:
    for doc in load_yaml_docs(path):
        check_prometheus_rule(path, doc)

for path in SERVICE_MONITOR_FILES:
    for doc in load_yaml_docs(path):
        check_service_monitor(path, doc)

for path in DASHBOARD_CONFIGMAP_FILES:
    for doc in load_yaml_docs(path):
        check_dashboard_configmap(path, doc)

if errors:
    print("Validate monitoring FAILED:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)

print(
    f"Validate monitoring OK — {len(PROMETHEUS_RULE_FILES)} файл(ов) PrometheusRule, "
    f"{len(SERVICE_MONITOR_FILES)} файл(ов) ServiceMonitor/PodMonitor, "
    f"{len(DASHBOARD_CONFIGMAP_FILES)} dashboard ConfigMap — синтаксис и схема в порядке."
)