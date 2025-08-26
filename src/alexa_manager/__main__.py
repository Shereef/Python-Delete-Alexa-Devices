"""
Entrypoint for running the alexa_manager package as a module.

This allows execution via `uv run -m alexa_manager` or `python -m alexa_manager`.
"""

from .main import main

if __name__ == "__main__":
    main()
