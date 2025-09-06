# Terraform Sandbox Module

## Prerequisites

- Terraform CLI (version 1.0.0 or higher) must be installed
- AWS CLI configured with valid credentials (for actual deployments)

## Setup Instructions

1. Install Terraform CLI by following the official instructions at https://learn.hashicorp.com/tutorials/terraform/install-cli

```bash
# Linux/macOS
wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor | sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform

# macOS with Homebrew
brew tap hashicorp/tap
brew install hashicorp/tap/terraform

# Windows with Chocolatey
choco install terraform
```

2. Verify installation by running:

```bash
terraform version
```

3. For AWS deployments, configure AWS credentials:

```bash
aws configure
```

## Using the Sandbox

This sandbox allows you to experiment with Terraform configurations for AWS resources without affecting production environments. The sandbox provides example configurations for various AWS services like compute, storage, databases, networking, and more.
