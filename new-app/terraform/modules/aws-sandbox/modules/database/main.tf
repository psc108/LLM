# Database Module

# Security Group for RDS
resource "aws_security_group" "rds" {
  name        = "${var.name_prefix}-rds-sg"
  description = "Security group for RDS instances"
  vpc_id      = var.vpc_id

  ingress {
    description = "MySQL from VPC"
    from_port   = 3306
    to_port     = 3306
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  ingress {
    description = "PostgreSQL from VPC"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-rds-sg"
  })
}

# RDS Subnet Group
resource "aws_db_subnet_group" "main" {
  count       = var.create_rds_examples && length(var.database_subnet_ids) > 1 ? 1 : 0
  name        = "${var.name_prefix}-db-subnet-group"
  description = "Subnet group for RDS instances"
  subnet_ids  = var.database_subnet_ids

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-db-subnet-group"
  })
}

# KMS Key for RDS encryption
resource "aws_kms_key" "rds" {
  count                   = var.create_rds_examples ? 1 : 0
  description             = "KMS key for RDS encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-rds-kms-key"
  })
}

resource "aws_kms_alias" "rds" {
  count         = var.create_rds_examples ? 1 : 0
  name          = "alias/${var.name_prefix}-rds-key"
  target_key_id = aws_kms_key.rds[0].key_id
}

# Generate random passwords for RDS instances
resource "random_password" "mysql" {
  count   = var.create_rds_examples ? 1 : 0
  length  = 16
  special = false
}

resource "random_password" "postgres" {
  count   = var.create_rds_examples ? 1 : 0
  length  = 16
  special = false
}

# MySQL RDS Instance
resource "aws_db_instance" "mysql" {
  count                  = var.create_rds_examples && length(var.database_subnet_ids) > 1 ? 1 : 0
  identifier             = "${var.name_prefix}-mysql"
  engine                 = "mysql"
  engine_version         = "8.0"
  instance_class         = var.rds_instance_class
  allocated_storage      = 20
  max_allocated_storage  = 100
  storage_type           = "gp3"
  storage_encrypted      = true
  kms_key_id             = aws_kms_key.rds[0].arn
  db_name                = "sandbox"
  username               = "admin"
  password               = random_password.mysql[0].result
  parameter_group_name   = "default.mysql8.0"
  db_subnet_group_name   = aws_db_subnet_group.main[0].name
  vpc_security_group_ids = [aws_security_group.rds.id]
  skip_final_snapshot    = true
  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:30-sun:05:30"
  deletion_protection    = false
  copy_tags_to_snapshot  = true
  publicly_accessible    = false
  multi_az               = false
  apply_immediately      = true
  monitoring_interval    = 60
  monitoring_role_arn    = aws_iam_role.rds_monitoring[0].arn
  enabled_cloudwatch_logs_exports = ["audit", "error", "general", "slowquery"]

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-mysql"
  })
}

# PostgreSQL RDS Instance
resource "aws_db_instance" "postgres" {
  count                  = var.create_rds_examples && length(var.database_subnet_ids) > 1 ? 1 : 0
  identifier             = "${var.name_prefix}-postgres"
  engine                 = "postgres"
  engine_version         = "14"
  instance_class         = var.rds_instance_class
  allocated_storage      = 20
  max_allocated_storage  = 100
  storage_type           = "gp3"
  storage_encrypted      = true
  kms_key_id             = aws_kms_key.rds[0].arn
  db_name                = "sandbox"
  username               = "admin"
  password               = random_password.postgres[0].result
  parameter_group_name   = "default.postgres14"
  db_subnet_group_name   = aws_db_subnet_group.main[0].name
  vpc_security_group_ids = [aws_security_group.rds.id]
  skip_final_snapshot    = true
  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:30-sun:05:30"
  deletion_protection    = false
  copy_tags_to_snapshot  = true
  publicly_accessible    = false
  multi_az               = false
  apply_immediately      = true
  monitoring_interval    = 60
  monitoring_role_arn    = aws_iam_role.rds_monitoring[0].arn
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-postgres"
  })
}

