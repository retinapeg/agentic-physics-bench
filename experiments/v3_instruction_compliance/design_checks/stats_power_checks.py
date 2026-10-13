"""Numerical checks for the V3 design review (statistics sections). Read-only w.r.t. the repo.
Run: PYTHONDONTWRITEBYTECODE=1 python3 -B stats_checks.py
"""
import math
import sys
import itertools
import numpy as np
from scipy import stats
from scipy.special import comb

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[3] / "src"))  # repo src/ (path made relative on 2026-10-13)
from analyze_v2 import paired  # the cluster bootstrap the draft proposes to reuse

np.set_printoptions(precision=4, suppress=True)
H = lambda s: print("\n" + "=" * 8 + " " + s + " " + "=" * 8)

# ---------------------------------------------------------------- 1. Clopper-Pearson for 0/n
H("1. Clopper-Pearson upper bounds for 0/n")
print(f"{'n':>4} {'2-sided 95% upper (1-0.025^(1/n))':>36} {'scipy beta.ppf(.975,1,n)':>26} {'1-sided 95% upper (1-0.05^(1/n))':>34} {'rule of 3 (3/n)':>16}")
for n in (12, 18, 20, 24, 36, 54, 60, 72, 108):
    two = 1 - 0.025 ** (1 / n)
    two_sp = stats.beta.ppf(0.975, 1, n)
    one = 1 - 0.05 ** (1 / n)
    print(f"{n:>4} {two:>36.4%} {two_sp:>26.4%} {one:>34.4%} {3/n:>16.4%}")

# ---------------------------------------------------------------- 2. Standard errors at p = 0.5
H("2. SE of a proportion at p=0.5 (worst case)")
for n, k in ((36, 12), (54, 18), (12, 12)):
    se_ind = math.sqrt(0.25 / n)
    se_cor = math.sqrt(0.25 / k)  # perfectly correlated within task: effective n = clusters
    m = n / k
    print(f"n={n} episodes in {k} clusters (m={m:g} reps): SE independent={se_ind:.4f}; "
          f"perfectly correlated (n_eff={k})={se_cor:.4f}; DEFF=1+(m-1)rho -> rho=1 gives {se_ind*math.sqrt(1+(m-1)):.4f}")

# ---------------------------------------------------------------- 3. Fisher power, 20 vs 20
H("3. One-sided Fisher exact test, n=20 vs 20, alpha=0.05")
n = 20
# critical value given 0/20 in group 1
print("p-value of 0/20 vs k/20 (one-sided, H1: group2 > group1):")
for k in range(1, 8):
    table = [[k, n - k], [0, n]]  # row0 = DEMAND (events, non-events), row1 = NEUTRAL
    p_f = stats.fisher_exact(table, alternative="greater")[1]
    p_b = stats.boschloo_exact(table, alternative="greater").pvalue
    p_hand = comb(20, k, exact=True) / comb(40, k, exact=True)
    print(f"  k={k}: Fisher p={p_f:.4f} (hand C(20,k)/C(40,k)={p_hand:.4f}); Boschloo p={p_b:.4f}")


def exact_power(p1, p2, n=20, alpha=0.05, test="fisher"):
    """Exact power: enumerate all (x1, x2) outcomes, sum binomial probabilities of rejections.
    Group 1 = NEUTRAL (rate p1), group 2 = DEMAND (rate p2); H1: p2 > p1."""
    pw = 0.0
    for x1 in range(n + 1):
        pr1 = stats.binom.pmf(x1, n, p1)
        if pr1 < 1e-15:
            continue
        for x2 in range(n + 1):
            pr2 = stats.binom.pmf(x2, n, p2)
            if pr2 < 1e-15:
                continue
            table = [[x2, n - x2], [x1, n - x1]]
            if test == "fisher":
                p = stats.fisher_exact(table, alternative="greater")[1]
            else:
                p = stats.boschloo_exact(table, alternative="greater").pvalue
            if p <= alpha:
                pw += pr1 * pr2
    return pw


