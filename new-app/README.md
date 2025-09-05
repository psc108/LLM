# LLM Assistant

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
