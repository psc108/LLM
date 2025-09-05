import os
import logging
import time
from flask import Flask, render_template, request, jsonify, send_from_directory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
logger.info("Starting LLM Assistant application")

# Create Flask app
app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Get model configuration
active_model = os.environ.get('MODEL_NAME', 'codellama:13b-instruct')
ollama_host = os.environ.get('OLLAMA_HOST', 'localhost')
ollama_port = os.environ.get('OLLAMA_PORT', '11434')

@app.route('/')
def index():
    """Serve the main application page"""
    return render_template('index.html', active_model=active_model)

@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('static', path)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring the application and LLM status"""
    try:
        import requests
        import platform
        import psutil

        # System information
        system_info = {
            'python_version': platform.python_version(),
            'platform': platform.platform(),
            'cpu_percent': psutil.cpu_percent(interval=0.1),
            'memory_percent': psutil.virtual_memory().percent
        }

        # Check Ollama status
        ollama_status = {
            'running': False,
            'models': [],
            'version': 'unknown'
        }

        try:
            # Check if Ollama is running and get available models
            response = requests.get(
                f"http://{ollama_host}:{ollama_port}/api/tags",
                timeout=2
            )
            if response.status_code == 200:
                ollama_status['running'] = True
                models_data = response.json().get('models', [])
                ollama_status['models'] = [model.get('name') for model in models_data]

                # Try to get version
                try:
                    version_response = requests.get(
                        f"http://{ollama_host}:{ollama_port}/api/version",
                        timeout=1
                    )
                    if version_response.status_code == 200:
                        ollama_status['version'] = version_response.json().get('version', 'unknown')
                except Exception as e:
                    logger.warning(f"Failed to get Ollama version: {e}")
        except Exception as e:
            logger.warning(f"Ollama connection error: {e}")

        # Check if the active model is available
        model_base_name = active_model.split(':')[0] if ':' in active_model else active_model
        model_available = any(model.startswith(model_base_name) for model in ollama_status['models'])

        # Determine overall status
        if not ollama_status['running']:
            status = "error"
        elif not model_available:
            status = "loading"
        else:
            status = "ok"

        # Always return 200 status code for the frontend
        return jsonify({
            'status': 'ok',  # Always return 'ok' for the frontend
            'actual_status': status,  # The real status
            'model': active_model,
            'ollama': ollama_status,
            'system': system_info,
            'timestamp': time.time()
        })
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            'status': 'ok',  # Still return 'ok' for the frontend
            'actual_status': 'error',
            'error': str(e),
            'timestamp': time.time()
        })

@app.route('/api/chat', methods=['POST'])
def chat():
    """Process chat messages and get responses from the LLM"""
    try:
        start_time = time.time()
        data = request.get_json()
        message = data.get('message', '').strip()

        if not message:
            return jsonify({
                'success': False,
                'error': 'Message is empty'
            })

        # Check if Ollama is running
        import requests
        ollama_running = False

        try:
            response = requests.get(
                f"http://{ollama_host}:{ollama_port}/api/tags",
                timeout=2
            )
            ollama_running = response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama connection error: {e}")

        # If Ollama is running, use it to generate a response
        if ollama_running:
            try:
                # Create a system prompt for infrastructure as code
                system_prompt = """
                You are an expert in infrastructure as code, specializing in Terraform, AWS, and cloud architecture. 
                Provide accurate, secure, and well-documented solutions following best practices. 
                When showing code examples:
                - Always wrap code in triple backticks with the appropriate language specifier (```terraform, ```json, etc.).
                - For Terraform code use ```terraform or ```hcl
                - Include clear comments in your code examples
                - Focus on security, maintainability, and following cloud best practices
                - Be concise but thorough in your explanations
                """

                # Format the prompt for Ollama
                formatted_prompt = f"{system_prompt}\n\nUser: {message}\n\nAssistant:"

                # Call the Ollama API
                response = requests.post(
                    f"http://{ollama_host}:{ollama_port}/api/generate",
                    json={
                        'model': active_model,
                        'prompt': formatted_prompt,
                        'stream': False,
                        'options': {
                            'temperature': 0.1,
                            'top_p': 0.9,
                            'top_k': 40
                        }
                    },
                    timeout=60
                )

                if response.status_code == 200:
                    result = response.json()
                    response_time = time.time() - start_time

                    return jsonify({
                        'success': True,
                        'response': result.get('response', ''),
                        'model': active_model,
                        'response_time': round(response_time, 2)
                    })
                else:
                    logger.error(f"Ollama API returned status code: {response.status_code}")
                    return jsonify({
                        'success': False,
                        'error': f"LLM service returned an error: {response.status_code}",
                        'response_time': round(time.time() - start_time, 2)
                    })
            except Exception as e:
                logger.error(f"Error calling Ollama API: {e}")
                return jsonify({
                    'success': False,
                    'error': f"Error communicating with LLM service: {str(e)}",
                    'response_time': round(time.time() - start_time, 2)
                })

        # Fallback response when Ollama is not available
        return jsonify({
            'success': True,
            'response': (
                "I received your question about infrastructure, but the LLM service is currently unavailable. "
                "Please ensure Ollama is running and the correct model is loaded. "
                f"Expected model: {active_model}"
            ),
            'response_time': round(time.time() - start_time, 2)
        })
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'response_time': 0
        })

# Run the application
if __name__ == '__main__':
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

    logger.info(f"Starting server on {host}:{port} (debug={debug})")
    app.run(host=host, port=port, debug=debug)
