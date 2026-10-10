import os
import sys
from pathlib import Path

# Run every test against the in-memory GPIO mock - no hardware required.
os.environ.setdefault("HOMEAUTO_GPIO_BACKEND", "mock")
os.environ.setdefault("HOMEAUTO_API_TOKEN", "test-token-0123456789abcdefghij")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
