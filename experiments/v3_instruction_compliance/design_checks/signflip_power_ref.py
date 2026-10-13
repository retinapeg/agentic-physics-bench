"""Exact one-sided sign-flip power for 12 tasks x 3 reps at reference uptake pA and treatment uptake pB (seeded)."""
import random, itertools
T, R, SIMS = 12, 3, 2000
def draw_task_rates(rng, p, icc):
    if icc <= 0: return p
    # beta-binomial: task-level rate ~ Beta with mean p, ICC = 1/(a+b+1)
    s = 1/icc - 1
    a, b = max(p*s, 1e-6), max((1-p)*s, 1e-6)
    return rng.betavariate(a, b)
def signflip_p(d):
    n = len(d); obs = sum(d)
    cnt = 0; total = 0
    for signs in itertools.product((1,-1), repeat=n):
        s = sum(x*y for x,y in zip(d, signs)); total += 1
        if s <= obs + 1e-12: cnt += 1   # predicted direction: negative difference (B below A)
    return cnt/total
def power(pA, pB, icc, alpha, rng):
    rej = 0
    for _ in range(SIMS):
        d = []
        for t in range(T):
            ra = draw_task_rates(rng, pA, icc); rb = draw_task_rates(rng, pB, icc)
            a = sum(rng.random() < ra for _ in range(R))/R; b = sum(rng.random() < rb for _ in range(R))/R
            d.append(b - a)
        if signflip_p(d) <= alpha: rej += 1
    return rej/SIMS
rng = random.Random(20261006)
print("pA   pB    icc   power@0.05  power@0.0167")
for pA in (1.0, 0.8, 0.6):
    for drop in (0.2, 0.33, 0.5):
        pB = max(pA - drop, 0.0)
        for icc in (0.0, 0.5):
            p1 = power(pA, pB, icc, 0.05, rng); p2 = power(pA, pB, icc, 0.0167, rng)
            print(f"{pA:.2f} {pB:.2f}  {icc:.1f}   {p1:.2f}        {p2:.2f}")