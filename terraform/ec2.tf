# 3 EC2-инстанса — frontend/backend/worker (см. обоснование деления в
# security_groups.tf). AMI берём динамически через публичный SSM-параметр
# (Amazon Linux 2023, x86_64) — не хардкодим id, который отличается по
# регионам и версиям; тот же принцип "не хардкодить", что и во всём проекте.

data "aws_ssm_parameter" "al2023_ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

# Key Pair — из уже существующего ПУБЛИЧНОГО ключа пользователя (см.
# variables.tf::ssh_public_key_path). Terraform приватный ключ не создаёт и
# не хранит — им управляет только тот, кто запускает apply/ansible, как и
# остальными секретами проекта.
resource "aws_key_pair" "main" {
  key_name   = "${var.project_name}-key"
  public_key = file(var.ssh_public_key_path)

  tags = {
    Name = "${var.project_name}-key"
  }
}

resource "aws_instance" "frontend" {
  ami                    = data.aws_ssm_parameter.al2023_ami.value
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
  ami                    = data.aws_ssm_parameter.al2023_ami.value
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
  ami                    = data.aws_ssm_parameter.al2023_ami.value
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
