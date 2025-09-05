# Storage Module

# Generate a random suffix for globally unique bucket names
resource "random_string" "bucket_suffix" {
  length  = 8
  special = false
  upper   = false
}

# S3 Bucket for static website hosting
resource "aws_s3_bucket" "static_website" {
  count         = var.create_s3_examples ? 1 : 0
  bucket        = "${var.name_prefix}-website-${random_string.bucket_suffix.result}"
  force_destroy = true

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-website-bucket"
  })
}

resource "aws_s3_bucket_website_configuration" "static_website" {
  count  = var.create_s3_examples ? 1 : 0
  bucket = aws_s3_bucket.static_website[0].id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "error.html"
  }
}

resource "aws_s3_bucket_versioning" "static_website" {
  count  = var.create_s3_examples ? 1 : 0
  bucket = aws_s3_bucket.static_website[0].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "static_website" {
  count  = var.create_s3_examples ? 1 : 0
  bucket = aws_s3_bucket.static_website[0].id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "static_website" {
  count  = var.create_s3_examples ? 1 : 0
  bucket = aws_s3_bucket.static_website[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.static_website[0].arn}/*"
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.static_website]
}

resource "aws_s3_object" "index" {
  count        = var.create_s3_examples ? 1 : 0
  bucket       = aws_s3_bucket.static_website[0].id
  key          = "index.html"
  content_type = "text/html"
  content      = <<-EOF
    <!DOCTYPE html>
    <html>
    <head>
        <title>AWS Terraform Sandbox - S3 Website Example</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }
            h1 { color: #232f3e; }
            .container { max-width: 800px; margin: 0 auto; padding: 20px; }
            .info { background-color: #f8f8f8; padding: 20px; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>AWS Terraform Sandbox - S3 Website Example</h1>
            <div class="info">
                <p>This static website is hosted on Amazon S3 and was created via Terraform.</p>
                <p>The S3 bucket has website hosting enabled with versioning and a public access policy.</p>
                <p><strong>Bucket name:</strong> ${aws_s3_bucket.static_website[0].id}</p>
                <p><strong>Created on:</strong> ${timestamp()}</p>
            </div>
        </div>
    </body>
    </html>
  EOF
}

resource "aws_s3_object" "error" {
  count        = var.create_s3_examples ? 1 : 0
  bucket       = aws_s3_bucket.static_website[0].id
  key          = "error.html"
  content_type = "text/html"
  content      = <<-EOF
    <!DOCTYPE html>
    <html>
    <head>
        <title>Error - AWS Terraform Sandbox</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }
            h1 { color: #d13212; }
            .container { max-width: 800px; margin: 0 auto; padding: 20px; }
            .error { background-color: #f8d7da; color: #721c24; padding: 20px; border-radius: 5px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Error - Page Not Found</h1>
            <div class="error">
                <p>The page you requested could not be found.</p>
                <p>Please return to the <a href="/index.html">home page</a>.</p>
            </div>
        </div>
    </body>
    </html>
  EOF
}

# S3 Bucket for data storage
resource "aws_s3_bucket" "data_store" {
  count         = var.create_s3_examples ? 1 : 0
  bucket        = "${var.name_prefix}-data-${random_string.bucket_suffix.result}"
  force_destroy = true

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-data-bucket"
  })
}

resource "aws_s3_bucket_versioning" "data_store" {
  count  = var.create_s3_examples ? 1 : 0
  bucket = aws_s3_bucket.data_store[0].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "data_store" {
  count  = var.create_s3_examples ? 1 : 0
  bucket = aws_s3_bucket.data_store[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Example folders and objects
resource "aws_s3_object" "data_folder_logs" {
  count  = var.create_s3_examples ? 1 : 0
  bucket = aws_s3_bucket.data_store[0].id
  key    = "logs/"
  source = "/dev/null"  # Empty object for folder
}

resource "aws_s3_object" "data_folder_data" {
  count  = var.create_s3_examples ? 1 : 0
  bucket = aws_s3_bucket.data_store[0].id
  key    = "data/"
  source = "/dev/null"  # Empty object for folder
}

resource "aws_s3_object" "example_config" {
  count        = var.create_s3_examples ? 1 : 0
  bucket       = aws_s3_bucket.data_store[0].id
  key          = "config/settings.json"
  content_type = "application/json"
  content      = jsonencode({
    app_name     = "Terraform Sandbox App"
    version      = "1.0.0"
    environment  = "development"
    debug_mode   = true
    max_retries  = 3
    timeout_ms   = 5000
    created_at   = timestamp()
  })
}

# S3 Bucket with lifecycle policy for logs
resource "aws_s3_bucket" "logs" {
  count         = var.create_s3_examples ? 1 : 0
  bucket        = "${var.name_prefix}-logs-${random_string.bucket_suffix.result}"
  force_destroy = true

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-logs-bucket"
  })
}

resource "aws_s3_bucket_lifecycle_configuration" "logs" {
  count  = var.create_s3_examples ? 1 : 0
  bucket = aws_s3_bucket.logs[0].id

  rule {
    id     = "log-transition-to-ia"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    expiration {
      days = 365
    }
  }

  rule {
    id     = "log-expire-delete-markers"
    status = "Enabled"

    expiration {
      expired_object_delete_marker = true
    }
  }
}

resource "aws_s3_bucket_public_access_block" "logs" {
  count  = var.create_s3_examples ? 1 : 0
  bucket = aws_s3_bucket.logs[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Security group for EFS mount targets
resource "aws_security_group" "efs" {
  count       = var.create_efs_examples ? 1 : 0
  name        = "${var.name_prefix}-efs-sg"
  description = "Security group for EFS mount targets"
  vpc_id      = var.vpc_id

  ingress {
    description = "NFS from VPC"
    from_port   = 2049
    to_port     = 2049
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
    Name = "${var.name_prefix}-efs-sg"
  })
}

# EFS File System
resource "aws_efs_file_system" "main" {
  count            = var.create_efs_examples ? 1 : 0
  creation_token   = "${var.name_prefix}-efs"
  performance_mode = "generalPurpose"
  throughput_mode  = "bursting"
  encrypted        = true

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-efs"
  })
}

# EFS Mount Targets (one per subnet)
resource "aws_efs_mount_target" "main" {
  count           = var.create_efs_examples ? length(var.private_subnet_ids) : 0
  file_system_id  = aws_efs_file_system.main[0].id
  subnet_id       = var.private_subnet_ids[count.index]
  security_groups = [aws_security_group.efs[0].id]
}

# EFS Access Point
resource "aws_efs_access_point" "main" {
  count          = var.create_efs_examples ? 1 : 0
  file_system_id = aws_efs_file_system.main[0].id

  posix_user {
    gid = 1000
    uid = 1000
  }

  root_directory {
    path = "/app"
    creation_info {
      owner_gid   = 1000
      owner_uid   = 1000
      permissions = "0755"
    }
  }

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-efs-ap"
  })
}
