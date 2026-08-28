"""
Простая защита admin-эндпоинтов через заголовок X-Admin-Key
(решение зафиксировано в miklat-progress.md — минимум кода для учебного
проекта, ключ прокидывается через .env / K8s Secret в следующих фазах).
"""

import hmac

from fastapi import Header, HTTPException, status

from app.config import ADMIN_API_KEY


def require_admin(x_admin_key: str = Header(default="")) -> None:
    if not ADMIN_API_KEY:
        # Ключ не сконфигурирован на сервере — admin-эндпоинты должны быть
        # недоступны, а не открыты по любому пустому значению.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API key is not configured on the server",
        )
    if not x_admin_key or not hmac.compare_digest(x_admin_key, ADMIN_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Admin-Key",
        )
