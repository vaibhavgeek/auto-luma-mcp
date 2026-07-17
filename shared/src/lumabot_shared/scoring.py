from collections.abc import Mapping


def clamp_score(value: float | int) -> int:
    return max(0, min(100, round(value)))


def validate_score(value: int) -> int:
    if not 0 <= value <= 100:
        raise ValueError("score must be between 0 and 100")
    return value


def weighted_score(scores: Mapping[str, int], weights: Mapping[str, float]) -> int:
    if not scores:
        raise ValueError("at least one score is required")

    total_weight = 0.0
    weighted_total = 0.0
    for key, score in scores.items():
        validate_score(score)
        weight = weights.get(key, 0.0)
        if weight < 0:
            raise ValueError("weights must be non-negative")
        total_weight += weight
        weighted_total += score * weight

    if total_weight <= 0:
        raise ValueError("total weight must be greater than zero")
    return clamp_score(weighted_total / total_weight)
