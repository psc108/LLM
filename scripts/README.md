# Terraform LLM Assistant Utility Scripts

This folder contains utility scripts to manage the Terraform LLM Assistant container.

## Available Scripts

### `stop_all_containers.sh`

This script stops and optionally removes all running Docker containers on your system.

Usage:
```bash
./stop_all_containers.sh
```

### `free_port.sh`

This script identifies and stops Docker containers using specific ports. By default, it checks ports 5000, 8080, and 11434.

Usage:
```bash
# Check default ports (5000, 8080, 11434)
./free_port.sh

# Check specific ports
./free_port.sh 3000 5000 8000
```

### `restart_assistant.sh`

This script performs a complete restart of the Terraform LLM Assistant:
1. Checks for and resolves port conflicts
2. Stops any existing Terraform LLM Assistant container
3. Starts a fresh container with the correct port configuration

Usage:
```bash
./restart_assistant.sh
```

Customize the environment variables for more control:
```bash
CONTAINER_ENGINE=podman PUBLISH_PORT=9090 OLLAMA_PORT=11435 ./restart_assistant.sh
```

## Troubleshooting Port Issues

If you're seeing port conflicts (especially on port 5000 or 8080), run the `free_port.sh` script to identify and stop containers using those ports.

For a complete fresh start, you can use the `restart_assistant.sh` script which handles port conflicts automatically.

## Making Scripts Executable

If you encounter permission issues when running the scripts, make them executable with:

```bash
chmod +x *.sh
```
