# Security Groups — по одной на роль, минимальные правила (принцип
# least-privilege, тот же, что уже применён к IAM в Фазе 1).
#
# Распределение сервисов по трём EC2 (см. ec2.tf) — то же деление, что задаёт
# сам план (frontend/backend/worker) и структура Ansible-playbook'ов
# (deploy-backend.yml / deploy-worker.yml):
#   - frontend: nginx + собранная статика React (порт 80/443 наружу).
#   - backend:  miklat-gateway (8000, единственная точка входа для frontend),
#               miklat-service (8001), miklat-comments (8002).
#   - worker:   miklat-routes (8003), miklat-walking-routes (8004),
#               miklat-photos (8005), OSRM (5000) — более тяжёлые/фоновые
#               сервисы и то, что напрямую говорит с S3/SNS.
# gateway на backend обращается напрямую к worker-портам (та же логика
# resolve_target, что и в docker-compose, только по приватным IP вместо
# DNS-имён контейнеров).

resource "aws_security_group" "frontend" {
  name        = "${var.project_name}-frontend-sg"
  description = "HTTP/HTTPS из интернета на frontend (nginx), SSH только с доверенного IP"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH (только доверенный IP)"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_allowed_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-frontend-sg"
  }
}

resource "aws_security_group" "backend" {
  name        = "${var.project_name}-backend-sg"
  description = "gateway/service/comments — доступ только от frontend (и друг друга), SSH только с доверенного IP"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "miklat-gateway (8000) — только от frontend"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.frontend.id]
  }

  ingress {
    description = "SSH (только доверенный IP)"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_allowed_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-backend-sg"
  }
}

resource "aws_security_group" "worker" {
  name        = "${var.project_name}-worker-sg"
  description = "routes/walking-routes/photos + OSRM — доступ только от backend (gateway туда проксирует), SSH только с доверенного IP"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "miklat-routes (8003) — только от backend"
    from_port       = 8003
    to_port         = 8003
    protocol        = "tcp"
    security_groups = [aws_security_group.backend.id]
  }

  ingress {
    description     = "miklat-walking-routes (8004) — только от backend"
    from_port       = 8004
    to_port         = 8004
    protocol        = "tcp"
    security_groups = [aws_security_group.backend.id]
  }

  ingress {
    description     = "miklat-photos (8005) — только от backend"
    from_port       = 8005
    to_port         = 8005
    protocol        = "tcp"
    security_groups = [aws_security_group.backend.id]
  }

  ingress {
    description = "SSH (только доверенный IP)"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_allowed_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-worker-sg"
  }
}

# Отдельная SG у самой worker-группы на 5000 (OSRM) не нужна отдельным
# ingress-правилом наружу — OSRM вызывается локально на том же хосте, что и
# miklat-routes/miklat-walking-routes (аналог docker-compose, где OSRM был
# отдельным контейнером в той же сети) — если понадобится дать доступ к нему
# ещё откуда-то, правило добавляется сюда же явным Sid, а не общим 0.0.0.0/0.

resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds-sg"
  description = "PostgreSQL — доступ только от backend и worker, никогда из интернета"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "PostgreSQL от backend"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.backend.id]
  }

  ingress {
    description     = "PostgreSQL от worker"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.worker.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-rds-sg"
  }
}
