# Все значения, специфичные для окружения/аккаунта, вынесены сюда — реальные
# значения задаются через terraform.tfvars (в git не попадает, см.
# .gitignore), в репозитории только terraform.tfvars.example с плейсхолдерами.

variable "aws_region" {
  description = "AWS-регион. Тот же, что уже используется для dev S3/SNS из Фазы 1 (il-central-1, Israel/Tel Aviv)."
  type        = string
  default     = "il-central-1"
}

variable "aws_profile" {
  description = "Имя профиля AWS CLI (~/.aws/credentials), которым Terraform должен пользоваться. Пусто = профиль по умолчанию / переменные окружения AWS_ACCESS_KEY_ID и т.п."
  type        = string
  default     = ""
}

variable "environment" {
  description = "Метка окружения для тегов (dev/staging/prod) — здесь фактически всегда dev, но вынесено переменной, а не захардкожено."
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Префикс имени для всех ресурсов и тегов — используется вместо повторения строки \"miklat\" по всему коду."
  type        = string
  default     = "miklat"
}

# --- Сеть ---

variable "vpc_cidr" {
  description = "CIDR-блок VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR-блоки публичных подсетей (по одной на AZ) — здесь размещаются все 3 EC2-инстанса, т.к. проекту не нужен NAT Gateway (лишние деньги/сложность для учебного стенда с одним стейджем)."
  type        = list(string)
  default     = ["10.20.1.0/24", "10.20.2.0/24"]
}

variable "availability_zones" {
  description = "AZ для публичных подсетей — должны существовать в выбранном регионе (в il-central-1 их две: il-central-1a, il-central-1b)."
  type        = list(string)
  default     = ["il-central-1a", "il-central-1b"]
}

# --- Доступ по SSH ---

variable "ssh_allowed_cidr" {
  description = "CIDR, которому разрешён SSH (порт 22) на EC2-инстансы. Намеренно БЕЗ значения по умолчанию — 0.0.0.0/0 для SSH недопустим (см. таблицу сверки Задания 2), значение обязан явно задать тот, кто применяет конфигурацию, указав свой текущий внешний IP (например, \"1.2.3.4/32\")."
  type        = string
}

variable "ssh_public_key_path" {
  description = "Путь к ФАЙЛУ ПУБЛИЧНОГО SSH-ключа (например, ~/.ssh/miklat-devops.pub), который Terraform загрузит в AWS как Key Pair. Приватный ключ Terraform никогда не видит и не создаёт — им управляет только тот, кто применяет конфигурацию, так же как остальными секретами проекта."
  type        = string
}

variable "mbdai_public_ip" {
  description = "CIDR (обычно /32) с публичным IP сервера mbdai, на котором развёрнут k3s (Фаза 3, Задание 3) — вне этого VPC. Нужен, чтобы дать k3s-подам доступ к RDS: они не входят ни в одну SG внутри VPC, поэтому единственный способ их пропустить — явный CIDR. Намеренно БЕЗ значения по умолчанию, как и ssh_allowed_cidr — 0.0.0.0/0 для доступа к БД недопустим, значение обязан явно задать тот, кто применяет конфигурацию (например, \"83.229.70.64/32\")."
  type        = string
}

# --- EC2 ---

variable "instance_type" {
  description = "Тип инстанса для всех трёх серверов (frontend/backend/worker). t3.micro — минимальный тип, есть в free tier."
  type        = string
  default     = "t3.micro"
}

variable "ami_id" {
  description = "AMI Amazon Linux 2023 (x86_64) для всех трёх EC2-инстансов — ЗАФИКСИРОВАННЫЙ явный ID, а не динамический SSM-параметр \"latest\". Изначально AMI брался через data.aws_ssm_parameter (см. историю ec2.tf), но это оказалось нестабильно: значение SSM-параметра \"latest\" меняется со временем независимо от того, менялась ли конфигурация проекта, из-за чего terraform plan через несколько дней после apply начинал показывать destroy+recreate всех трёх инстансов без единой реальной причины (обнаружено при сборке evidence для Задания 2, 02.09.2026). Значение по умолчанию — реальный AMI, на котором сейчас развёрнуты все три инстанса (снят через `aws ec2 describe-instances`). Обновлять значение сознательно, только когда реально нужна новая версия ОС."
  type        = string
  default     = "ami-0487e9d84db7c95ff"
}

# --- RDS ---

variable "db_instance_class" {
  description = "Класс инстанса RDS. db.t3.micro — минимальный, есть в free tier."
  type        = string
  default     = "db.t3.micro"
}

variable "db_engine_version" {
  description = "Версия PostgreSQL для RDS — совпадает с тем, что используется локально в docker-compose (Postgres 16), чтобы поведение не отличалось между окружениями."
  type        = string
  default     = "16"
}

variable "db_allocated_storage_gb" {
  description = "Размер диска RDS в ГБ."
  type        = number
  default     = 20
}

variable "db_name" {
  description = "Имя базы данных PostgreSQL."
  type        = string
  default     = "miklat"
}

variable "db_username" {
  description = "Master-пользователь RDS."
  type        = string
  default     = "miklat_admin"
}

variable "db_password" {
  description = "Master-пароль RDS. Без значения по умолчанию и намеренно sensitive — задаётся только в terraform.tfvars (не в git) или через переменную окружения TF_VAR_db_password."
  type        = string
  sensitive   = true
}

# --- S3 / SNS ---

variable "notification_email" {
  description = "Email для подписки на SNS-топик уведомлений (тот же смысл, что и ручная dev-подписка из Фазы 1, но теперь создаётся Terraform'ом)."
  type        = string
  default     = "shelternearyou@gmail.com"
}