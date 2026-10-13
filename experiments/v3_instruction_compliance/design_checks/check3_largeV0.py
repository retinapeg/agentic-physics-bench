# Large-V0 (section 7.3 R4) and free-particle (8.4) checks (written by Claude, 2026-10-06)
import numpy as np, sympy as sp
from scipy.special import mathieu_a, mathieu_b
print("=== 7. Large V0: pendulum levels vs harmonic ladder E_k ~ -V0 + sqrt(V0)(k+1/2) ===")
for V0 in [10.0, 40.0, 100.0]:
    q = -4*V0; h = np.sqrt(4*V0)
    levels = sorted([(mathieu_a(2*n,q)/8, f"a{2*n}") for n in range(0,6)] + [(mathieu_b(2*n,q)/8, f"b{2*n}") for n in range(1,6)])[:6]
    print(f"V0={V0} (q={q}, h=sqrt|q|={h:.4f}):")
    for k,(E,lab) in enumerate(levels):
        s = 2*k+1
        harm = -V0 + np.sqrt(V0)*(k+0.5)
        # DLMF 28.8.1 next terms, divided by 8:  -(s^2+1)/8/8 - (s^3+3s)/(2^7 h)/8 ... (28.8.1: -(s^2+1)/8 - (s^3+3s)/(2^7 h) - (5s^4+34s^2+9)/(2^12 h^2))
        corr2 = -(s*s+1)/64
        corr3 = -(s**3+3*s)/(2**7*h)/8
        corr4 = -(5*s**4+34*s*s+9)/(2**12*h*h)/8
        print(f"  k={k} {lab}: E={E:.8f}  harmonic={harm:.8f}  E-harm={E-harm:.6f}  28.8.1 next term -(s^2+1)/64={corr2:.6f}  +3 terms={corr2+corr3+corr4:.6f}")
print("\n=== Doublets? a_m vs b_(m+1) at q=40 (both belong to the 2pi-periodic-in-z problem; only even orders are pendulum states) ===")
q=40.0
for m in range(0,5):
    print(f"  a_{m}(40)={mathieu_a(m,q):.10f}  b_{m+1}(40)={mathieu_b(m+1,q):.10f}  split={mathieu_b(m+1,q)-mathieu_a(m,q):.3e}  pendulum member: {'a'+str(m) if m%2==0 else 'b'+str(m+1)}")
print("  => in the pendulum spectrum each harmonic level appears once (a0, b2, a2, b4, a4, ...); the exponentially small a_m-b_{m+1} gap is a tunnelling splitting of the DOUBLE-well problem on z in [0,2pi), not a splitting inside the pendulum spectrum.")
print("  Pendulum level spacing at V0=10:", [f"{x:.5f}" for x in np.diff(sorted([mathieu_a(2*n,-40.0)/8 for n in range(0,4)] + [mathieu_b(2*n,-40.0)/8 for n in range(1,4)]))], " vs sqrt(V0)=", np.sqrt(10))

print("\n=== 11. Free particle kernel (2 pi tau)^(-1/2) exp(-(x-x')^2/(2 tau)) for H=-1/2 d^2/dx^2 ===")
x, xp, tau = sp.symbols('x xp tau', positive=True)
K = (2*sp.pi*tau)**sp.Rational(-1,2)*sp.exp(-(x-xp)**2/(2*tau))
heat = sp.simplify(sp.diff(K,tau) - sp.Rational(1,2)*sp.diff(K,x,2))   # d/dtau K = -H K = +1/2 K_xx
print("  dK/dtau - (1/2) d2K/dx2 =", heat)
print("  int K dx over R =", sp.simplify(sp.integrate(K,(x,-sp.oo,sp.oo))))
print("  tau->0 delta normalisation ok; also check: wrong candidate (4 pi tau)^(-1/2) exp(-(x-x')^2/(4 tau)) solves dK/dtau = K_xx (i.e. H=-d^2/dx^2):",
      sp.simplify(sp.diff((4*sp.pi*tau)**sp.Rational(-1,2)*sp.exp(-(x-xp)**2/(4*tau)),tau) - sp.diff((4*sp.pi*tau)**sp.Rational(-1,2)*sp.exp(-(x-xp)**2/(4*tau)),x,2)))