print("\nExact power (alpha=0.05 one-sided), NEUTRAL rate p1, DEMAND rate p2:")
print(f"{'p1':>5} {'p2':>5} {'Fisher':>8} {'Boschloo':>9} {'P(Bin(20,p2)>=5) check':>24}")
for p1 in (0.0, 0.05):
    for p2 in (0.2, 0.25, 0.3, 0.4, 0.5):
        pf = exact_power(p1, p2, test="fisher")
        pb = exact_power(p1, p2, test="boschloo")
        chk = stats.binom.sf(4, 20, p2) if p1 == 0 else float("nan")
        print(f"{p1:>5.2f} {p2:>5.2f} {pf:>8.3f} {pb:>9.3f} {chk:>24.3f}")

# p2 needed for 80% power when p1 = 0 (Fisher: reject iff x2 >= 5)
from scipy.optimize import brentq
p80_f = brentq(lambda p: stats.binom.sf(4, 20, p) - 0.8, 0.05, 0.9)
# Boschloo: find critical k under p1=0
kcrit_b = min(k for k in range(1, 21) if stats.boschloo_exact([[k, 20 - k], [0, 20]], alternative="greater").pvalue <= 0.05)
p80_b = brentq(lambda p: stats.binom.sf(kcrit_b - 1, 20, p) - 0.8, 0.05, 0.9)
print(f"\nWith p1=0: Fisher rejects iff DEMAND >= 5/20; true DEMAND rate for 80% power = {p80_f:.3f}")
print(f"With p1=0: Boschloo rejects iff DEMAND >= {kcrit_b}/20; true DEMAND rate for 80% power = {p80_b:.3f}")
# Also Holm-adjusted threshold alpha/2 = 0.025 for HB2 under p1=0
kcrit_f_holm = min(k for k in range(1, 21) if comb(20, k, exact=True) / comb(40, k, exact=True) <= 0.025)
print(f"Holm (m=2) smallest threshold 0.025: Fisher critical k = {kcrit_f_holm}/20")

# ---------------------------------------------------------------- 4. Sign-flip resolution and paired() behaviour
H("4. Exact sign-flip test resolution with 12 tasks; paired() interval with k non-zero tasks")
print("k non-zero same-sign tasks -> minimal one-sided p = 2^-k; P(bootstrap resample all-zero) = ((12-k)/12)^12")
for k in range(1, 13):
    print(f"  k={k:>2}: min p = {2**-k:.5f}; P(all-zero resample) = {((12-k)/12)**12:.4f}")

print("\nActual analyze_v2.paired() on d = [-1]*k + [0]*(12-k) (12 tasks, seed 20260923, B=2000):")
for k in (1, 2, 3, 4, 5, 6):
    p = {f"t{i}": {"c1": (0.0 if i < k else 1.0), "c2": 1.0} for i in range(12)}  # c1-c2 = -1 for first k tasks
    r = paired([f"t{i}" for i in range(12)], p, "c1", "c2")
    print(f"  k={k}: mean diff={r['mean_difference']:+.3f}, bootstrap_95pct={r['bootstrap_95pct']}, tied={r['tasks_tied']}, "
          f"excludes 0: {r['bootstrap_95pct'][1] < 0}; exact sign-flip one-sided p = {2**-k:.4f}")
print("\nWith 3 reps, d_t takes values in {-1,-2/3,-1/3,0,1/3,2/3,1}; same check for d = [-1/3]*k + [0]*(12-k):")
for k in (3, 4, 5):
    p = {f"t{i}": {"c1": (2/3 if i < k else 1.0), "c2": 1.0} for i in range(12)}
    r = paired([f"t{i}" for i in range(12)], p, "c1", "c2")
    print(f"  k={k}: bootstrap_95pct={[round(x,3) for x in r['bootstrap_95pct']]}, excludes 0: {r['bootstrap_95pct'][1] < 0}; sign-flip p={2**-k:.4f}")


