"""
Тонкий клиент к AWS SNS — публикация уведомлений о новой заявке на укрытие
(SNS-триггер #1a) и о жалобе на существующее укрытие (SNS-триггер #2), см.
db/001_init.sql и combined-project-overview.md.

Тот же принцип, что и app/aws_client.py в miklat-photos: единственная точка,
где сервис реально обращается к AWS, вынесена в отдельный модуль специально
для того, чтобы её было легко monkeypatch-нуть в тестах (в песочнице Claude
нет сети до AWS и нет тестового топика).
"""

import json
import logging

import boto3
from botocore.exceptions import ClientError

from app.config import AWS_REGION

logger = logging.getLogger("miklat-service.aws")

_sns_client = None


def _sns():
    global _sns_client
    if _sns_client is None:
        _sns_client = boto3.client("sns", region_name=AWS_REGION)
    return _sns_client


def publish_report_notification(topic_arn: str, report: dict) -> None:
    """SNS-триггер #2: пользователь пожаловался на существующее укрытие.
    Публикуется в тот же Topic `miklat-notifications`, что и уведомления о
    новых заявках/фото на модерации (#1a/#1b) — отличаются только полем
    "event" в теле сообщения."""
    message = {
        "event": "miklat_reported",
        "report_id": report["id"],
        "miklat_id": report["miklat_id"],
        "issue_type": report["issue_type"],
        "comment": report.get("comment"),
        "reported_at": str(report["reported_at"]),
    }
    _sns().publish(
        TopicArn=topic_arn,
        Subject="miklat-devops: новая жалоба на укрытие",
        Message=json.dumps(message, ensure_ascii=False),
    )


def publish_submission_notification(topic_arn: str, submission: dict) -> None:
    """SNS-триггер #1a: пользователь предложил новое укрытие (форма
    'добавить укрытие' на фронтенде) — заявка легла в miklat_submissions
    со статусом 'pending', ждёт admin-модерации (approve/reject)."""
    message = {
        "event": "new_submission_pending_moderation",
        "submission_id": submission["id"],
        "name": submission.get("name"),
        "address": submission.get("address"),
        "lon": submission["lon"],
        "lat": submission["lat"],
        "submitted_at": str(submission["submitted_at"]),
    }
    _sns().publish(
        TopicArn=topic_arn,
        Subject="miklat-devops: новая заявка на укрытие",
        Message=json.dumps(message, ensure_ascii=False),
    )


def check_topic_reachable(topic_arn: str) -> bool:
    """Лёгкая readiness-проверка (аналог head_bucket в miklat-photos) —
    подтверждает, что топик существует и у нас есть права на него."""
    try:
        _sns().get_topic_attributes(TopicArn=topic_arn)
        return True
    except ClientError as exc:
        logger.warning("SNS readiness check failed: %s", exc)
        return False
