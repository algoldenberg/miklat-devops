# SNS topic для уведомлений — управляется Terraform'ом, аналог ручного
# dev-топика из Фазы 1 (`miklat-notifications`), но отдельный (см. s3.tf —
# та же логика: ручной остаётся для локальной разработки, этот — для стенда
# на EC2). Три триггера (#1a новая заявка, #1b фото на модерации, #2 жалоба)
# по-прежнему различаются полем "event" в теле сообщения — топик один, как и
# в Фазе 1.

resource "aws_sns_topic" "notifications" {
  name = "${var.project_name}-notifications-tf"

  tags = {
    Name = "${var.project_name}-notifications"
  }
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.notifications.arn
  protocol  = "email"
  endpoint  = var.notification_email

  # Email-подписки требуют подтверждения по ссылке из письма — Terraform не
  # может сделать это за пользователя, это тот же ручной шаг, что был и в
  # Фазе 1 (клик "Confirm subscription" в письме от AWS).
}
