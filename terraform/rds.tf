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

  # НЕ публичный доступ — несмотря на то, что подсеть технически "публичная"
  # (см. обоснование в network.tf), сама RDS не получает публичный IP, а SG
  # и так пускает только backend/worker. Двойная защита, а не полагание на
  # что-то одно.
  publicly_accessible = false

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
