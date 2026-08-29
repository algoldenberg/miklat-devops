# Провайдер AWS. Регион фиксирован переменной (уже выбран в Фазе 1, шаг 9 —
# il-central-1 / Israel-Tel Aviv, тот же аккаунт, что для dev S3/SNS).
#
# Credentials НЕ прописаны здесь явно (ни access key, ни secret) — Terraform
# берёт их из стандартной цепочки поиска AWS-провайдера: переменные окружения
# (AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY) или файл ~/.aws/credentials
# (профиль по умолчанию, либо конкретный — см. var.aws_profile). Это тот же
# принцип, что и с секретами приложения — ничего чувствительного не лежит в
# файлах репозитория.
provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile != "" ? var.aws_profile : null

  default_tags {
    tags = {
      Project     = "miklat-devops"
      ManagedBy   = "terraform"
      Environment = var.environment
    }
  }
}

# Текущий аккаунт AWS — используется дальше (например, для уникального имени
# S3-бакета) вместо random-суффикса, тем же способом, каким уже назван
# ручной dev-бакет из Фазы 1 (miklat-photos-dev-<account_id>).
data "aws_caller_identity" "current" {}