# IAM role for enhanced RDS monitoring
resource "aws_iam_role" "rds_monitoring" {
  count = var.create_rds_examples ? 1 : 0
  name  = "${var.name_prefix}-rds-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-rds-monitoring-role"
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  count      = var.create_rds_examples ? 1 : 0
  role       = aws_iam_role.rds_monitoring[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# DynamoDB Tables
resource "aws_dynamodb_table" "basic" {
  count        = var.create_dynamodb_examples ? 1 : 0
  name         = "${var.name_prefix}-basic-table"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-basic-table"
  })
}

resource "aws_dynamodb_table" "advanced" {
  count        = var.create_dynamodb_examples ? 1 : 0
  name         = "${var.name_prefix}-advanced-table"
  billing_mode = "PROVISIONED"
  read_capacity  = 5
  write_capacity = 5
  hash_key     = "userId"
  range_key    = "gameTitle"

  attribute {
    name = "userId"
    type = "S"
  }

  attribute {
    name = "gameTitle"
    type = "S"
  }

  attribute {
    name = "topScore"
    type = "N"
  }

  global_secondary_index {
    name               = "GameTitleIndex"
    hash_key           = "gameTitle"
    range_key          = "topScore"
    write_capacity     = 5
    read_capacity      = 5
    projection_type    = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-advanced-table"
  })
}

resource "aws_dynamodb_table" "ttl_example" {
  count        = var.create_dynamodb_examples ? 1 : 0
  name         = "${var.name_prefix}-ttl-table"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  ttl {
    attribute_name = "expiryTime"
    enabled        = true
  }

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-ttl-table"
  })
}

# Example items for DynamoDB tables
resource "aws_dynamodb_table_item" "basic_item1" {
  count      = var.create_dynamodb_examples ? 1 : 0
  table_name = aws_dynamodb_table.basic[0].name
  hash_key   = aws_dynamodb_table.basic[0].hash_key

  item = jsonencode({
    id = { S = "item-1" }
    name = { S = "Example Item 1" }
    description = { S = "This is an example item in the basic table" }
    created_at = { S = timestamp() }
    active = { BOOL = true }
    count = { N = "42" }
  })
}

resource "aws_dynamodb_table_item" "basic_item2" {
  count      = var.create_dynamodb_examples ? 1 : 0
  table_name = aws_dynamodb_table.basic[0].name
  hash_key   = aws_dynamodb_table.basic[0].hash_key

  item = jsonencode({
    id = { S = "item-2" }
    name = { S = "Example Item 2" }
    description = { S = "This is another example item in the basic table" }
    created_at = { S = timestamp() }
    active = { BOOL = false }
    count = { N = "99" }
  })
}

resource "aws_dynamodb_table_item" "advanced_item1" {
  count      = var.create_dynamodb_examples ? 1 : 0
  table_name = aws_dynamodb_table.advanced[0].name
  hash_key   = aws_dynamodb_table.advanced[0].hash_key
  range_key  = aws_dynamodb_table.advanced[0].range_key

  item = jsonencode({
    userId = { S = "user-1" }
    gameTitle = { S = "Galaxy Invaders" }
    topScore = { N = "5842" }
    wins = { N = "17" }
    losses = { N = "5" }
    lastPlayed = { S = timestamp() }
  })
}

resource "aws_dynamodb_table_item" "advanced_item2" {
  count      = var.create_dynamodb_examples ? 1 : 0
  table_name = aws_dynamodb_table.advanced[0].name
  hash_key   = aws_dynamodb_table.advanced[0].hash_key
  range_key  = aws_dynamodb_table.advanced[0].range_key

  item = jsonencode({
    userId = { S = "user-2" }
    gameTitle = { S = "Comet Chase" }
    topScore = { N = "1024" }
    wins = { N = "5" }
    losses = { N = "12" }
    lastPlayed = { S = timestamp() }
  })
}
