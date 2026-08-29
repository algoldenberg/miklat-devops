# IAM для доступа приложения (backend + worker EC2) к S3/SNS.
#
# Решение, отличное от Фазы 1: там был отдельный IAM-пользователь
# (`miklat-app-dev`) со статическим access key в `.env` — рабочий вариант для
# докер-контейнеров на своей машине, но на "настоящих" EC2 правильнее
# instance profile (IAM Role, прикреплённая к инстансу) — приложению вообще
# не нужно видеть access key/secret, credentials сами подставляются AWS
# через instance metadata и автоматически ротируются. Тот же принцип
# least-privilege, что и раньше, просто более подходящий механизм для EC2
# (на K8s/Фазе 3 будет ещё один механизм — см. заметку про IRSA в
# miklat-progress.md).

resource "aws_iam_role" "app" {
  name = "${var.project_name}-app-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "ec2.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-app-role"
  }
}

# Права — минимально необходимые, тот же набор, что и в
# `miklat-app-dev-policy.json` из Фазы 1 (включая s3:ListBucket и
# sns:GetTopicAttributes, добавленные туда же по факту, что они нужны
# эндпоинту /ready — см. соответствующую заметку в miklat-progress.md).
resource "aws_iam_policy" "app" {
  name        = "${var.project_name}-app-policy"
  description = "Минимальные права приложения miklat на S3 (фото) и SNS (уведомления)"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "PhotosObjectAccess"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
        ]
        Resource = "${aws_s3_bucket.photos.arn}/*"
      },
      {
        Sid      = "PhotosBucketReadyCheck"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.photos.arn
      },
      {
        Sid      = "PublishNotifications"
        Effect   = "Allow"
        Action   = "sns:Publish"
        Resource = aws_sns_topic.notifications.arn
      },
      {
        Sid      = "TopicReadyCheck"
        Effect   = "Allow"
        Action   = "sns:GetTopicAttributes"
        Resource = aws_sns_topic.notifications.arn
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "app" {
  role       = aws_iam_role.app.name
  policy_arn = aws_iam_policy.app.arn
}

resource "aws_iam_instance_profile" "app" {
  name = "${var.project_name}-app-instance-profile"
  role = aws_iam_role.app.name
}
