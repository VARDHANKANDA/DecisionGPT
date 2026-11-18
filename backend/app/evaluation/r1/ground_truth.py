"""R1 re-exports app.evaluation.ground_truth unchanged (audit-verified in V1). Kept as an r1/ file only for the versioned layout; the implementation is byte-identical."""
from app.evaluation.ground_truth import *  # noqa: F401,F403
from app.evaluation import ground_truth as _impl  # noqa: F401
