"""Vercel serverless entrypoint for the Flask API.

Vercel's @vercel/python runtime imports this module and looks for a module-level
WSGI callable named `app`. Only /api/* is routed here (see vercel.json rewrites);
the built React SPA is served as static assets straight from Vercel's CDN, so
static requests never invoke a function.

SANDBOX ONLY. See SANDBOX.md → "Vercel deployment" for the serverless caveats,
most importantly that the module-level caches in dashboard.py and exam.py do not
survive between cold starts.
"""

import os
import sys

# backend/ holds the application package; put it on the path before importing.
_BACKEND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
sys.path.insert(0, _BACKEND)

# Signals to app.create_app() that it must not use filesystem-backed sessions.
# Vercel's filesystem is read-only apart from /tmp, and /tmp is not shared
# between invocations, so Flask-Session's filesystem backend cannot work here.
os.environ.setdefault('SERVERLESS', '1')

from app import app  # noqa: E402  (path setup must precede this import)
