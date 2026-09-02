# 3 EC2-инстанса — frontend/backend/worker (см. обоснование деления в
# security_groups.tf). AMI ЗАФИКСИРОВАН явным ID (var.ami_id), а не взят
# динамически через SSM-параметр "latest" — так было изначально, но при
# сборке evidence для Задания 2 (02.09.2026) обнаружилось, что значение
# SSM-параметра "latest" со временем меняется само по себе (AWS выпускает
# новые версии AL2023), из-за чего `terraform plan` через несколько дней
# после `apply` начинал показывать "-/+ destroy and then create replacement"
# для всех трёх инстансов без единого реального изменения конфигурации —
# случайный `terraform apply` в этот момент снёс бы всю инфраструктуру.
# Исправлено закреплением конкретного AMI ID (реальный AMI, на котором
# сейчас развёрнуты все три инстанса) — обновлять сознательно, только
# когда реально нужна новая версия ОС, тогда apply пересоздаст инстансы
# намеренно, а не случайно.

# Key Pair — из уже существующего ПУБЛИЧНОГО ключа пользователя (см.
# variables.tf::ssh_public_key_path). Terraform приватный ключ не создаёт и
# не хранит — им управляет только тот, кто запускает apply/ansible, как и
# остальными секретами проекта.
resource "aws_key_pair" "main" {
  key_name = "${var.project_name}-key"
  # pathexpand() — на случай, если путь в tfvars задан с "~" (Terraform,
  # в отличие от bash, сам "~" не разворачивает). Тем не менее на Windows
  # надёжнее всё равно указывать полный путь с буквой диска (C:/Users/...),
  # а не "~" и не MSYS-стиль "/c/Users/..." — см. terraform.tfvars.example.
  public_key = file(pathexpand(var.ssh_public_key_path))

  tags = {
    Name = "${var.project_name}-key"
  }
}

resource "aws_instance" "frontend" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.frontend.id]
  key_name               = aws_key_pair.main.key_name

  tags = {
    Name = "${var.project_name}-frontend"
    Role = "frontend"
  }
}

resource "aws_instance" "backend" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.backend.id]
  key_name               = aws_key_pair.main.key_name
  # miklat-service на backend публикует SNS (submissions/reports) — нужен
  # тот же instance profile, что и у worker (см. iam.tf).
  iam_instance_profile = aws_iam_instance_profile.app.name

  tags = {
    Name = "${var.project_name}-backend"
    Role = "backend"
  }
}

resource "aws_instance" "worker" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.worker.id]
  key_name               = aws_key_pair.main.key_name
  # miklat-photos на worker пишет в S3 и публикует SNS — нужен instance
  # profile с правами из iam.tf (вместо статического IAM-пользователя,
  # как было в Фазе 1 для локальной разработки).
  iam_instance_profile = aws_iam_instance_profile.app.name

  tags = {
    Name = "${var.project_name}-worker"
    Role = "worker"
  }
}