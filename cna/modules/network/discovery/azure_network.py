"""Azure network topology discovery.

Phase C implementation.
DD-006: Enumerates ALL active regions dynamically.
DD-002: Stores observed state only.
"""

# Phase C is not yet implemented. All network discovery is handled by
# azure_discovery.py. This module exists as the Phase C extension point.
raise NotImplementedError(
    "azure_network.py is a Phase C stub. "
    "Network discovery is provided by azure_discovery.py — do not import this module directly."
)