def signflip_p(d, direction="less"):
    """Exact one-sided sign-flip p-value for the mean of paired differences d (enumerate all 2^n)."""
    d = np.asarray(d, float)
    n = len(d)
    obs = d.sum()
    signs = np.array(list(itertools.product([1, -1], repeat=n)))
    sums = signs @ d
    if direction == "less":
        return np.mean(sums <= obs + 1e-12)
    return np.mean(sums >= obs - 1e-12)


print("\nCheck signflip_p against 2^-k:", [round(signflip_p([-1]*k + [0]*(12-k)), 5) for k in (3, 4, 5)])

# ---------------------------------------------------------------- 5. Null calibration: paired() interval-excludes-0 vs sign-flip
H("5. Type I error under H0 (12 tasks, 3 reps, A and B both request with prob pi, independent episodes)")
rng = np.random.default_rng(20261006)
NSIM = 1500
for pi in (0.5, 0.8, 0.95):
    rej_boot = rej_sf = 0
    for s in range(NSIM):
        a = rng.binomial(3, pi, 12) / 3
        b = rng.binomial(3, pi, 12) / 3
        p = {f"t{i}": {"B": b[i], "A": a[i]} for i in range(12)}
        r = paired([f"t{i}" for i in range(12)], p, "B", "A", rng_seed=int(rng.integers(1, 2**31)))
        if r["bootstrap_95pct"][1] < 0:  # the draft's HA1 bootstrap criterion (interval entirely below 0)
            rej_boot += 1
        if signflip_p(b - a, "less") <= 0.05:
            rej_sf += 1
    print(f"  pi={pi}: P(bootstrap interval entirely below 0) = {rej_boot/NSIM:.3f} (nominal 0.025); "
          f"P(sign-flip one-sided p<=0.05) = {rej_sf/NSIM:.3f} (nominal <=0.05)")

# ---------------------------------------------------------------- 6. HA4 power simulation
H("6. HA4 power: 6 easy + 6 hard tasks, 6 prohibited episodes per task (C-NO 3 + D 3)")
rng = np.random.default_rng(20261006)
NSIM = 4000
B = 2000
splits = np.array([c for c in itertools.combinations(range(12), 6)])  # 924 label assignments


def perm_p(props):
    """One-sided exact permutation test of stratum labels: hard = first 6, easy = last 6; H1: hard > easy."""
    obs = props[:6].mean() - props[6:].mean()
    hard_means = props[splits].mean(axis=1)
    diffs = hard_means - (props.sum() - props[splits].sum(axis=1)) / 6
    return np.mean(diffs >= obs - 1e-12)


def strat_boot_lower(props, rng):
    """Stratified cluster bootstrap (resample 6 hard and 6 easy tasks with replacement), percentile 95% interval."""
    hi = rng.integers(0, 6, size=(B, 6))
    ei = rng.integers(0, 6, size=(B, 6))
    boots = props[:6][hi].mean(axis=1) - props[6:][ei].mean(axis=1)
    boots.sort()
    return boots[int(0.025 * B)], boots[int(0.975 * B) - 1]


def draw_task_rates(mean, mode, rng, ntask=6):
    if mode == "independent":
        return np.full(ntask, mean)
    if mode.startswith("icc"):
        rho = float(mode[3:])
        s = 1 / rho - 1  # a+b = (1-rho)/rho
        return rng.beta(mean * s, (1 - mean) * s, ntask) if mean > 0 else np.zeros(ntask)
    if mode == "mixture":  # one violator task in six with rate 6*mean (=0.6 at mean 0.1), others 0
        r = np.zeros(ntask)
        r[rng.integers(0, ntask)] = min(1.0, ntask * mean)
        return r
    raise ValueError(mode)


