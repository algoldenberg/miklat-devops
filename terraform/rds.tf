# RDS PostgreSQL — та же версия (16), что и в локальном docker-compose
# (postgres:16 + PostGIS), чтобы поведение СУБД не отличалось между
# окружениями. PostGIS extension включается вручную одной командой
# (`CREATE EXTENSION postgis;`) уже внутри самой БД при первом деплое через
# Ansible — RDS этого через Terraform не делает.

resource "aws_db_instance" "main" {
  identifier     = "${var.project_name}-db"
  engine         = "postgres"
  engine_version = var.db_engine_version
  instance_class = var.db_instance_class

  allocated_storage = var.db_allocated_storage_gb
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  # ОБНОВЛЕНО в Фазе 3 (Задание 3): изначально было `false` — несмотря на то,
  # что подсеть технически "публичная" (см. обоснование в network.tf), сама
  # RDS не получала публичный IP, полагаясь на то, что backend/worker и так
  # внутри VPC. Но k3s (mbdai) живёт СНАРУЖИ VPC — при publicly_accessible=
  # false DNS-имя RDS резолвится ТОЛЬКО в приватный IP, недостижимый снаружи
  # вообще никаким SG-правилом (это обнаружено на реальном деплое: правило
  # в aws_security_group.rds для IP mbdai уже было применено, но TCP-подключение
  # с mbdai всё равно падало по таймауту — потому что пакетам физически
  # некуда маршрутизироваться до приватного IP без VPN/peering).
  # Осознанный компромисс (задокументировать в README, по аналогии с "no NAT
  # Gateway" и NodePort-Ingress): переключаем на `true`, чтобы у RDS появился
  # публичный IP, но реальная защита остаётся на security group — она и так
  # уже сужена до backend/worker SG (изнутри VPC) + один конкретный /32 IP
  # mbdai (снаружи), а не 0.0.0.0/0.
  publicly_accessible = true

  # Без этого флага AWS применил бы publicly_accessible не сразу, а только
  # в следующее maintenance window (см. поведение aws_db_instance без
  # apply_immediately) — для учебного стенда это не нужно, изменение должно
  # подействовать сразу после terraform apply.
  apply_immediately = true

  # multi-AZ намеренно выключен — учебный стенд с одним стейджем, лишние
  # деньги без реальной надобности (нет продакшен-SLA, который нужно держать).
  multi_az = false

  # skip_final_snapshot = true — проект будет полностью уничтожаться
  # (`terraform destroy`) после сдачи задания, финальный снапшот тут не нужен
  # и только оставлял бы платный ресурс, который потом пришлось бы отдельно
  # чистить руками.
  skip_final_snapshot = true

  backup_retention_period = 1

  tags = {
    Name = "${var.project_name}-db"
  }
}