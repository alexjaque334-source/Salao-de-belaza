import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from server import app  # noqa: E402

# Vercel's @vercel/python runtime serves this ASGI `app` object directly.
