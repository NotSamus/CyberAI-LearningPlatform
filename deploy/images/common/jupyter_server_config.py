# Baked into both notebook images at /etc/jupyter/jupyter_server_config.py
import os

frame_ancestors = os.environ.get("FRAME_ANCESTORS", "'self'")
c.ServerApp.tornado_settings = {  # noqa: F821
    "headers": {"Content-Security-Policy": f"frame-ancestors {frame_ancestors}"},
}
# Students get a terminal-free, simpler surface; re-enable if you teach shell skills
c.ServerApp.terminals_enabled = False  # noqa: F821
