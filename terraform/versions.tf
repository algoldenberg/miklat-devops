# Версии Terraform и провайдеров — зафиксированы явно (не "latest"), чтобы
# план/apply были воспроизводимы на любой машине (у пользователя это будет
# Windows + Git Bash, как и весь остальной проект).

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
