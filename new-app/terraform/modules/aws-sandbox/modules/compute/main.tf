# Compute Module

data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Create Key Pair if enabled
resource "aws_key_pair" "sandbox" {
  count      = var.create_key_pair && var.ssh_public_key != "" ? 1 : 0
  key_name   = var.key_name != "" ? var.key_name : "${var.name_prefix}-key"
  public_key = var.ssh_public_key

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-key"
  })
}

# Security Group for bastion host
resource "aws_security_group" "bastion" {
  count       = var.create_bastion ? 1 : 0
  name        = "${var.name_prefix}-bastion-sg"
  description = "Security group for bastion host"
  vpc_id      = var.vpc_id

  # SSH access
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "SSH from anywhere (for demo only - restrict in production)"
  }

  # ICMP (ping)
  ingress {
    from_port   = -1
    to_port     = -1
    protocol    = "icmp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "ICMP from anywhere"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-bastion-sg"
  })
}

# Security Group for internal instances
resource "aws_security_group" "internal" {
  name        = "${var.name_prefix}-internal-sg"
  description = "Security group for internal instances"
  vpc_id      = var.vpc_id

  # SSH from bastion
  ingress {
    from_port       = 22
    to_port         = 22
    protocol        = "tcp"
    security_groups = var.create_bastion ? [aws_security_group.bastion[0].id] : []
    description     = "SSH from bastion"
  }

  # HTTP
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "HTTP from within VPC"
  }

  # HTTPS
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "HTTPS from within VPC"
  }

  # Application port
  ingress {
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "Application port from within VPC"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-internal-sg"
  })
}

# IAM Role for instances with SSM access
resource "aws_iam_role" "ec2_ssm" {
  name = "${var.name_prefix}-ec2-ssm-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-ec2-ssm-role"
  })
}

resource "aws_iam_role_policy_attachment" "ssm_managed_instance" {
  role       = aws_iam_role.ec2_ssm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "ssm_patch_management" {
  role       = aws_iam_role.ec2_ssm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMPatchAssociation"
}

resource "aws_iam_instance_profile" "ec2_ssm" {
  name = "${var.name_prefix}-ec2-ssm-profile"
  role = aws_iam_role.ec2_ssm.name

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-ec2-ssm-profile"
  })
}

# Bastion host in public subnet
resource "aws_instance" "bastion" {
  count = var.create_bastion ? 1 : 0

  ami                         = data.aws_ami.amazon_linux.id
  instance_type               = var.instance_type
  subnet_id                   = var.public_subnet_ids[0]
  vpc_security_group_ids      = [aws_security_group.bastion[0].id]
  associate_public_ip_address = true
  key_name                    = var.create_key_pair ? aws_key_pair.sandbox[0].key_name : var.key_name
  iam_instance_profile        = aws_iam_instance_profile.ec2_ssm.name

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 20
    encrypted             = true
    delete_on_termination = true
  }

  user_data = <<-EOF
    #!/bin/bash
    echo "Installing utilities..."
    dnf update -y
    dnf install -y amazon-ssm-agent jq htop vim-enhanced git
    systemctl enable amazon-ssm-agent
    systemctl start amazon-ssm-agent

    # Add banner
    echo "==============================================" > /etc/motd
    echo "  AWS Terraform Sandbox - Bastion Host" >> /etc/motd
    echo "  Created via Terraform" >> /etc/motd
    echo "==============================================" >> /etc/motd

    # Setup hostname
    hostnamectl set-hostname ${var.name_prefix}-bastion

    echo "Bastion host setup completed"
  EOF

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-bastion"
  })
}

# EC2 instances in private subnets
resource "aws_instance" "private" {
  count = var.create_ec2_examples ? length(var.private_subnet_ids) : 0

  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  subnet_id              = var.private_subnet_ids[count.index]
  vpc_security_group_ids = [aws_security_group.internal.id]
  key_name               = var.create_key_pair ? aws_key_pair.sandbox[0].key_name : var.key_name
  iam_instance_profile   = aws_iam_instance_profile.ec2_ssm.name

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 20
    encrypted             = true
    delete_on_termination = true
  }

  user_data = <<-EOF
    #!/bin/bash
    echo "Installing utilities and web server..."
    dnf update -y
    dnf install -y amazon-ssm-agent jq htop vim-enhanced git nginx
    systemctl enable amazon-ssm-agent nginx
    systemctl start amazon-ssm-agent nginx

    # Create a simple web page
    cat <<'EOT' > /usr/share/nginx/html/index.html
    <!DOCTYPE html>
    <html>
    <head>
        <title>AWS Terraform Sandbox - Private Instance ${count.index + 1}</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1 { color: #232f3e; }
            .info { background-color: #f8f8f8; padding: 20px; border-radius: 5px; }
        </style>
    </head>
    <body>
        <h1>AWS Terraform Sandbox - Private Instance ${count.index + 1}</h1>
        <div class="info">
            <p>This server was created with Terraform</p>
            <p>Instance ID: <script>document.write(fetch('http://169.254.169.254/latest/meta-data/instance-id').then(r => r.text()).then(id => document.write(id)));</script></p>
            <p>Private IP: <script>document.write(fetch('http://169.254.169.254/latest/meta-data/local-ipv4').then(r => r.text()).then(ip => document.write(ip)));</script></p>
            <p>AZ: <script>document.write(fetch('http://169.254.169.254/latest/meta-data/placement/availability-zone').then(r => r.text()).then(az => document.write(az)));</script></p>
        </div>
    </body>
    </html>
    EOT

    # Setup hostname
    hostnamectl set-hostname ${var.name_prefix}-private-${count.index + 1}

    echo "Private instance setup completed"
  EOF

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-private-${count.index + 1}"
  })
}

