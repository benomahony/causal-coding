from __future__ import annotations

import pandas as pd
from dowhy import CausalModel

from .model import graph


def causal_model(*, treatment: str = "agentic_task_share", outcome: str = "lead_time") -> CausalModel:
    """Build the current causal theory in DoWhy without observational data."""
    data = pd.DataFrame(columns=sorted(graph().nodes))
    return CausalModel(data=data, treatment=treatment, outcome=outcome, graph=graph())
