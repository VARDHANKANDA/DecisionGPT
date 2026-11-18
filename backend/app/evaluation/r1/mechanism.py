"""R1 re-exports app.evaluation.mechanism unchanged (audit-verified in V1). Kept as an r1/ file only for the versioned layout; the implementation is byte-identical."""
from app.evaluation.mechanism import *  # noqa: F401,F403
from app.evaluation import mechanism as _impl  # noqa: F401