# Launch template for ASG
resource "aws_launch_template" "web_app" {
  count = var.create_asg_examples ? 1 : 0

  name_prefix            = "${var.name_prefix}-web-app-"
  image_id               = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  key_name               = var.create_key_pair ? aws_key_pair.sandbox[0].key_name : var.key_name
  vpc_security_group_ids = [aws_security_group.internal.id]
  user_data              = base64encode(<<-EOF
    #!/bin/bash
    echo "Installing utilities and web server..."
    dnf update -y
    dnf install -y amazon-ssm-agent jq htop vim-enhanced git nginx
    systemctl enable amazon-ssm-agent nginx
    systemctl start amazon-ssm-agent nginx

    # Create a simple web page
    cat <<'EOT' > /usr/share/nginx/html/index.html
    <!DOCTYPE html>
    <html>
    <head>
        <title>AWS Terraform Sandbox - ASG Instance</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1 { color: #232f3e; }
            .info { background-color: #f8f8f8; padding: 20px; border-radius: 5px; }
        </style>
    </head>
    <body>
        <h1>AWS Terraform Sandbox - ASG Instance</h1>
        <div class="info">
            <p>This server was created by an Auto Scaling Group with Terraform</p>
            <p>Instance ID: <script>document.write(fetch('http://169.254.169.254/latest/meta-data/instance-id').then(r => r.text()).then(id => document.write(id)));</script></p>
            <p>Private IP: <script>document.write(fetch('http://169.254.169.254/latest/meta-data/local-ipv4').then(r => r.text()).then(ip => document.write(ip)));</script></p>
            <p>AZ: <script>document.write(fetch('http://169.254.169.254/latest/meta-data/placement/availability-zone').then(r => r.text()).then(az => document.write(az)));</script></p>
        </div>
    </body>
    </html>
    EOT

    # Setup hostname
    hostnamectl set-hostname ${var.name_prefix}-asg-web

    echo "ASG instance setup completed"
  EOF
  )

  iam_instance_profile {
    name = aws_iam_instance_profile.ec2_ssm.name
  }

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = 20
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  tag_specifications {
    resource_type = "instance"
    tags = merge(var.common_tags, {
      Name = "${var.name_prefix}-asg-web"
    })
  }

  tag_specifications {
    resource_type = "volume"
    tags = merge(var.common_tags, {
      Name = "${var.name_prefix}-asg-web-volume"
    })
  }

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-asg-web-lt"
  })
}

# Auto Scaling Group
resource "aws_autoscaling_group" "web_app" {
  count = var.create_asg_examples ? 1 : 0

  name                      = "${var.name_prefix}-web-app-asg"
  min_size                  = 1
  max_size                  = 3
  desired_capacity          = 2
  vpc_zone_identifier       = var.private_subnet_ids
  health_check_type         = "EC2"
  health_check_grace_period = 300
  force_delete              = true

  launch_template {
    id      = aws_launch_template.web_app[0].id
    version = "$Latest"
  }

  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 50
    }
  }

  dynamic "tag" {
    for_each = merge(var.common_tags, {
      Name = "${var.name_prefix}-asg-web"
    })

    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Scaling policies
resource "aws_autoscaling_policy" "scale_up" {
  count                  = var.create_asg_examples ? 1 : 0
  name                   = "${var.name_prefix}-scale-up"
  autoscaling_group_name = aws_autoscaling_group.web_app[0].name
  adjustment_type        = "ChangeInCapacity"
  scaling_adjustment     = 1
  cooldown               = 300
}

resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  count               = var.create_asg_examples ? 1 : 0
  alarm_name          = "${var.name_prefix}-high-cpu"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 120
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Scale up when CPU exceeds 80% for 4 minutes"
  alarm_actions       = [aws_autoscaling_policy.scale_up[0].arn]
  dimensions = {
    AutoScalingGroupName = aws_autoscaling_group.web_app[0].name
  }

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-high-cpu-alarm"
  })
}

resource "aws_autoscaling_policy" "scale_down" {
  count                  = var.create_asg_examples ? 1 : 0
  name                   = "${var.name_prefix}-scale-down"
  autoscaling_group_name = aws_autoscaling_group.web_app[0].name
  adjustment_type        = "ChangeInCapacity"
  scaling_adjustment     = -1
  cooldown               = 300
}

resource "aws_cloudwatch_metric_alarm" "low_cpu" {
  count               = var.create_asg_examples ? 1 : 0
  alarm_name          = "${var.name_prefix}-low-cpu"
  comparison_operator = "LessThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 120
  statistic           = "Average"
  threshold           = 20
  alarm_description   = "Scale down when CPU is below 20% for 4 minutes"
  alarm_actions       = [aws_autoscaling_policy.scale_down[0].arn]
  dimensions = {
    AutoScalingGroupName = aws_autoscaling_group.web_app[0].name
  }

  tags = merge(var.common_tags, {
    Name = "${var.name_prefix}-low-cpu-alarm"
  })
}
