"""
Dynamic Crowd-Escalation Priority Algorithm
Calculates dynamic priority score based on base severity, crowd confirmation count,
and elapsed waiting time.
"""
import datetime
from typing import Tuple

CATEGORY_BASE_WEIGHTS = {
    "water_cooler": 25.0,     # High impact: hydration for entire floor/wing
    "washing_machine": 20.0,  # High friction: community laundry blockage
    "dryer": 15.0,
    "electrical": 18.0,       # Safety & core utility (lights/fan/power)
    "plumbing": 16.0,         # Water wastage / sanitation
    "network": 12.0,          # Academic connectivity
    "carpentry": 10.0,        # Fixtures, wardrobe, door latches
    "other": 8.0
}


def calculate_priority(
    category: str,
    confirmations_count: int,
    created_at: datetime.datetime,
    now: datetime.datetime = None
) -> Tuple[float, str]:
    """
    Computes dynamic priority score and tier:
    Score = BaseWeight + (confirmations * 3.5) + (hours_pending * 1.2)
    """
    if now is None:
        now = datetime.datetime.utcnow()

    # Determine base weight
    base_weight = CATEGORY_BASE_WEIGHTS.get(category.lower(), 10.0)

    # Time elapsed in hours
    time_delta = now - created_at
    hours_pending = max(0.0, time_delta.total_seconds() / 3600.0)

    # Scaled crowd confirmations (sublinear/linear blend)
    # Each extra student confirmation adds 3.5 points
    crowd_factor = max(1, confirmations_count) * 3.5

    # Time aging factor: issues lingering over 24-48 hours rise steadily
    time_factor = min(40.0, hours_pending * 1.2)

    total_score = round(base_weight + crowd_factor + time_factor, 1)

    if total_score >= 50.0:
        tier = "CRITICAL"
    elif total_score >= 35.0:
        tier = "HIGH"
    elif total_score >= 22.0:
        tier = "MEDIUM"
    else:
        tier = "LOW"

    return total_score, tier
