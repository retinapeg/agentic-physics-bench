# Exact (Clopper-Pearson) 95% two-sided upper bound for 0 successes in n trials: 1 - 0.025**(1/n)
from scipy.stats import beta
for n in (36, 54, 72):
    closed = 1 - 0.025 ** (1 / n)
    cp = beta.ppf(0.975, 0 + 1, n - 0)   # upper limit of the two-sided 95% CP interval at x=0
    print(f"n={n}: 1-0.025^(1/n)={closed:.4f}  beta.ppf(0.975,1,n)={cp:.4f}  -> {100*closed:.1f}%")