from /Users/matt/Documents/charm/auto_outsrc/parser/SW05/userFuncs import *

from toolbox.pairinggroup import PairingGroup, ZR, G1, G2, GT, pair, SymEnc, SymDec
from toolbox.secretutil import SecretUtil
from toolbox.iterate import dotprod2
from charm.pairing import hash as DeriveKey
from charm.engine.util import objectToBytes, bytesToObject
from builtInFuncs import *


from charm.toolbox.pairinggroup import *
from charm.core.engine.util import *
from charm.core.math.integer import randomBits

group = None

N = 2

secparam = 80

Eprime = {}
loopVar = {}
Eprimeprime = {}
D = {}
wHash = {}
E = {}
N = {}
wPrimeHash = {}
evalTVar = {}
t = {}
coeffs = {}
S = {}

def setup(n):
    global t

    t = {}

    input = n
    g = group.random(G1)
    y = group.random(ZR)
    g1 = (g ** y)
    g2 = group.random(G2)
    for i in range(0, n+1):
        t[i] = group.random(G2)
    dummyVar = group.random(ZR)
    pk = [g, g1, g2, t]
    mk = [y, dummyVar]
    output = (pk, mk)
    return output

def evalT(pk, n, x):
    global loopVar
    global N
    global t
    global coeffs

    Nint = {}

    input = [pk, n, x]
    t = pk[3]
    for i in range(0, n+1):
        N[i] = (i+1)
        Nint[i] = (i + 1)
    coeffs = recoverCoefficients(N)
    prodResult = group.init(G2)
    lenNint = len(Nint)
    for i in range(0, lenNint):
        loopVar = Nint[i]
        j = (i)
        iMinusOne = i-1
        prodResult = (prodResult * (t[iMinusOne] ** coeffs[j]))
    T = ((pk[2] ** (x * n)) * prodResult)
    output = T
    return output

def extract(mk, ID, pk, dOver, n):
    global loopVar
    global D
    global wHash
    global evalTVar

    q = {}
    D = {}
    wHash = {}
    d = {}

    input = [mk, ID, pk, dOver, n]
    lenID = len(ID)
    for i in range(0, lenID):
        loopVar = ID[i]
        wHash[i] = group.hash(loopVar, ZR)
    r = group.random(ZR)
    for i in range(0, dOver):
        q[i] = group.random(ZR)
    q[0] = mk[0]
    shares = genShares(mk[0], dOver, n, q, wHash)
    wHashLen = len(wHash)
    for i in range(0, wHashLen):
        loopVar = wHash[i]
        evalTVar = evalT(pk, n, loopVar)
        D[loopVar] = ((pk[2] ** shares[i][1]) * (evalTVar ** r))
        d[loopVar] = (pk[0] ** r)
    sk = [wHash, D, d]
    output = sk
    return output

def encrypt(pk, wPrime, M, n):
    global Eprime
    global loopVar
    global Eprimeprime
    global E
    global wPrimeHash
    global evalTVar

    E = {}
    wPrimeHash = {}

    input = [pk, wPrime, M, n]
    wPrimeLen = len(wPrime)
    for i in range(0, wPrimeLen):
        loopVar = wPrime[i]
        wPrimeHash[i] = group.hash(loopVar, ZR)
    s = group.random(ZR)
    Eprime = (M * (pair(pk[1], pk[2]) ** s))
    Eprimeprime = (pk[0] ** s)
    wPrimeHashLen = len(wPrimeHash)
    for i in range(0, wPrimeHashLen):
        loopVar = wPrimeHash[i]
        evalTVar = evalT(pk, n, loopVar)
        E[i] = (evalTVar ** s)
    CT = [wPrimeHash, Eprime, Eprimeprime, E]
    output = CT
    return output

def decrypt(pk, sk, CT, w, d):
    global Eprime
    global loopVar
    global Eprimeprime
    global D
    global wHash
    global E
    global wPrimeHash
    global coeffs
    global S

    input = [pk, sk, CT, w, d]
    wPrimeHash = CT[0]
    Eprime = CT[1]
    Eprimeprime = CT[2]
    E = CT[3]
    wHash = sk[0]
    D = sk[1]
    d = sk[2]
    S = intersection_subset(w, CT[0], d)
    coeffs = recoverCoefficients(S)
    prod = group.init(GT)
    SLen = len(S)
    for i in range(0, SLen):
        loopVar = S[i]
        prod = (prod * ((pair(d[loopVar], E[loopVar]) / pair(CT[2], D[loopVar])) ** coeffs[loopVar]))
    M = (CT[1] * prod)
    output = M
    return output

def SmallExp(bits=80):
    return group.init(ZR, randomBits(bits))

def main():
    global group
    group = PairingGroup(secparam)

if __name__ == '__main__':
    main()
