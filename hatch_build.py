"""Refuse to build a wheel that would install without its data."""
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

BUNDLED_DB = Path("src/sdo_mcp/data/sdo.sqlite")


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        # Editable installs (uv sync) run from the checkout and use SDO_DB.
        if version == "editable":
            return
        if not (Path(self.root) / BUNDLED_DB).is_file():
            raise RuntimeError(
                f"{BUNDLED_DB} is missing; run `uv run python -m sdo_mcp.bundle` first"
            )
