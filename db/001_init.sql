-- miklat-devops — начальная схема БД (PostgreSQL + PostGIS)
--
-- Спроектирована на основе РЕАЛЬНЫХ данных прод-приложения shelter-route-planner
-- (экспорт mongodb-backup/shelter_planner: коллекции shelters, comments,
-- shelter_reports, shelter_submissions) — см. db/seed/*.json.

CREATE EXTENSION IF NOT EXISTS postgis;

-- ============================================================
-- miklats — основная таблица укрытий
-- ============================================================
CREATE TABLE miklats (
    id               BIGSERIAL PRIMARY KEY,
    name             TEXT,
    address          TEXT,
    city             TEXT,
    capacity         INTEGER,
    accessible       BOOLEAN NOT NULL DEFAULT TRUE,
    geom             GEOGRAPHY(Point, 4326) NOT NULL,
    type             TEXT NOT NULL DEFAULT 'public_shelter',
    description      TEXT,
    source           TEXT,
    is_verified      BOOLEAN NOT NULL DEFAULT TRUE,   -- сид-данные считаются проверенными; новые заявки — FALSE до модерации
    legacy_mongo_id  TEXT UNIQUE,                      -- ObjectId из прод-Mongo, для трассировки/связки при импорте
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX miklats_geom_gix ON miklats USING GIST (geom);
CREATE INDEX miklats_city_idx ON miklats (city);
CREATE INDEX miklats_type_idx ON miklats (type);

COMMENT ON COLUMN miklats.type IS
  'Известные значения из прод-данных: public_shelter, school_shelter, parking_storage, parking_shelter, migunit, private_building. Намеренно TEXT, а не enum — таксономия расширялась исторически.';

-- ============================================================
-- miklat_comments — рейтинги/отзывы (Comment Service)
-- ============================================================
CREATE TABLE miklat_comments (
    id               BIGSERIAL PRIMARY KEY,
    miklat_id        BIGINT NOT NULL REFERENCES miklats(id) ON DELETE CASCADE,
    username         TEXT NOT NULL DEFAULT 'Anonymous',
    comment          TEXT NOT NULL,
    rating           SMALLINT CHECK (rating BETWEEN 1 AND 5),
    legacy_mongo_id  TEXT UNIQUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX miklat_comments_miklat_id_idx ON miklat_comments (miklat_id);

-- ============================================================
-- miklat_reports — жалобы на существующее укрытие
-- (SNS-триггер #2: новая жалоба -> email админу)
-- ============================================================
CREATE TABLE miklat_reports (
    id               BIGSERIAL PRIMARY KEY,
    miklat_id        BIGINT NOT NULL REFERENCES miklats(id) ON DELETE CASCADE,
    issue_type       TEXT NOT NULL,                    -- реальные значения из прода: closed, wrong_address, other
    comment          TEXT,
    contact          TEXT,
    reporter_ip      INET,                              -- заполняется только для НОВЫХ (не импортированных) жалоб
    status           TEXT NOT NULL DEFAULT 'pending',   -- pending | resolved | invalid
    legacy_mongo_id  TEXT UNIQUE,
    reported_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at      TIMESTAMPTZ
);

CREATE INDEX miklat_reports_status_idx ON miklat_reports (status);

-- ============================================================
-- miklat_submissions — заявки на НОВОЕ укрытие
-- (SNS-триггер #1a: новая заявка -> email админу)
-- ============================================================
CREATE TABLE miklat_submissions (
    id                BIGSERIAL PRIMARY KEY,
    name              TEXT,
    address           TEXT,
    geom              GEOGRAPHY(Point, 4326) NOT NULL,
    type              TEXT,
    capacity          INTEGER,
    comment           TEXT,
    status            TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | rejected
    submitted_by_ip   INET,                              -- заполняется только для НОВЫХ (не импортированных) заявок
    reviewed_by       TEXT,
    rejection_reason  TEXT,
    miklat_id         BIGINT REFERENCES miklats(id),     -- заполняется при approved
    legacy_mongo_id   TEXT UNIQUE,
    submitted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at       TIMESTAMPTZ
);

CREATE INDEX miklat_submissions_status_idx ON miklat_submissions (status);

-- ============================================================
-- miklat_photos — фото укрытий (в проде такой коллекции не было — новая
-- сущность капстоуна под Photo Service)
-- (SNS-триггер #1b: новое фото на модерации -> email админу)
-- ============================================================
CREATE TABLE miklat_photos (
    id              BIGSERIAL PRIMARY KEY,
    miklat_id       BIGINT NOT NULL REFERENCES miklats(id) ON DELETE CASCADE,
    s3_key          TEXT NOT NULL,
    uploaded_by_ip  INET,
    status          TEXT NOT NULL DEFAULT 'pending',    -- pending | approved | rejected
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at     TIMESTAMPTZ
);

CREATE INDEX miklat_photos_status_idx ON miklat_photos (status);
CREATE INDEX miklat_photos_miklat_id_idx ON miklat_photos (miklat_id);
