"""Backward-compatible entry point for the warp control plane.

All logic has been factored into the ``runtime.cp`` package.  This module
re-exports ``ControlPlaneService`` and ``main`` so that existing callers
(integration tests, CLI wrappers, and ``python runtime/control_plane.py``)
continue to work without changes.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the parent of ``runtime/`` is on the import path so that
# ``from runtime.cp import …`` resolves when this file is executed
# directly as ``python runtime/control_plane.py``.
_PARENT = str(Path(__file__).resolve().parents[1])
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from runtime.cp import ControlPlaneService, main  # noqa: E402, F401

if __name__ == "__main__":
    raise SystemExit(main())
