"""
LATTICE · IITH Operations Console - Unified FastAPI Application Entrypoint
Re-exports the consolidated FastAPI application from student_app, which contains the Student API,
analytics endpoints, presentation deck routes, and sub-mounted Technician (/tech) and Admin (/admin) micro-portals.
"""
from .student_app import app

__all__ = ["app"]
