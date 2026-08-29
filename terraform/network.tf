# Сеть: VPC + публичные подсети + Internet Gateway + маршрутизация.
#
# Решение по приватным подсетям/NAT Gateway: сознательно НЕ делаем. Все три
# EC2 (frontend/backend/worker) идут в публичные подсети — NAT Gateway стоит
# денег и добавляет сложность, а реальной изоляции это в рамках учебного
# стенда с одним стейджем не даёт (SG и так ограничивают, кто с кем говорит,
# см. security_groups.tf). RDS при этом всё равно НЕ выставлена наружу — она
# просто внутри той же публичной подсети, но её собственная SG разрешает
# доступ только от backend/worker SG, не из интернета (см. rds.tf) — это и
# есть содержательная защита, а не факт "публичная/приватная подсеть".

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-igw"
  }
}

resource "aws_subnet" "public" {
  count                   = length(var.public_subnet_cidrs)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-public-${var.availability_zones[count.index]}"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.project_name}-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Отдельная subnet group для RDS — требует минимум 2 подсети в разных AZ,
# даже если сам инстанс RDS не multi-AZ (это ограничение самого сервиса).
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = aws_subnet.public[*].id

  tags = {
    Name = "${var.project_name}-db-subnet-group"
  }
}
