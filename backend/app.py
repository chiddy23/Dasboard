"""
JustInsurance Student Dashboard - Flask Application

A multi-tenant SaaS dashboard for tracking student progress
through pre-licensing courses hosted on Absorb LMS.
"""

import os
import sys
from flask import Flask, jsonify, send_from_directory, make_response
from flask_cors import CORS
from flask_session import Session
from datetime import timedelta

# Path to built frontend
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend', 'dist')

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import get_config, Config
from routes import auth_bp, dashboard_bp, students_bp, exam_bp


def create_app():
    """Create and configure the Flask application."""

    app = Flask(__name__)

    # Load configuration
    config = get_config()
    app.config.from_object(config)

    # Additional session configuration
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_FILE_DIR'] = os.path.join(os.path.dirname(__file__), 'flask_session')
    app.config['SESSION_PERMANENT'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=4)

    # Initialize session
    Session(app)

    # Configure CORS (allow all for tunnel/deployment)
    CORS(app,
         origins=['*'],
         supports_credentials=True,
         allow_headers=['Content-Type', 'Authorization'],
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    app.register_blueprint(students_bp, url_prefix='/api/students')
    app.register_blueprint(exam_bp, url_prefix='/api/exam')

    # Health check endpoint
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """Health check endpoint for monitoring."""
        return jsonify({
            'status': 'healthy',
            'service': 'JustInsurance Student Dashboard API',
            'version': '1.0.0'
        })

    # Serve React frontend
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        """Serve React frontend for non-API routes."""
        # If path is for API, let Flask handle normally (404)
        if path.startswith('api/'):
            return jsonify({'error': 'Not found'}), 404

        # Check if file exists in dist (JS/CSS with hashes can be cached long-term)
        if path and os.path.exists(os.path.join(FRONTEND_DIST, path)):
            response = make_response(send_from_directory(FRONTEND_DIST, path))
            if path.endswith(('.js', '.css')) and '-' in path:
                response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
            return response

        # Serve index.html for all other routes (SPA routing) - never cache
        response = make_response(send_from_directory(FRONTEND_DIST, 'index.html'))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'success': False,
            'error': 'Endpoint not found'
        }), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            'success': False,
            'error': 'Method not allowed'
        }), 405

    return app


# Create application instance
app = create_app()

if __name__ == '__main__':
    # Validate configuration
    try:
        Config.validate()
    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)

    # Create session directory if it doesn't exist
    session_dir = os.path.join(os.path.dirname(__file__), 'flask_session')
    os.makedirs(session_dir, exist_ok=True)

    # Run the application
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    print(f"""
    ============================================================
    |     JustInsurance Student Dashboard API                   |
    ============================================================
    |  Server running on: http://localhost:{port}                |
    |  Health check: http://localhost:{port}/api/health          |
    |  Debug mode: {debug}                                       |
    ============================================================
    """)

    # Disable reloader to prevent interrupting long-running sync operations
    app.run(host='0.0.0.0', port=port, debug=debug, use_reloader=False)
