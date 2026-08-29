# Outputs — то, что реально понадобится дальше: Ansible inventory (IP серверов)
# и .env приложения (RDS endpoint, S3 bucket, SNS ARN, region). Можно собрать
# машиночитаемо через `terraform output -json` (задел под бонус —
# динамический inventory-скрипт в Фазе 2/Ansible).

output "frontend_public_ip" {
  description = "Публичный IP frontend-сервера — сюда идёт браузер/DNS."
  value       = aws_instance.frontend.public_ip
}

output "backend_public_ip" {
  description = "Публичный IP backend-сервера (gateway/service/comments)."
  value       = aws_instance.backend.public_ip
}

output "worker_public_ip" {
  description = "Публичный IP worker-сервера (routes/walking-routes/photos/OSRM)."
  value       = aws_instance.worker.public_ip
}

output "db_endpoint" {
  description = "Endpoint RDS (host:port) — идёт в DATABASE_URL приложения."
  value       = aws_db_instance.main.endpoint
}

output "db_name" {
  value = aws_db_instance.main.db_name
}

output "s3_photos_bucket" {
  description = "Имя S3-бакета для фото укрытий."
  value       = aws_s3_bucket.photos.bucket
}

output "sns_topic_arn" {
  description = "ARN SNS-топика уведомлений."
  value       = aws_sns_topic.notifications.arn
}

output "aws_region" {
  value = var.aws_region
}
