# Test of Duru (arXiv:1911.07074) eq. (16): kappa = sum_{L,k} (1/2pi) e^{-i L^2 T/(2mu)} i^k J_k(-alpha T) e^{iL(th_b-th_a)+ik th_b}, V = alpha cos(theta), mu=1
# Our H = -1/2 d^2 - V0 cos(theta)  =>  alpha = -V0.  Compare with the exact kernel exp(-iTH) from the Fourier matrix (independent).
import numpy as np
from scipy.special import jv, iv
from scipy.linalg import expm
def H_matrix(V0, M=60):
    m = np.arange(-M, M+1); H = np.diag(m**2/2.0)
    for i in range(len(m)-1): H[i,i+1]=H[i+1,i]=-V0/2.0
    return m, H
def K_exact_realtime(tha, thb, T, V0, M=60):
    m, H = H_matrix(V0, M); U = expm(-1j*T*H)
    phib = np.exp(1j*m*thb)/np.sqrt(2*np.pi); phia = np.exp(1j*m*tha)/np.sqrt(2*np.pi)
    return phib @ U @ np.conj(phia)     # <thb| e^{-iTH} |tha>
def K_duru16(tha, thb, T, alpha, N=60):
    L = np.arange(-N, N+1); k = np.arange(-N, N+1)
    sL = np.sum(np.exp(-1j*L**2*T/2)*np.exp(1j*L*(thb-tha)))
    sk = np.sum((1j)**k * jv(k, -alpha*T) * np.exp(1j*k*thb))
    return sL*sk/(2*np.pi)
def K_free_realtime(tha, thb, T, N=60):
    L = np.arange(-N, N+1); return np.sum(np.exp(-1j*L**2*T/2)*np.exp(1j*L*(thb-tha)))/(2*np.pi)
V0 = 1.0; alpha = -V0
print("Real time, V0=1 (alpha=-1). Duru(16) vs exact expm kernel vs Trotter product K_free * exp(-i T alpha cos th_b):")
for tha, thb, T in [(0.3, 1.7, 0.2), (0.0, 0.0, 0.5), (2.0, -1.0, 1.0), (1.0, 1.0, 0.1), (0.5, 2.5, 0.05)]:
    kd = K_duru16(tha, thb, T, alpha); ke = K_exact_realtime(tha, thb, T, V0); kt = K_free_realtime(tha,thb,T)*np.exp(-1j*T*alpha*np.cos(thb))
    print(f"  tha={tha} thb={thb} T={T}: |Duru-exact|={abs(kd-ke):.3e}  |Duru - Trotter|={abs(kd-kt):.1e}  |exact|={abs(ke):.3f}")
print("\nSchrodinger residual of Duru(16): R = (-1/2 d^2/dthb^2 + alpha cos thb - i d/dT) kappa, finite differences at (0.3,1.7,T=0.5):")
h=1e-3; tha, thb, T = 0.3, 1.7, 0.5
f = lambda b,t: K_duru16(tha,b,t,alpha)
d2 = (f(thb+h,T)-2*f(thb,T)+f(thb-h,T))/h**2; dT = (f(thb,T+h)-f(thb,T-h))/(2*h)
R = -0.5*d2 + alpha*np.cos(thb)*f(thb,T) - 1j*dT
g = lambda b,t: K_exact_realtime(tha,b,t,V0)
d2e = (g(thb+h,T)-2*g(thb,T)+g(thb-h,T))/h**2; dTe = (g(thb,T+h)-g(thb,T-h))/(2*h)
Re = -0.5*d2e + alpha*np.cos(thb)*g(thb,T) - 1j*dTe
print(f"  |R(Duru)| = {abs(R):.3e}    |R(exact expm kernel)| = {abs(Re):.3e} (finite-difference noise level)")
print("\nImaginary time: Duru(16) continued (T=-i tau) collapses to K0(tau) * exp(tau V0 cos th_b):")
from mpmath import jtheta, mpf, e, pi as mpi
tau = 0.5
K0 = float(jtheta(3, mpf(1.7-0.3)/2, e**(-mpf(tau)/2))/(2*mpi))
kcoll = K0*np.exp(tau*V0*np.cos(1.7))
m,H = H_matrix(V0,60); U = expm(-tau*H); mm = np.arange(-60,61)
kex = (np.exp(1j*mm*1.7)/np.sqrt(2*np.pi)) @ U @ np.conj(np.exp(1j*mm*0.3)/np.sqrt(2*np.pi))
print(f"  collapsed Duru = {kcoll:.6f}   exact = {kex.real:.6f}   rel. error = {abs(kcoll-kex.real)/abs(kex.real):.2%}")