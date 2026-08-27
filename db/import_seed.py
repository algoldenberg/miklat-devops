#!/usr/bin/env python3
"""
Загружает seed-данные (db/seed/*.json) в PostgreSQL/PostGIS.

Seed-файлы получены из реального дампа прод-приложения shelter-route-planner
(mongodb-backup/shelter_planner: shelters, comments, shelter_reports,
shelter_submissions) и конвертированы в плоский JSON. IP-адреса пользователей
(reporter_ip / submitted_by_ip) намеренно НЕ перенесены — это приватные данные
реальных людей, в новой базе эти поля просто останутся NULL для сид-записей и
будут заполняться только для новых, реальных обращений через приложение.

Использование:
    export DATABASE_URL="postgresql://miklat:miklat@localhost:5432/miklat"
    python3 db/import_seed.py
"""

import json
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

SEED_DIR = Path(__file__).parent / "seed"


def get_conn():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        sys.exit("ERROR: задайте переменную окружения DATABASE_URL")
    return psycopg2.connect(dsn)


def load_json(name):
    with open(SEED_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def import_miklats(cur):
    rows = load_json("miklats_seed.json")
    values = [
        (
            r["legacy_mongo_id"],
            r["name"],
            r["address"],
            r["city"],
            r["capacity"],
            r["accessible"],
            r["lon"],
            r["lat"],
            r["type"],
            r["description"],
            r["source"],
        )
        for r in rows
    ]
    execute_values(
        cur,
        """
        INSERT INTO miklats
            (legacy_mongo_id, name, address, city, capacity, accessible,
             geom, type, description, source, is_verified)
        VALUES %s
        ON CONFLICT (legacy_mongo_id) DO NOTHING
        """,
        values,
        template="(%s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s, %s, %s, TRUE)",
    )
    print(f"miklats: вставлено (или уже было) {len(values)} записей")


def legacy_id_map(cur):
    cur.execute("SELECT legacy_mongo_id, id FROM miklats WHERE legacy_mongo_id IS NOT NULL")
    return dict(cur.fetchall())


def import_comments(cur, id_map):
    rows = load_json("comments_seed.json")
    values = []
    skipped = 0
    for r in rows:
        miklat_id = id_map.get(r["legacy_shelter_mongo_id"])
        if miklat_id is None:
            skipped += 1
            continue
        values.append((r["legacy_mongo_id"], miklat_id, r["username"], r["comment"], r["rating"]))
    if values:
        execute_values(
            cur,
            """
            INSERT INTO miklat_comments (legacy_mongo_id, miklat_id, username, comment, rating)
            VALUES %s
            ON CONFLICT (legacy_mongo_id) DO NOTHING
            """,
            values,
        )
    print(f"miklat_comments: вставлено {len(values)}, пропущено (нет связанного miklat) {skipped}")


def import_reports(cur, id_map):
    rows = load_json("reports_seed.json")
    values = []
    skipped = 0
    for r in rows:
        miklat_id = id_map.get(r["legacy_shelter_mongo_id"])
        if miklat_id is None:
            skipped += 1
            continue
        values.append(
            (r["legacy_mongo_id"], miklat_id, r["issue_type"], r["comment"], r["contact"], r["status"])
        )
    if values:
        execute_values(
            cur,
            """
            INSERT INTO miklat_reports (legacy_mongo_id, miklat_id, issue_type, comment, contact, status)
            VALUES %s
            ON CONFLICT (legacy_mongo_id) DO NOTHING
            """,
            values,
        )
    print(f"miklat_reports: вставлено {len(values)}, пропущено (нет связанного miklat) {skipped}")


def import_submissions(cur, id_map):
    rows = load_json("submissions_seed.json")
    values = [
        (
            r["legacy_mongo_id"],
            r["name"],
            r["address"],
            r["lon"],
            r["lat"],
            r["type"],
            r["capacity"],
            r["comment"],
            r["status"],
            r["reviewed_by"],
            r["rejection_reason"],
            id_map.get(r["legacy_approved_shelter_mongo_id"]) if r.get("legacy_approved_shelter_mongo_id") else None,
        )
        for r in rows
    ]
    execute_values(
        cur,
        """
        INSERT INTO miklat_submissions
            (legacy_mongo_id, name, address, geom, type, capacity, comment,
             status, reviewed_by, rejection_reason, miklat_id)
        VALUES %s
        ON CONFLICT (legacy_mongo_id) DO NOTHING
        """,
        values,
        template="(%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s, %s, %s, %s, %s, %s, %s)",
    )
    print(f"miklat_submissions: вставлено (или уже было) {len(values)} записей")


def main():
    conn = get_conn()
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            import_miklats(cur)
            id_map = legacy_id_map(cur)
            import_comments(cur, id_map)
            import_reports(cur, id_map)
            import_submissions(cur, id_map)
        conn.commit()
        print("Готово.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
