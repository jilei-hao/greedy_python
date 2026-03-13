# --------------------------------------------------------------------------
# Re-export all original C++ classes for full backward compatibility
# --------------------------------------------------------------------------
from ._picsl_greedy import (  # noqa: F401
    Greedy2D,
    Greedy3D,
    GreedyFloat2D,
    GreedyFloat3D,
    LMShoot2D,
    LMShoot3D,
    LMShootFloat2D,
    LMShootFloat3D,
    MultiChunkGreedy2D,
    MultiChunkGreedy3D,
    Propagation,
    PropagationFloat,
)

# --------------------------------------------------------------------------
# New Python-friendly high-level wrapper classes
# --------------------------------------------------------------------------
from ._greedy_api import (  # noqa: F401
    AffineResult,
    DeformableResult,
    GreedyRegistration,
    LMShootWrapper,
    MultiChunkGreedyWrapper,
    PropagationWrapper,
)
