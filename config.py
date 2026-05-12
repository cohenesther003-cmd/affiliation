import yaml
from pathlib import Path

_config_path = Path(__file__).parent / "config.yaml"

with open(_config_path) as f:
    CONFIG = yaml.safe_load(f)
