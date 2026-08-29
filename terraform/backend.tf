# State — намеренно локальный backend (terraform.tfstate в этой же папке),
# не S3+DynamoDB. Причина: проект соло (нет параллельной работы нескольких
# человек над одним state, ради которой обычно и нужен remote backend с
# locking), а поднимать отдельный S3-бакет+DynamoDB-таблицу только под сам
# Terraform state — лишняя инфраструктура ради инфраструктуры для учебного
# проекта. Компромисс осознанный и описан в README (раздел "State").
#
# terraform.tfstate НИКОГДА не коммитится (см. .gitignore, terraform/*.tfstate*)
# — в нём в открытом виде хранятся все атрибуты ресурсов, включая RDS-пароль.
terraform {
  backend "local" {
    path = "terraform.tfstate"
  }
}
