import json
from pathlib import Path

__version__ = json.loads((Path(__file__).parent / "package.json").read_text())["version"]
