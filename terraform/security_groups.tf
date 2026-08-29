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
  name = "${var.project_name}-frontend-sg"
  # Описания (description) у SG и у ingress/egress-правил AWS принимает
  # только ASCII (регулярка на стороне API не пропускает кириллицу) — здесь
  # и ниже по файлу они на английском, а объяснения по-русски остаются в
  # обычных комментариях (#).
  description = "HTTP/HTTPS from internet to frontend (nginx), SSH only from trusted IP"
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
    description = "SSH (trusted IP only)"
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
  description = "gateway/service/comments - access only from frontend, SSH only from trusted IP"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "miklat-gateway (8000) - from frontend only"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.frontend.id]
  }

  ingress {
    description = "SSH (trusted IP only)"
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
  description = "routes/walking-routes/photos + OSRM - access only from backend, SSH only from trusted IP"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "miklat-routes (8003) - from backend only"
    from_port       = 8003
    to_port         = 8003
    protocol        = "tcp"
    security_groups = [aws_security_group.backend.id]
  }

  ingress {
    description     = "miklat-walking-routes (8004) - from backend only"
    from_port       = 8004
    to_port         = 8004
    protocol        = "tcp"
    security_groups = [aws_security_group.backend.id]
  }

  ingress {
    description     = "miklat-photos (8005) - from backend only"
    from_port       = 8005
    to_port         = 8005
    protocol        = "tcp"
    security_groups = [aws_security_group.backend.id]
  }

  ingress {
    description = "SSH (trusted IP only)"
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
  description = "PostgreSQL - access only from backend and worker, never from the internet"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "PostgreSQL from backend"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.backend.id]
  }

  ingress {
    description     = "PostgreSQL from worker"
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
