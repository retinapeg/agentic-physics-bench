# Kernel checks for section 7.2/7.3 (written by Claude, 2026-10-06)
import numpy as np, mpmath as mp
from scipy.special import mathieu_a, mathieu_b, mathieu_cem, mathieu_sem
from scipy.linalg import expm, eigh
DEG = 180/np.pi
mp.mp.dps = 40

def K_theta(th, thp, tau):      # (1/2pi) theta3((th-thp)/2, nome e^{-tau/2}), mpmath
    return mp.jtheta(3, mp.mpf(th-thp)/2, mp.e**(-mp.mpf(tau)/2))/(2*mp.pi)
def K_gauss(th, thp, tau, N=60):  # winding/image sum
    s = mp.mpf(0)
    for n in range(-N, N+1):
        s += mp.e**(-(mp.mpf(th-thp)+2*mp.pi*n)**2/(2*mp.mpf(tau)))
    return s/mp.sqrt(2*mp.pi*mp.mpf(tau))
def K_fourier(th, thp, tau, N=200):  # spectral sum over m
    s = mp.mpf(1)
    for m in range(1, N+1):
        s += 2*mp.cos(m*mp.mpf(th-thp))*mp.e**(-m*m*mp.mpf(tau)/2)
    return s/(2*mp.pi)
def K_mathieu(th, thp, tau, q, N=None, prefactor=1/np.pi, shift=False):
    # spectral sum with scipy Mathieu functions; argument theta/2 in degrees; q as given
    # shift=True: use the q -> -q equivalence: functions of -q at (pi - theta)/2
    if N is None: N = int(np.sqrt(2*40/tau))+3
    z, zp = th/2, thp/2
    if shift: q = -q; z, zp = (np.pi-th)/2, (np.pi-thp)/2
    s = 0.0
    for n in range(0, N+1):
        s += mathieu_cem(2*n, q, z*DEG)[0]*mathieu_cem(2*n, q, zp*DEG)[0]*np.exp(-tau*mathieu_a(2*n, q)/8)
    for n in range(1, N+1):
        s += mathieu_sem(2*n, q, z*DEG)[0]*mathieu_sem(2*n, q, zp*DEG)[0]*np.exp(-tau*mathieu_b(2*n, q)/8)
    return prefactor*s

def H_matrix(V0, M=40):
    m = np.arange(-M, M+1)
    H = np.diag(m**2/2.0)
    for i in range(len(m)-1):
        H[i, i+1] = H[i+1, i] = -V0/2.0
    return m, H
def K_matrix(th, thp, tau, V0, M=40):
    m, H = H_matrix(V0, M)
    U = expm(-tau*H)
    phi = np.exp(1j*m*th)/np.sqrt(2*np.pi); phip = np.exp(1j*m*thp)/np.sqrt(2*np.pi)
    return (phi @ U @ np.conj(phip))

pts = [(0.3, 1.7, 0.2), (0.0, 0.0, 0.5), (2.0, -1.0, 1.0), (3.1, 0.2, 2.0), (1.0, 1.0, 0.1), (5.5, 0.4, 0.7)]

print("=== 4a. q=0: Mathieu spectral sum (1/pi prefactor, scipy) vs theta3 vs Gaussian vs Fourier ===")
mx = {'mathieu-theta':0,'gauss-theta':0,'fourier-theta':0}
for th, thp, tau in pts:
    kt = K_theta(th,thp,tau); kg = K_gauss(th,thp,tau); kf = K_fourier(th,thp,tau)
    km = K_mathieu(th,thp,tau,0.0)
    mx['mathieu-theta'] = max(mx['mathieu-theta'], abs(km-float(kt)))
    mx['gauss-theta'] = max(mx['gauss-theta'], float(abs(kg-kt)))
    mx['fourier-theta'] = max(mx['fourier-theta'], float(abs(kf-kt)))
    print(f"th={th} th'={thp} tau={tau}: theta3 form={mp.nstr(kt,17)}  mathieu={km:.16f}  gauss-theta={mp.nstr(kg-kt,3)}  fourier-theta={mp.nstr(kf-kt,3)}")
print("max abs differences:", {k: f"{v:.2e}" for k,v in mx.items()})
print("prefactor test at q=0: with 1/(2pi) instead of 1/pi, diff =", abs(K_mathieu(0.3,1.7,0.2,0.0,prefactor=1/(2*np.pi))-float(K_theta(0.3,1.7,0.2))))

