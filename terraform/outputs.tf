# Outputs — то, что реально понадобится дальше: Ansible inventory (IP серверов)
# и .env приложения (RDS endpoint, S3 bucket, SNS ARN, region). Можно собрать
# машиночитаемо через `terraform output -json` (задел под бонус —
# динамический inventory-скрипт в Фазе 2/Ansible).

output "frontend_public_ip" {
  description = "Публичный IP frontend-сервера — сюда идёт браузер/DNS, и по нему же Ansible ходит по SSH (frontend — единственный, кому нужен публичный вход для конечного пользователя)."
  value       = aws_instance.frontend.public_ip
}

output "backend_public_ip" {
  description = "Публичный IP backend-сервера — нужен только чтобы Ansible мог зайти по SSH (сам backend внутри VPC ходит по приватному IP, наружу его не выставляем ничем, кроме SSH)."
  value       = aws_instance.backend.public_ip
}

output "worker_public_ip" {
  description = "Публичный IP worker-сервера — только для SSH от Ansible, как и у backend."
  value       = aws_instance.worker.public_ip
}

# Приватные IP — то, чем сервисы реально обращаются друг к другу внутри VPC
# (nginx на frontend -> gateway на backend; gateway на backend -> сервисы на
# worker). Трафик между инстансами так не выходит за пределы VPC и не зависит
# от NAT/публичных адресов, хотя все инстансы формально в "публичных" подсетях
# (см. обоснование в network.tf).
output "backend_private_ip" {
  description = "Приватный IP backend — сюда nginx на frontend проксирует /api/*."
  value       = aws_instance.backend.private_ip
}

output "worker_private_ip" {
  description = "Приватный IP worker — сюда miklat-gateway на backend проксирует routes/walking-routes/photos."
  value       = aws_instance.worker.private_ip
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
