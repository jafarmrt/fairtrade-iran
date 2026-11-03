"""
Weighted counting (section 1.2 of the governance document), with exact
fractions so that "more than half" and "two thirds" are never off by rounding.

    score = sum over groups of  weight(g) x (count in g / members of g)

where a group with no members in the denominator is left out and its weight is
shared among the other groups in proportion to their weights.
"""

from fractions import Fraction

from .models import GROUPS, Option


def effective_weights(weights, totals):
    """Weights as fractions of 1, after sharing out the weight of groups whose total is zero."""
    active = [g for g in GROUPS if totals.get(g, 0) > 0 and weights.get(g, 0) > 0]
    whole = sum(weights[g] for g in active)
    if not whole:
        return {g: Fraction(0) for g in GROUPS}
    return {g: (Fraction(weights[g], whole) if g in active else Fraction(0)) for g in GROUPS}


def weighted_share(weights, counts, totals):
    """The weighted score (a Fraction between 0 and 1) of `counts` out of `totals`, per group."""
    w = effective_weights(weights, totals)
    return sum((w[g] * Fraction(min(counts.get(g, 0), totals[g]), totals[g])
                for g in GROUPS if w[g]), Fraction(0))


def meets(value, num, den, strict):
    threshold = Fraction(num, den)
    return value > threshold if strict else value >= threshold


def pct(value):
    """A Fraction as a percentage rounded for display (the decision always uses the exact value)."""
    return round(float(value) * 100, 2)


def quorum(settings, assembly, eligible, present):
    """(score, met) for attendance: present out of all members on the roll, per group."""
    score = weighted_share(settings.weights, present, eligible)
    if assembly.call == assembly.Call.SECOND:
        met = meets(score, settings.quorum_second_num, settings.quorum_second_den, strict=False)
    else:
        met = meets(score, settings.quorum_first_num, settings.quorum_first_den, strict=True)
    return score, met


def count(settings, item, eligible, present, tallies):
    """
    The result of one agenda item.

    eligible, present: {group: n};  tallies: {option_id: {group: n}}.
    Returns a JSON-serialisable dict that is stored on the item.
    """
    weights = settings.weights
    q_score, q_met = quorum(settings, item.assembly, eligible, present)
    eff = effective_weights(weights, present)
    rows = []
    for option in item.ballot_options():
        counts = tallies.get(option.pk, {})
        score = weighted_share(weights, counts, present)
        rows.append({
            "id": option.pk, "code": option.code, "label": option.label, "label_en": option.label_en,
            "counts": {g: counts.get(g, 0) for g in GROUPS}, "votes": sum(counts.values()),
            "score": pct(score), "_exact": score,
        })
    result = {
        "eligible": {g: eligible.get(g, 0) for g in GROUPS},
        "present": {g: present.get(g, 0) for g in GROUPS},
        "weights": {g: pct(eff[g]) for g in GROUPS},
        "quorum": pct(q_score),
        "quorum_met": q_met,
        "options": rows,
        "passed": None,
        "elected": [],
        "tie": False,
    }
    if item.kind == item.Kind.RESOLUTION:
        yes = next((r["_exact"] for r in rows if r["code"] == Option.YES), Fraction(0))
        if item.majority == item.Majority.SPECIAL:
            ok = meets(yes, settings.special_num, settings.special_den, strict=False)
        else:
            ok = meets(yes, settings.majority_num, settings.majority_den, strict=True)
        result["passed"] = bool(q_met and ok)
    else:
        ranked = sorted((r for r in rows if r["_exact"] > 0), key=lambda r: r["_exact"], reverse=True)
        seats = max(item.seats, 1)
        elected = ranked[:seats]
        if len(ranked) > seats and ranked[seats]["_exact"] == ranked[seats - 1]["_exact"]:
            # A tie for the last seat: the assembly decides (e.g. a run-off); nobody at that score is elected.
            cutoff = ranked[seats - 1]["_exact"]
            elected = [r for r in elected if r["_exact"] > cutoff]
            result["tie"] = True
        result["elected"] = [r["id"] for r in elected] if q_met else []
        result["passed"] = bool(q_met and elected)
    for r in rows:
        del r["_exact"]
    return result
