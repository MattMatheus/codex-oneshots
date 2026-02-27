from functools import lru_cache


SINGLES = {f"S{i}": i for i in range(1, 21)}
DOUBLES = {f"D{i}": i * 2 for i in range(1, 21)}
TRIPLES = {f"T{i}": i * 3 for i in range(1, 21)}
BULLS = {"SB": 25, "DB": 50}

ALL_THROWS: dict[str, int] = {}
ALL_THROWS.update(SINGLES)
ALL_THROWS.update(DOUBLES)
ALL_THROWS.update(TRIPLES)
ALL_THROWS.update(BULLS)

FINISH_THROWS: dict[str, int] = {}
FINISH_THROWS.update(DOUBLES)
FINISH_THROWS["DB"] = 50


def _rank_throw(label: str) -> tuple[int, int, str]:
    """Prefer higher-value throws, then deterministic lexical tie-break."""
    kind_rank = {"T": 0, "D": 1, "S": 2}.get(label[0], 3)
    return (-ALL_THROWS[label], kind_rank, label)


@lru_cache(maxsize=256)
def suggest_checkout(score: int, max_darts: int = 3) -> list[list[str]]:
    if score < 2 or score > 170 or max_darts < 1:
        return []

    suggestions: list[list[str]] = []
    prethrows = sorted(ALL_THROWS.keys(), key=_rank_throw)
    finishers = sorted(FINISH_THROWS.keys(), key=lambda l: -FINISH_THROWS[l])

    # 1 dart finishes
    for last in finishers:
        if FINISH_THROWS[last] == score:
            suggestions.append([last])

    if max_darts >= 2:
        for first in prethrows:
            remaining = score - ALL_THROWS[first]
            if remaining < 2:
                continue
            for last in finishers:
                if FINISH_THROWS[last] == remaining:
                    suggestions.append([first, last])

    if max_darts >= 3:
        for first in prethrows:
            for second in prethrows:
                remaining = score - ALL_THROWS[first] - ALL_THROWS[second]
                if remaining < 2:
                    continue
                for last in finishers:
                    if FINISH_THROWS[last] == remaining:
                        suggestions.append([first, second, last])

    # Deduplicate while preserving order and limit output size.
    unique: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for combo in suggestions:
        key = tuple(combo)
        if key not in seen:
            seen.add(key)
            unique.append(combo)

    return unique[:20]
