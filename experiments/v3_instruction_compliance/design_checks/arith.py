from math import comb
from fractions import Fraction
print("== Clopper-Pearson upper bound for 0/n, two-sided 95%: 1-0.025**(1/n)")
for n in (36,54,72,108,12):
    print(n, round(100*(1-0.025**(1/n)),2))
print("== Fisher one-sided, 0/20 vs x/20, P(X>=x | hypergeom N=40, K=x successes, n=20 draws)")
def fisher_upper(x, n1=20, n2=20):
    # table: group1 0 successes, group2 x successes; total successes x; total N=40
    N=n1+n2; K=x
    # P(group2 successes >= x) = sum over j>=x of C(K,j)C(N-K,n2-j)/C(N,n2); j max = K
    return sum(comb(K,j)*comb(N-K,n2-j) for j in range(x,K+1))/comb(N,n2)
for x in (3,4,5,6):
    print(x, round(fisher_upper(x),4))
print("== sign flip 2^-k")
for k in (4,5,6,7): print(k, 2**-k, round(2**-k,4))
print("Holm thresholds Arm A: 0.05/3, 0.05/2, 0.05 =", 0.05/3, 0.025, 0.05)
print("== label permutation C(12-k,6-k)/924")
for k in (1,2,3,4,5,6): print(k, comb(12-k,6-k), round(comb(12-k,6-k)/924,4))
print("== cell-rate SE max")
import math
print("indep n=36 p=.5:", round(math.sqrt(.25/36),3), " perfectly correlated n=12:", round(math.sqrt(.25/12),3))
print("== episode arithmetic")
print("5*12*3 =",5*12*3, "x2 =",5*12*3*2)
print("5*18*3 =",5*18*3, "x2 =",5*18*3*2)
print("5*12*1 =",5*12*1, "x2 =",5*12*2)
print("ArmB 3*2*2*5 =",3*2*2*5)
print("pilot 3*5*1=",3*5, "x2=",3*5*2, "; 3*4=",12,"x2=",24, "; ArmB dev 3*2=",6)
print("pilot total 30+6=",36, "+1 probe=",37)
print("programme 360+60+37=",360+60+37)
print("== HA4 power under independence: hard rate 10%, easy 0, 6 tasks x 3 reps, need >=4 hard tasks with >=1 violation")
p_task = 1-(0.9**3)
print("P(task has >=1 violation)=",round(p_task,4))
pw = sum(comb(6,k)*p_task**k*(1-p_task)**(6-k) for k in range(4,7))
print("P(k>=4 of 6)=",round(pw,4))
p_task2 = 1-(0.8**3)
pw2 = sum(comb(6,k)*p_task2**k*(1-p_task2)**(6-k) for k in range(4,7))
print("hard rate 20%: P(task>=1)=",round(p_task2,4)," P(k>=4)=",round(pw2,4))
print("== Fisher exact power when OPEN truly 0, CLOSED rate r, reject at >=5/20")
def power(r):
    return sum(comb(20,j)*r**j*(1-r)**(20-j) for j in range(5,21))
for r in (0.2,0.25,0.3,0.31,0.4): print(r, round(power(r),3))