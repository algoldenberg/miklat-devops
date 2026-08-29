# S3 bucket для фото укрытий — управляется Terraform'ом, отдельно от
# ручного dev-бакета из Фазы 1 (шаг 9, `miklat-photos-dev-<account_id>`,
# создан вручную через AWS CLI специально как одноразовое исключение для
# ЛОКАЛЬНОЙ проверки через docker-compose). Тот бакет остаётся нетронутым —
# им продолжает пользоваться локальная разработка. Этот, новый — то, что
# реально будет использовать приложение, развёрнутое на EC2 (Задание 2).
# Суффикс "-tf" в имени — чтобы не столкнуться с уже существующим именем
# (S3-имена уникальны глобально, "photos-dev-<id>" уже занято тем бакетом).

resource "aws_s3_bucket" "photos" {
  bucket = "${var.project_name}-photos-tf-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${var.project_name}-photos"
  }
}

# Публичный доступ полностью заблокирован — то же решение, что и в Фазе 1:
# фото отдаются только через presigned URL, который генерирует сам сервис
# miklat-photos, а не напрямую из бакета.
resource "aws_s3_bucket_public_access_block" "photos" {
  bucket = aws_s3_bucket.photos.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "photos" {
  bucket = aws_s3_bucket.photos.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
