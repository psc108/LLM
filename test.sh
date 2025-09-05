#!/usr/bin/env python3

print("=== Testing Flask App Dependencies ===")

# Test system info first
import sys
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")

# Test standard library imports (these should always work)
standard_modules = ['os', 'logging', 'time', 'subprocess', 'json', 'threading', 'platform']

print("\nTesting standard library modules:")
for module_name in standard_modules:
    try:
        __import__(module_name)
        print(f"✅ {module_name}")
    except ImportError as e:
        print(f"❌ {module_name}: {e}")

# Test third-party modules
print("\nTesting third-party modules:")
third_party_modules = ['flask', 'requests', 'psutil', 'dotenv']

for module_name in third_party_modules:
    try:
        module = __import__(module_name)
        print(f"✅ {module_name}")
    except ImportError as e:
        print(f"❌ {module_name}: {e}")

print("\n=== Creating Simple Flask App ===")

try:
    from flask import Flask, jsonify
    import os

    app = Flask(__name__)

    @app.route('/')
    def hello():
        return jsonify({
            'message': 'Flask app is working!',
            'python_version': sys.version,
            'cwd': os.getcwd()
        })

    print("✅ Flask app created successfully!")
    print("Starting server on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)

except Exception as e:
    print(f"❌ Error creating Flask app: {e}")
    import traceback
    traceback.print_exc()