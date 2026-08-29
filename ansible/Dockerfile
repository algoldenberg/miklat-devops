# Control node для Ansible — запускается локально (docker run), внутрь
# монтируются код репозитория и SSH-ключ; сам образ никак не связан с тем,
# что он настраивает (сегодня — 3 EC2 в AWS). Нужен, потому что
# ansible-playbook официально не поддерживает нативный Windows как control
# node — а WSL заводить не обязательно, раз Docker Desktop и так уже есть
# и используется во всём остальном проекте.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        openssh-client \
        rsync \
    && rm -rf /var/lib/apt/lists/*

# ansible (не ansible-core) — тянет за собой набор стандартных коллекций
# (включая ansible.posix, нужен для модуля synchronize при переносе
# OSRM-данных в deploy-worker.yml).
RUN pip install --no-cache-dir ansible==9.*

WORKDIR /ansible