def simulate(hard, easy, mode, nsim=NSIM):
    rej_perm = rej_boot = rej_fisher = 0
    for _ in range(nsim):
        rh = draw_task_rates(hard, mode, rng)
        re = draw_task_rates(easy, mode, rng)
        xh = rng.binomial(6, rh)
        xe = rng.binomial(6, re)
        props = np.concatenate([xh / 6, xe / 6])
        if perm_p(props) <= 0.05:
            rej_perm += 1
        lo, hi_ = strat_boot_lower(props, rng)
        if lo > 0:
            rej_boot += 1
        tab = [[xh.sum(), 36 - xh.sum()], [xe.sum(), 36 - xe.sum()]]
        if stats.fisher_exact(tab, alternative="greater")[1] <= 0.05:
            rej_fisher += 1
    return rej_perm / nsim, rej_boot / nsim, rej_fisher / nsim


print("Analytic (independence, easy=0): P(task shows >=1 violation)=1-(1-p)^6; perm test rejects iff >=4 of 6 hard tasks non-zero")
for hard in (0.1, 0.2, 0.3, 0.5):
    q = 1 - (1 - hard) ** 6
    print(f"  hard={hard}: q={q:.3f}; P(k>=4 of 6)={stats.binom.sf(3, 6, q):.3f}")
print("Exact permutation p for k of 6 hard tasks non-zero (easy all zero): C(12-k,6-k)/924 =",
      {k: round(comb(12 - k, 6 - k, exact=True) / 924, 4) for k in range(1, 7)})

print(f"\nSimulation ({NSIM} sims, seeded): power / rejection rate of (exact label-permutation p<=0.05 | stratified "
      f"cluster-bootstrap 95% lower bound > 0 | naive Fisher 36 vs 36 one-sided)")
print(f"{'hard':>5} {'easy':>5} {'within-task correlation':>24} {'perm':>7} {'boot':>7} {'fisher':>7}")
for hard, easy in ((0.1, 0.0), (0.2, 0.0), (0.3, 0.0), (0.5, 0.0)):
    for mode in ("independent", "icc0.5", "icc0.8", "mixture"):
        pp, pb, pf = simulate(hard, easy, mode, nsim=1500 if mode != "independent" else NSIM)
        print(f"{hard:>5} {easy:>5} {mode:>24} {pp:>7.3f} {pb:>7.3f} {pf:>7.3f}")
print("\nNull (hard = easy): type I error of the three rules")
for rate in (0.05, 0.1, 0.2):
    for mode in ("independent", "icc0.5", "icc0.8"):
        pp, pb, pf = simulate(rate, rate, mode, nsim=1500)
        print(f"{rate:>5} {rate:>5} {mode:>24} {pp:>7.3f} {pb:>7.3f} {pf:>7.3f}")

# ---------------------------------------------------------------- 7. Budget arithmetic
H("7. Budget arithmetic")
print("Arm A recommended: 5*12*3 =", 5 * 12 * 3, "episodes;", 5 * 12 * 3 * 2, "calls (max; a missing_output episode uses 1)")
print("Arm A larger:      5*18*3 =", 5 * 18 * 3, "episodes;", 5 * 18 * 3 * 2, "calls; per cell", 18 * 3)
print("Arm A fallback:    5*12*1 =", 5 * 12 * 1, "episodes;", 5 * 12 * 1 * 2, "calls; per cell", 12)
print("Arm B: 3*2*2*5 =", 3 * 2 * 2 * 5, "; per pooled V0!=0 frame cell: 2*2*5 =", 2 * 2 * 5, "; V0=0 NEUTRAL cell: 2*5 =", 2 * 5)
print("Pilot recommended: 1 + 3*5*1*2 + 2*2*1 =", 1 + 3 * 5 * 2 + 4, "; minimum: 1 + 3*4*2 + 4 =", 1 + 3 * 4 * 2 + 4)
print("Total live (no calibration): 360 + 60 + 35 =", 360 + 60 + 35)
print("Prohibited-state pooled n: 2 cells * 36 =", 72, "; 18-task variant:", 2 * 54)
