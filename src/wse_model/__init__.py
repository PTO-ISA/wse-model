"""WSE architecture model.

The package is split into two layers:

* a **pure-Python semantic core** (:mod:`wse_model.calendar`,
  :mod:`wse_model.noc`, :mod:`wse_model.analysis`, ...) that owns encoding,
  legality, conservation, and performance rules and needs no toolchain; and
* an **ACIR model layer** (:mod:`wse_model.acir`) that expresses the same rules
  as schedulable ``agentic_circuit`` processes, queues, resources, and
  committed state.

The semantic core is the authority. The ACIR layer must not disagree with it.
"""

from wse_model.errors import (
    CalendarError,
    ConservationError,
    IllegalBitPairError,
    LandSetError,
    OpenItemError,
    RouteTreeError,
    TopologyError,
    VersionMismatchError,
    WseModelError,
)
from wse_model.topology import (
    CALENDAR_BASELINE,
    WHITEPAPER_HARDWARE,
    MeshTopology,
    TopologyProfile,
    topology_profile,
)
from wse_model.version import __version__

__all__ = [
    "CALENDAR_BASELINE",
    "WHITEPAPER_HARDWARE",
    "CalendarError",
    "ConservationError",
    "IllegalBitPairError",
    "LandSetError",
    "MeshTopology",
    "OpenItemError",
    "RouteTreeError",
    "TopologyError",
    "TopologyProfile",
    "VersionMismatchError",
    "WseModelError",
    "__version__",
    "topology_profile",
]
