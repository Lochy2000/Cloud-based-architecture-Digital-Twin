"""
loads per-asset YAML configuration.

separate from config.py because asset parameters describe the simulated
physical system, not the deployment environment. config.py supplies the path;
this validates the contents.
"""

import yaml

class AssetError(Exception):
    """Raised when an asset configuration file is missing or malformed."""