print("\n=== 4c/independent. V0 != 0: Mathieu spectral sum vs Fourier-matrix expm kernel (independent of scipy Mathieu) ===")
for V0 in [0.1, 1.0, 10.0]:
    q = -4*V0
    mxd = 0; mxs = 0; mxi = 0
    for th, thp, tau in pts:
        km = K_mathieu(th,thp,tau,q)
        kmat = K_matrix(th,thp,tau,V0, M=60)
        ksh = K_mathieu(th,thp,tau,q,shift=True)
        mxd = max(mxd, abs(km-kmat.real)); mxi = max(mxi, abs(kmat.imag)); mxs = max(mxs, abs(km-ksh))
        print(f"V0={V0} th={th} th'={thp} tau={tau}: mathieu={km:.14f} matrix={kmat.real:.14f} diff={km-kmat.real:.1e} shifted(+q,pi-theta) diff={km-ksh:.1e}")
    print(f"V0={V0}: max|mathieu - matrix| = {mxd:.2e}; max|Im matrix| = {mxi:.1e}; max|q<0 form - (+q, pi-theta) form| = {mxs:.2e}")
    # wrong-prefactor sensitivity
    km2 = K_mathieu(0.3,1.7,0.5,q,prefactor=1/(2*np.pi)); kmat = K_matrix(0.3,1.7,0.5,V0,M=60).real
    print(f"V0={V0}: with prefactor 1/(2pi) the diff would be {km2-kmat:.3e} (so 1/pi is pinned)")

print("\n=== 4b. Trace: int_0^{2pi} K(th,th;tau) dth vs sum exp(-tau E) vs trace expm ===")
for V0 in [0.0, 1.0, 10.0]:
    q = -4*V0
    for tau in [0.3, 1.0, 3.0]:
        N = int(np.sqrt(2*40/tau))+3
        grid = np.linspace(0, 2*np.pi, 4001)[:-1]; h = grid[1]-grid[0]
        diag = np.array([K_mathieu(t,t,tau,q,N=N) for t in grid])
        tr_num = diag.sum()*h
        spec = sum(np.exp(-tau*mathieu_a(2*n,q)/8) for n in range(0,N+1)) + sum(np.exp(-tau*mathieu_b(2*n,q)/8) for n in range(1,N+1))
        m, H = H_matrix(V0, 60); tr_mat = np.trace(expm(-tau*H))
        print(f"V0={V0} tau={tau}: int K(th,th) = {tr_num:.13f}  sum e^-tauE = {spec:.13f}  diff={tr_num-spec:.1e}   tr expm = {tr_mat:.13f} diff={spec-tr_mat:.1e}")

print("\n=== spectrum: eigenvalues of H (Fourier matrix) vs {a_2n/8} U {b_2n/8}, q=-4V0 ===")
for V0 in [0.1, 1.0, 10.0]:
    q = -4*V0
    m, H = H_matrix(V0, 80); ev = np.sort(eigh(H, eigvals_only=True))[:12]
    mat = sorted([mathieu_a(2*n,q)/8 for n in range(0,7)] + [mathieu_b(2*n,q)/8 for n in range(1,7)])[:12]
    print(f"V0={V0}: max|E_matrix - E_mathieu| (lowest 12) = {np.max(np.abs(ev-np.array(mat))):.2e}")
    print("   lowest 6:", np.array(mat[:6]))
    # which label each level is
    lab = sorted([(mathieu_a(2*n,q)/8, f"a{2*n}") for n in range(0,7)] + [(mathieu_b(2*n,q)/8, f"b{2*n}") for n in range(1,7)])[:8]
    print("   labels:", [l for _,l in lab])
    # and what would WRONG admissible sets give: include odd orders
    wrong = sorted([mathieu_a(n,q)/8 for n in range(0,12)] + [mathieu_b(n,q)/8 for n in range(1,12)])[:12]
    print(f"   if odd orders were (wrongly) included, max|E_matrix - E| = {np.max(np.abs(ev-np.array(wrong))):.2e}")
    # perturbation theory check at small V0: E0 = -V0^2 + O(V0^4)
    if V0 == 0.1: print(f"   E_0 = {mat[0]:.8f}; 2nd-order PT -V0^2 = {-V0**2:.8f}; a_0 series -q^2/2+7q^4/128 -> /8: {(-q*q/2+7*q**4/128)/8:.8f}")

print("\n=== semigroup check at V0=1: int K(th,th'';t1)K(th'',th';t2) dth'' vs K(th,th';t1+t2) ===")
q=-4.0; th, thp, t1, t2 = 0.4, 2.2, 0.5, 0.8
grid = np.linspace(0, 2*np.pi, 801)[:-1]; h = grid[1]-grid[0]
conv = sum(K_mathieu(th,s,t1,q)*K_mathieu(s,thp,t2,q) for s in grid)*h
print(f"convolution = {conv:.12f}  direct = {K_mathieu(th,thp,t1+t2,q):.12f}  diff = {conv-K_mathieu(th,thp,t1+t2,q):.1e}")