"""Exact small-sample statistics for V3, standard library only (PROTOCOL.md section 5).

Everything here is enumeration or bisection on exact binomial and hypergeometric sums, so CI needs no
numerical library. The scipy-based scripts in design_checks/ were used to check these during the design.
"""
import itertools
import math
import random


def binom_cdf(k, n, p):
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, k + 1))


def clopper_pearson(x, n, alpha=0.05):
    """Two-sided exact interval for a binomial proportion. 0/n gives [0, 1 - (alpha/2)^(1/n)]."""
    if n == 0:
        return [None, None]

    def bisect(too_small):
        lo, hi = 0.0, 1.0
        for _ in range(200):
            mid = (lo + hi) / 2
            if too_small(mid):
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2
    # lower: P(X >= x | p) = alpha/2 (increasing in p); upper: P(X <= x | p) = alpha/2 (decreasing in p)
    lower = 0.0 if x == 0 else bisect(lambda p: 1 - binom_cdf(x - 1, n, p) < alpha / 2)
    upper = 1.0 if x == n else bisect(lambda p: binom_cdf(x, n, p) > alpha / 2)
    return [lower, upper]


def sign_flip(diffs, direction):
    """Exact one-sided sign-flip permutation test over tasks on the mean difference.

    direction '>' tests mean > 0, '<' tests mean < 0. All 2^n sign assignments are enumerated; zero
    differences are kept (they are invariant). The observed assignment counts, so p >= 2^-k with k non-tied.
    """
    n = len(diffs)
    if n == 0:
        return {"n_tasks": 0, "mean_difference": None, "p": None, "non_tied": 0, "min_attainable_p": None}
    observed = sum(diffs) / n
    sign = 1.0 if direction == ">" else -1.0
    count = 0
    for signs in itertools.product((1.0, -1.0), repeat=n):
        stat = sum(s * d for s, d in zip(signs, diffs)) / n
        if sign * stat >= sign * observed - 1e-12:
            count += 1
    k = sum(1 for d in diffs if d != 0)
    return {"n_tasks": n, "mean_difference": observed, "p": count / 2 ** n, "non_tied": k, "min_attainable_p": 2.0 ** -k,
            "direction": direction, "can_reach_alpha_0.05": k >= 5}


def sign_flip_two_sided(diffs):
    n = len(diffs)
    if n == 0:
        return {"n_tasks": 0, "mean_difference": None, "p": None}
    observed = abs(sum(diffs) / n)
    count = sum(1 for signs in itertools.product((1.0, -1.0), repeat=n)
                if abs(sum(s * d for s, d in zip(signs, diffs)) / n) >= observed - 1e-12)
    return {"n_tasks": n, "mean_difference": sum(diffs) / n, "p": count / 2 ** n, "non_tied": sum(1 for d in diffs if d != 0)}


def label_permutation(group1, group2):
    """Exact one-sided permutation of group labels: P(mean(g1) - mean(g2) >= observed) over all assignments."""
    values = list(group1) + list(group2)
    n1 = len(group1)
    if not group1 or not group2:
        return {"p": None, "difference": None, "assignments": 0}
    observed = sum(group1) / n1 - sum(group2) / len(group2)
    total = sum(values)
    count = n = 0
    for idx in itertools.combinations(range(len(values)), n1):
        s1 = sum(values[i] for i in idx)
        stat = s1 / n1 - (total - s1) / (len(values) - n1)
        n += 1
        if stat >= observed - 1e-12:
            count += 1
    return {"p": count / n, "difference": observed, "assignments": n}


def fisher_one_sided(x1, n1, x2, n2):
    """Exact one-sided Fisher test that group 1's rate exceeds group 2's: P(X1 >= x1 | margins)."""
    if n1 == 0 or n2 == 0:
        return None
    total, successes = n1 + n2, x1 + x2
    denom = math.comb(total, successes)
    return sum(math.comb(n1, k) * math.comb(n2, successes - k) for k in range(x1, min(n1, successes) + 1)
               if successes - k <= n2) / denom


def holm(pvalues, alpha=0.05):
    """Holm-Bonferroni over a family {name: p}. Returns {name: {p, threshold, rejected}}; None p-values never reject."""
    names = sorted(pvalues, key=lambda k: (pvalues[k] is None, pvalues[k] if pvalues[k] is not None else 1.0))
    out, still = {}, True
    for i, name in enumerate(names):
        threshold = alpha / (len(names) - i)
        p = pvalues[name]
        rejected = still and p is not None and p <= threshold
        still = rejected
        out[name] = {"p": p, "threshold": threshold, "rejected": rejected}
    return out


def bootstrap_mean(diffs, seed, b=2000):
    """Descriptive 95% percentile interval for the mean of task-level differences (cluster = task)."""
    if not diffs:
        return [None, None]
    rng = random.Random(seed)
    means = sorted(sum(diffs[rng.randrange(len(diffs))] for _ in diffs) / len(diffs) for _ in range(b))
    return [means[int(0.025 * b)], means[int(0.975 * b) - 1]]
