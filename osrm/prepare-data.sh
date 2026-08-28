#!/usr/bin/env bash
#
# Разовая подготовка данных для OSRM: скачивает карту Израиля/Палестины
# (OpenStreetMap-экстракт от Geofabrik) и строит из неё граф для пешеходного
# профиля (foot). Результат кладётся в ./data/ — эту папку дальше монтирует
# сервис `osrm` из корневого docker-compose.yml.
#
# Нужно запускать один раз (или заново — после смены карты/профиля).
# Требует Docker (используем официальный образ osrm-backend, ничего не ставим
# локально) и свободную сеть до download.geofabrik.de.
#
# Запуск:  bash osrm/prepare-data.sh

set -euo pipefail

# На Windows Git Bash (MSYS) автоматическая подмена путей в аргументах умеет
# ломать составные docker-аргументы вида "/host/path:/container/path" —
# MSYS иногда принимает такую строку за список путей (как $PATH) и заменяет
# ":" на ";", коверкая и хостовую, и контейнерную часть. MSYS_NO_PATHCONV=1
# отключает эту подмену целиком для команд в этом скрипте; на Linux/macOS
# переменная просто не используется — скрипт остаётся кросс-платформенным.
export MSYS_NO_PATHCONV=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${SCRIPT_DIR}/data"
PBF_URL="https://download.geofabrik.de/asia/israel-and-palestine-latest.osm.pbf"
PBF_FILE="israel-and-palestine-latest.osm.pbf"
OSRM_IMAGE="ghcr.io/project-osrm/osrm-backend"

mkdir -p "${DATA_DIR}"
cd "${DATA_DIR}"

# Реальный экстракт Израиля/Палестины — больше 10 МБ с большим запасом.
# Прокси Geofabrik (download-proxyNN) иногда отдаёт вместо файла html-страницу
# с ошибкой ("Read Error", "Please retry your request") размером в пару КБ —
# без этой проверки такой ответ молча сохранился бы как будто это карта, и
# сломался бы уже на этапе osrm-extract с непонятной ошибкой парсинга PBF.
MIN_EXPECTED_BYTES=10000000

if [ -f "${PBF_FILE}" ] && [ "$(wc -c < "${PBF_FILE}")" -lt "${MIN_EXPECTED_BYTES}" ]; then
    echo "==> Найден подозрительно маленький файл карты ($(wc -c < "${PBF_FILE}") байт) — похоже, прошлая попытка скачивания не удалась. Удаляю."
    rm -f "${PBF_FILE}"
fi

if [ ! -f "${PBF_FILE}" ]; then
    echo "==> Скачиваю карту Израиля/Палестины (Geofabrik)..."
    # -f: считать HTTP-ошибки/ответы прокси ошибкой, а не "успешно скачанным файлом"
    # --retry: автоматически повторить при временных сбоях на стороне Geofabrik
    curl -fL --retry 5 --retry-delay 10 --retry-all-errors -o "${PBF_FILE}" "${PBF_URL}"

    ACTUAL_SIZE="$(wc -c < "${PBF_FILE}")"
    if [ "${ACTUAL_SIZE}" -lt "${MIN_EXPECTED_BYTES}" ]; then
        echo "==> ОШИБКА: скачанный файл подозрительно маленький (${ACTUAL_SIZE} байт) — это не карта, а, вероятно, страница с ошибкой прокси Geofabrik:"
        cat "${PBF_FILE}"
        rm -f "${PBF_FILE}"
        exit 1
    fi
else
    echo "==> ${PBF_FILE} уже скачан ($(wc -c < "${PBF_FILE}") байт), пропускаю."
fi

# Примечание про "//": на Windows Git Bash (MSYS) любой отдельный аргумент,
# похожий на unix-путь ("/opt/foot.lua"), автоматически подменяется на
# Windows-путь (например "C:/Program Files/Git/opt/foot.lua") ещё до того,
# как долетит до docker — из-за этого osrm-extract получает не тот путь.
# Двойной слеш в начале ("//opt/foot.lua") отключает эту подмену именно в
# Git Bash и одновременно остаётся корректным путём внутри Linux-контейнера
# (ядро схлопывает "//" в "/"), так что один и тот же скрипт работает и на
# Windows, и на Linux/macOS без разветвлений по ОС.
echo "==> osrm-extract (профиль foot)..."
docker run --rm -t -v "${DATA_DIR}:/data" "${OSRM_IMAGE}" \
    osrm-extract -p //opt/foot.lua "//data/${PBF_FILE}"

OSRM_BASE="${PBF_FILE%.osm.pbf}"

echo "==> osrm-partition..."
docker run --rm -t -v "${DATA_DIR}:/data" "${OSRM_IMAGE}" \
    osrm-partition "//data/${OSRM_BASE}.osrm"

echo "==> osrm-customize..."
docker run --rm -t -v "${DATA_DIR}:/data" "${OSRM_IMAGE}" \
    osrm-customize "//data/${OSRM_BASE}.osrm"

echo "==> Готово. Файлы графа лежат в ${DATA_DIR}/${OSRM_BASE}.osrm*"
echo "==> Теперь можно поднимать сервис osrm: docker compose up -d osrm"
