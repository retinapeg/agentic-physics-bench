import numpy as np, math
from scipy import special, integrate
import mpmath as mp
deg = 180/math.pi
# 1. q=0 reduction: scipy's ce_0(z,0), ce_{2n}(z,0), se_{2n}(z,0)
z = 0.7
print("ce_0(z,0) =", special.mathieu_cem(0, 0.0, z*deg)[0], " expected 1/sqrt2 =", 1/math.sqrt(2))
print("ce_2(z,0) =", special.mathieu_cem(2, 0.0, z*deg)[0], " cos2z =", math.cos(2*z))
print("se_2(z,0) =", special.mathieu_sem(2, 0.0, z*deg)[0], " sin2z =", math.sin(2*z))
print("a_2(0), b_2(0) =", special.mathieu_a(2, 0.0), special.mathieu_b(2, 0.0))
# 2. normalisation: int_0^{2pi} ce_n(z,q)^2 dz = pi ?
for q in (0.4, 4.0):
    for n in (0, 2, 4):
        val = integrate.quad(lambda zz: special.mathieu_cem(n, q, zz*deg)[0]**2, 0, 2*math.pi, limit=200)[0]
        print(f"q={q} n={n}: int ce^2 over 2pi = {val:.6f} (pi={math.pi:.6f})")
# 3. spectral kernel at q->0 vs theta form
def K_spec(th, thp, tau, q, N=30):
    s = 0.0
    for n in range(0, N):
        a = special.mathieu_a(2*n, q)
        s += special.mathieu_cem(2*n, q, th/2*deg)[0]*special.mathieu_cem(2*n, q, thp/2*deg)[0]*math.exp(-tau*a/8)
    for n in range(1, N):
        b = special.mathieu_b(2*n, q)
        s += special.mathieu_sem(2*n, q, th/2*deg)[0]*special.mathieu_sem(2*n, q, thp/2*deg)[0]*math.exp(-tau*b/8)
    return s/math.pi
def K_theta(th, thp, tau):
    return float(mp.jtheta(3, (th-thp)/2, mp.e**(-tau/2)))/(2*math.pi)
for (th, thp, tau) in ((0.3, 1.9, 0.5), (2.0, 2.0, 1.0), (5.0, 0.4, 0.2)):
    print(f"theta={th},{thp},tau={tau}: spectral(q=0)={K_spec(th,thp,tau,0.0):.10f}  theta3={K_theta(th,thp,tau):.10f}")
# trace check at q=-4 (V0=1): int K(th,th) dth vs sum exp(-tau E_n)
tau = 1.0; q = -4.0
try:
    tr = integrate.quad(lambda th: K_spec(th, th, tau, q, N=15), 0, 2*math.pi, limit=100)[0]
    Z = sum(math.exp(-tau*special.mathieu_a(2*n, q)/8) for n in range(15)) + sum(math.exp(-tau*special.mathieu_b(2*n, q)/8) for n in range(1, 15))
    print(f"q=-4: trace={tr:.8f}  Z={Z:.8f}")
except Exception as e:
    print("q=-4 trace failed:", e)
# 4. negative q behaviour of scipy
for n in (0, 1, 2):
    print(f"a_{2*n}(q=-4)={special.mathieu_a(2*n,-4.0)}  a_{2*n}(q=+4)={special.mathieu_a(2*n,4.0)}   b_{2*n+2}(-4)={special.mathieu_b(2*n+2,-4.0)} b(+4)={special.mathieu_b(2*n+2,4.0)}")
print("ce_0(z=0.7,q=-4):", special.mathieu_cem(0,-4.0,0.7*deg)[0], " vs ce_0(pi/2-z, +4):", special.mathieu_cem(0,4.0,(math.pi/2-0.7)*deg)[0])
print("ce_2(z=0.7,q=-4):", special.mathieu_cem(2,-4.0,0.7*deg)[0], " vs (-1)^1 ce_2(pi/2-z, +4):", -special.mathieu_cem(2,4.0,(math.pi/2-0.7)*deg)[0])
# 5. harmonic approx check for V0=10: E_0 ~ -V0 + sqrt(V0)/2 ; from Mathieu a_0(-40)/8
print("V0=10: a_0(q=-40)/8 =", special.mathieu_a(0,-40.0)/8, "  a_0(q=+40)/8 =", special.mathieu_a(0,40.0)/8, "  harmonic -V0+sqrt(V0)/2 =", -10+math.sqrt(10)/2)