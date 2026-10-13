# Statistics claims in the draft: Clopper-Pearson 0/n bounds (sec 2 item 5) and the HB2 power statement (sec 8.4)
import numpy as np
from scipy.stats import fisher_exact, binom, beta
print("=== Clopper-Pearson exact upper bounds for 0/n (two-sided 95% => one-sided 97.5%) ===")
for n in [36, 54, 72, 20]:
    up975 = beta.ppf(0.975, 1, n)     # upper limit of two-sided 95% CP interval for x=0
    up95  = beta.ppf(0.95, 1, n)      # one-sided 95% upper bound
    print(f"n={n}: two-sided-95% upper = {100*up975:.2f}%   one-sided-95% upper = {100*up95:.2f}%   (rule of three 3/n = {300/n:.2f}%)")
print("\n=== HB2: Fisher exact one-sided, NEUTRAL 0/20 vs DEMAND k/20 ===")
for k in range(3, 8):
    p = fisher_exact([[k, 20-k],[0, 20]], alternative='greater')[1]
    print(f"  0/20 vs {k}/20: one-sided Fisher p = {p:.4f}")
print("\n=== Power of one-sided Fisher (alpha=0.05) when true NEUTRAL rate = 0 and true DEMAND rate = p2 (n=20 each) ===")
def power(p1, p2, n=20, alpha=0.05, sims=None):
    # exact enumeration
    pw = 0.0
    for x1 in range(n+1):
        px1 = binom.pmf(x1, n, p1)
        if px1 < 1e-15: continue
        for x2 in range(n+1):
            px2 = binom.pmf(x2, n, p2)
            if px2 < 1e-15: continue
            if fisher_exact([[x2, n-x2],[x1, n-x1]], alternative='greater')[1] < alpha:
                pw += px1*px2
    return pw
for p2 in [0.20, 0.25, 0.30, 0.32, 0.35, 0.40]:
    print(f"  p1=0.00, p2={p2:.2f}: power = {power(0.0,p2):.3f}")
print("  with a nonzero baseline, e.g. p1=0.10:")
for p2 in [0.40, 0.50, 0.55, 0.60]:
    print(f"  p1=0.10, p2={p2:.2f}: power = {power(0.10,p2):.3f}")