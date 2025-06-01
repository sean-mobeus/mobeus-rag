import sys
import os

# Ensure the project root (which contains the 'backend' package) is on the Python path,
# and also add the backend directory so that top-level `import config` works for tests.
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
# Insert backend directory second so that `import config` resolves to backend/config
if BACKEND_DIR not in sys.path:
    sys.path.insert(1, BACKEND_DIR)