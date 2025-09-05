# LLM Assistant
# Terraform LLM Assistant

A Flask web application that provides a conversational interface to interact with language models for Terraform and cloud infrastructure assistance.

## Features

- Interactive chat interface for infrastructure as code assistance
- Integration with Ollama for local LLM inference
- Support for various code llama models
- Responsive UI for desktop and mobile use
- Model status monitoring and management

## Requirements

- Python 3.9+
- Ollama running locally or on a remote server

## Installation

1. Clone the repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set up environment variables (optional):
   - Create a `.env` file with the following variables:

```
MODEL_NAME=codellama:13b-instruct
OLLAMA_HOST=localhost
OLLAMA_PORT=11434
HOST=0.0.0.0
PORT=5000
FLASK_DEBUG=False
SECRET_KEY=your-secret-key
LOGS_DIR=~/terraform-llm-assistant/logs
```

## Usage

1. Start Ollama and pull the required model:

```bash
ollama pull codellama:13b-instruct
```

2. Run the application:

```bash
python app.py
```

3. Access the web interface at http://localhost:5000

## API Endpoints

- `/api/chat` - Send messages to the LLM and get responses
- `/api/model-status` - Check the status of Ollama and loaded models
- `/api/download-model` - Trigger download of a new model
- `/api/status` - Get application and model status

## Development

To run in development mode with auto-reload:

```bash
FLASK_DEBUG=True python app.py
```

## License

MIT
A modern web application for interacting with LLM models through Ollama, focused on infrastructure as code assistance.

## Features

- Clean, responsive UI with modern design principles
- Integration with Ollama for local LLM inference
- Specialized for Terraform, AWS, and infrastructure as code questions
- Code syntax highlighting
- Real-time status monitoring

## Getting Started

### Prerequisites

- Python 3.9+ 
- [Ollama](https://ollama.ai/) installed and running locally
- A compatible LLM model (default: codellama:13b-instruct)

### Installation

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the application:
   ```bash
   python app.py
   ```

### Environment Variables

The application can be configured using the following environment variables:

- `OLLAMA_HOST`: Host where Ollama is running (default: localhost)
- `OLLAMA_PORT`: Port where Ollama is running (default: 11434)
- `MODEL_NAME`: Name of the model to use (default: codellama:13b-instruct)
- `PORT`: Port to run the Flask app (default: 5000)
- `HOST`: Host to run the Flask app (default: 0.0.0.0)
- `FLASK_DEBUG`: Enable debug mode (default: False)
- `SECRET_KEY`: Flask secret key for session security

## Usage

1. Open your browser and navigate to `http://localhost:5000`
2. Ask questions about Terraform, AWS, or infrastructure as code
3. The UI will show example prompts to help you get started

## License

MIT License
