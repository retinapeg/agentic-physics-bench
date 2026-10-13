# Adversarial numerical checks for V3_DESIGN_REVIEW.md section 7 (written by Claude, 2026-10-06)
import numpy as np, mpmath as mp, sympy as sp
from scipy.special import mathieu_a, mathieu_b, mathieu_cem, mathieu_sem
from scipy.integrate import quad
from scipy.linalg import expm, eigh
DEG = 180/np.pi
np.set_printoptions(precision=3, linewidth=140)

print("=== 1. Substitution theta=2z (sympy) ===")
th, z, E, V0 = sp.symbols('theta z E V0', real=True)
w = sp.Function('w')
expr = -sp.Rational(1,2)*sp.diff(w(th/2), th, 2) - V0*sp.cos(th)*w(th/2) - E*w(th/2)   # (H-E)psi with psi(theta)=w(theta/2)
expr = sp.simplify(expr.subs(th, 2*z).doit()*(-8))
print("(-8)*(H-E)psi in z:", expr)
print("Mathieu form w'' + (a - 2q cos2z) w = 0  =>  a = 8E,  -2q = 8V0  =>  q = -4V0")

print("\n=== 2. Periodicity (scipy, degrees) ===")
q = -0.4
for n in range(0,5):
    zs = np.linspace(0, 2*np.pi, 7)
    ce = mathieu_cem(n, abs(q), zs*DEG)[0]; cep = mathieu_cem(n, abs(q), (zs+np.pi)*DEG)[0]
    print(f"ce_{n}: max|ce(z+pi)-ce(z)| = {np.max(np.abs(cep-ce)):.2e}   max|ce(z+pi)+ce(z)| = {np.max(np.abs(cep+ce)):.2e}")
for n in range(1,5):
    zs = np.linspace(0, 2*np.pi, 7)
    se = mathieu_sem(n, abs(q), zs*DEG)[0]; sep = mathieu_sem(n, abs(q), (zs+np.pi)*DEG)[0]
    print(f"se_{n}: max|se(z+pi)-se(z)| = {np.max(np.abs(sep-se)):.2e}   max|se(z+pi)+se(z)| = {np.max(np.abs(sep+se)):.2e}")

print("\n=== 2b. Does scipy accept negative q? ===")
for fn,name in [(mathieu_a,'a'),(mathieu_b,'b')]:
    print(name, "n=0..4 at q=-4:", [fn(n,-4.0) for n in range(0 if name=='a' else 1,5)])
    print(name, "n=0..4 at q=+4:", [fn(n,+4.0) for n in range(0 if name=='a' else 1,5)])
print("ce_0(z=0, q=-4):", mathieu_cem(0,-4.0,0.0), " ce_0(z=90deg,q=-4):", mathieu_cem(0,-4.0,90.0))
print("ce_0(z=0, q=+4):", mathieu_cem(0,4.0,0.0), " ce_0(z=90deg,q=+4):", mathieu_cem(0,4.0,90.0))

print("\n=== 3. Normalisation int_0^{2pi} ce_n^2 dz (scipy) ===")
for qq in [0.0, 0.4, 4.0, 40.0]:
    for n in [0,2,4,6]:
        I,err = quad(lambda x: mathieu_cem(n,qq,x*DEG)[0]**2, 0, 2*np.pi, limit=200)
        Ih,_ = quad(lambda x: mathieu_cem(n,qq,x*DEG)[0]**2, 0, np.pi, limit=200)
        print(f"q={qq:5.1f} ce_{n}: int_0^2pi = {I:.12f} (pi-I={np.pi-I:.1e}); int_0^pi = {Ih:.12f} (pi/2-I={np.pi/2-Ih:.1e})")
    for n in [2,4,6]:
        I,err = quad(lambda x: mathieu_sem(n,qq,x*DEG)[0]**2, 0, 2*np.pi, limit=200)
        print(f"q={qq:5.1f} se_{n}: int_0^2pi = {I:.12f} (pi-I={np.pi-I:.1e})")
    # odd order too, for completeness
    I,_ = quad(lambda x: mathieu_cem(1,qq,x*DEG)[0]**2, 0, 2*np.pi, limit=200)
    print(f"q={qq:5.1f} ce_1: int_0^2pi = {I:.12f} (pi-I={np.pi-I:.1e})")

print("\n=== 6. q=0 limits ===")
zs = np.array([0.0, 0.3, 1.1, 2.0, 3.0])
print("max|ce_0(z,0)-1/sqrt2| =", np.max(np.abs(mathieu_cem(0,0.0,zs*DEG)[0]-1/np.sqrt(2))))
for n in [1,2,3,4,6]:
    print(f"max|ce_{n}(z,0)-cos {n}z| = {np.max(np.abs(mathieu_cem(n,0.0,zs*DEG)[0]-np.cos(n*zs))):.2e}",
          f"  max|se_{n}(z,0)-sin {n}z| = {np.max(np.abs(mathieu_sem(n,0.0,zs*DEG)[0]-np.sin(n*zs))):.2e}",
          f"  a_{n}(0)-{n}^2 = {mathieu_a(n,0.0)-n*n:.1e}  b_{n}(0)-{n}^2 = {mathieu_b(n,0.0)-n*n:.1e}")
print("a_0(0) =", mathieu_a(0,0.0))

print("\n=== 5. Symmetry a_2n(-q)=a_2n(q), b_2n(-q)=b_2n(q); eigenfunctions under z->pi/2-z ===")
for qq in [0.4, 4.0, 40.0]:
    da = [abs(mathieu_a(2*n,-qq)-mathieu_a(2*n,qq)) for n in range(0,6)]
    db = [abs(mathieu_b(2*n,-qq)-mathieu_b(2*n,qq)) for n in range(1,6)]
    dodd = [mathieu_a(2*n+1,-qq)-mathieu_b(2*n+1,qq) for n in range(0,4)]
    print(f"q={qq}: max|a_2n(-q)-a_2n(q)|={max(da):.1e}  max|b_2n(-q)-b_2n(q)|={max(db):.1e}  a_(2n+1)(-q)-b_(2n+1)(q)={np.max(np.abs(dodd)):.1e}  (odd orders swap)")
    zs = np.linspace(0, 2*np.pi, 13)
    for n in range(0,4):
        lhs = mathieu_cem(2*n,-qq,zs*DEG)[0]; rhs = (-1)**n*mathieu_cem(2*n,qq,(np.pi/2-zs)*DEG)[0]
        print(f"   ce_{2*n}(z,-q) vs (-1)^n ce_{2*n}(pi/2-z,q): max diff {np.max(np.abs(lhs-rhs)):.1e}; vs +ce(pi/2-z,q): {np.max(np.abs(lhs-mathieu_cem(2*n,qq,(np.pi/2-zs)*DEG)[0])):.1e}")
    for n in range(1,4):
        lhs = mathieu_sem(2*n,-qq,zs*DEG)[0]; rhs = (-1)**(n-1)*mathieu_sem(2*n,qq,(np.pi/2-zs)*DEG)[0]
        print(f"   se_{2*n}(z,-q) vs (-1)^(n-1) se_{2*n}(pi/2-z,q): max diff {np.max(np.abs(lhs-rhs)):.1e}; vs +se(pi/2-z,q): {np.max(np.abs(lhs-mathieu_sem(2*n,qq,(np.pi/2-zs)*DEG)[0])):.1e}")