#!/usr/bin/env python3

import os
import sys
import subprocess
import textwrap

def check_terraform_installed():
    """Check if terraform is installed and accessible in PATH"""
    try:
        result = subprocess.run(
            ['terraform', '--version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        if result.returncode == 0:
            version = result.stdout.splitlines()[0] if result.stdout else 'Unknown version'
            print(f"✅ Terraform is installed: {version}")
            return True
        else:
            print("❌ Terraform is installed but returned an error:")
            print(result.stderr)
            return False
    except FileNotFoundError:
        print("❌ Terraform is not installed or not in PATH")
        return False

def print_installation_instructions():
    """Print installation instructions for Terraform"""
    instructions = """
    Please install Terraform by following the instructions below:

    Linux:
    ```
    wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor | sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg
    echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
    sudo apt update && sudo apt install terraform
    ```

    macOS (with Homebrew):
    ```
    brew tap hashicorp/tap
    brew install hashicorp/tap/terraform
    ```

    Windows (with Chocolatey):
    ```
    choco install terraform
    ```

    For more information, visit: https://learn.hashicorp.com/tutorials/terraform/install-cli
    """
    print(textwrap.dedent(instructions))

def main():
    print("Checking Terraform setup...")
    if not check_terraform_installed():
        print_installation_instructions()
        sys.exit(1)

    # Additional checks could be added here
    print("All setup requirements met!")
    sys.exit(0)

if __name__ == "__main__":
    main()
