"""Route blueprints for JustInsurance Student Dashboard."""

from .auth import auth_bp
from .dashboard import dashboard_bp
from .students import students_bp

__all__ = ['auth_bp', 'dashboard_bp', 'students_bp']
