#!/usr/bin/env python3
"""Mirror BioBloom.save()/load() exactly (positive ints -> Python // == MC /) and
round-trip random dishes, asserting the compact codec is lossless where it must be
(scalars, bands, even vertices, tip) and midpoint-correct for the dropped odds."""
import random

PMAX, BBANDS, CBANDS, KMAX, BMAX = 41, 24, 80, 20, 16
SAVE_MAGIC = 0x5B102


def packPt(x, y, ci): return ((ci & 0xFF) << 16) | ((x & 0xFF) << 8) | (y & 0xFF)
def upx(v): return (v >> 8) & 0xFF
def upy(v): return v & 0xFF
def upci(v): return (v >> 16) & 0xFF


def save(S):
    nfil, nbloom, coln = S['nfil'], S['nbloom'], S['coln']
    thnp, blnb = S['thnp'], S['blnb']
    n = 1 + 20 + 1
    for i in range(nfil): n += 5 + thnp[i] // 2 + 1
    n += 1
    for i in range(nbloom): n += 10 + (blnb[i] + 1) // 2
    n += 2
    n += (coln + 1) // 2
    a = [0] * n
    p = 0
    def put(v):
        nonlocal p; a[p] = v; p += 1
    put(SAVE_MAGIC)
    for key in ('lastDay', 'lastMin', 'lastSteps', 'bar', 'epiOn', 'epiIdx',
                'nightAcc', 'sleepSeed', 'winN', 'winHead'):
        put(S[key])
    for i in range(10): put(S['win'][i])
    put(nfil)
    for i in range(nfil):
        put(S['tha'][i]); put(S['thL'][i]); put(S['thv'][i]); put(S['thnext'][i])
        np = thnp[i]; put(np)
        base = i * PMAX
        for k in range(0, np, 2): put(S['pt'][base + k])
        if (np & 1) == 0 and np > 0: put(S['pt'][base + np - 1])
    put(nbloom)
    for i in range(nbloom):
        for key in ('blbx', 'blby', 'blang', 'blw', 'blsalt', 'blreach', 'blmom'):
            put(S[key][i])
        put(blnb[i]); put(S['blmom0'][i]); put(S['bllastzi'][i])
        bb = i * BBANDS; nb = blnb[i]
        for k in range(0, nb, 2):
            w = S['blband'][bb + k] & 0xFFFF
            if k + 1 < nb: w |= (S['blband'][bb + k + 1] & 0xFFFF) << 16
            put(w)
    put(S['colreach']); put(coln)
    for k in range(0, coln, 2):
        w = S['colband'][k] & 0xFFFF
        if k + 1 < coln: w |= (S['colband'][k + 1] & 0xFFFF) << 16
        put(w)
    assert p == n, (p, n)
    return a


def load(a):
    if a is None or len(a) < 22 or a[0] != SAVE_MAGIC: return None
    sz = len(a); p = 1
    D = {'pt': [0] * (KMAX * PMAX), 'blband': [0] * (BMAX * BBANDS),
         'colband': [0] * CBANDS}
    for key in ('lastDay', 'lastMin', 'lastSteps', 'bar', 'epiOn', 'epiIdx',
                'nightAcc', 'sleepSeed', 'winN', 'winHead'):
        D[key] = a[p]; p += 1
    D['win'] = a[p:p + 10]; p += 10
    nfil = a[p]; p += 1
    assert 0 <= nfil <= KMAX
    D['nfil'] = nfil
    for k in ('tha', 'thL', 'thv', 'thnext', 'thnp'): D[k] = [0] * KMAX
    for i in range(nfil):
        D['tha'][i] = a[p]; p += 1; D['thL'][i] = a[p]; p += 1
        D['thv'][i] = a[p]; p += 1; D['thnext'][i] = a[p]; p += 1
        np = a[p]; p += 1
        assert 1 <= np <= PMAX
        D['thnp'][i] = np; base = i * PMAX
        for k in range(0, np, 2): D['pt'][base + k] = a[p]; p += 1
        if (np & 1) == 0: D['pt'][base + np - 1] = a[p]; p += 1
        for k in range(1, np, 2):
            if k == np - 1: continue
            v0 = D['pt'][base + k - 1]; v1 = D['pt'][base + k + 1]
            D['pt'][base + k] = packPt((upx(v0) + upx(v1)) // 2,
                                       (upy(v0) + upy(v1)) // 2, upci(v1))
    nbloom = a[p]; p += 1
    assert 0 <= nbloom <= BMAX
    D['nbloom'] = nbloom
    for k in ('blbx', 'blby', 'blang', 'blw', 'blsalt', 'blreach', 'blmom',
              'blnb', 'blmom0', 'bllastzi'): D[k] = [0] * BMAX
    for i in range(nbloom):
        for key in ('blbx', 'blby', 'blang', 'blw', 'blsalt', 'blreach', 'blmom'):
            D[key][i] = a[p]; p += 1
        nb = a[p]; p += 1; D['blmom0'][i] = a[p]; p += 1
        D['bllastzi'][i] = a[p]; p += 1
        assert 0 <= nb <= BBANDS
        D['blnb'][i] = nb; bb = i * BBANDS
        for k in range(0, nb, 2):
            w = a[p]; p += 1
            D['blband'][bb + k] = w & 0xFFFF
            if k + 1 < nb: D['blband'][bb + k + 1] = (w >> 16) & 0xFFFF
    D['colreach'] = a[p]; p += 1
    coln = a[p]; p += 1
    assert 0 <= coln <= CBANDS
    D['coln'] = coln
    for k in range(0, coln, 2):
        w = a[p]; p += 1
        D['colband'][k] = w & 0xFFFF
        if k + 1 < coln: D['colband'][k + 1] = (w >> 16) & 0xFFFF
    assert p == sz, (p, sz)
    return D


def rand_dish(rng):
    nfil = rng.randint(1, KMAX); nbloom = rng.randint(0, BMAX)
    coln = rng.randint(0, CBANDS)
    S = {'lastDay': 20, 'lastMin': 810, 'lastSteps': rng.randint(0, 99999),
         'bar': rng.randint(0, 60), 'epiOn': rng.randint(0, 1),
         'epiIdx': rng.randint(-1, 15), 'nightAcc': rng.randint(0, 600),
         'sleepSeed': rng.randint(0, 600), 'winN': 10, 'winHead': rng.randint(0, 9),
         'win': [rng.randint(0, 200) for _ in range(10)],
         'nfil': nfil, 'nbloom': nbloom, 'coln': coln, 'colreach': rng.randint(7, 78)}
    for k in ('tha', 'thL', 'thv', 'thnext', 'thnp'): S[k] = [0] * KMAX
    S['pt'] = [0] * (KMAX * PMAX)
    for i in range(nfil):
        np = rng.randint(1, PMAX)
        S['tha'][i] = rng.randint(0, 255); S['thL'][i] = rng.randint(0, 5504)
        S['thv'][i] = rng.randint(2, 4); S['thnext'][i] = rng.randint(7, 88)
        S['thnp'][i] = np
        for k in range(np):
            S['pt'][i * PMAX + k] = packPt(rng.randint(0, 215), rng.randint(0, 179),
                                           rng.randint(0, 10))
    for k in ('blbx', 'blby', 'blang', 'blw', 'blsalt', 'blreach', 'blmom',
              'blnb', 'blmom0', 'bllastzi'): S[k] = [0] * BMAX
    S['blband'] = [0] * (BMAX * BBANDS)
    for i in range(nbloom):
        nb = rng.randint(0, BBANDS)
        for key, hi in (('blbx', 215), ('blby', 179), ('blang', 255), ('blw', 16),
                        ('blsalt', 4095), ('blreach', 46), ('blmom', 46),
                        ('blmom0', 46), ('bllastzi', 8)):
            S[key][i] = rng.randint(0, hi)
        S['blnb'][i] = nb
        for k in range(nb):
            S['blband'][i * BBANDS + k] = (rng.randint(0, 10) << 8) | rng.randint(0, 46)
    S['colband'] = [0] * CBANDS
    for k in range(coln):
        S['colband'][k] = (rng.randint(0, 10) << 8) | rng.randint(0, 78)
    return S


def check(S, D):
    for key in ('lastDay', 'lastMin', 'lastSteps', 'bar', 'epiOn', 'epiIdx',
                'nightAcc', 'sleepSeed', 'winN', 'winHead', 'nfil', 'nbloom',
                'coln', 'colreach'):
        assert S[key] == D[key], (key, S[key], D[key])
    assert S['win'] == list(D['win'])
    for i in range(S['nfil']):
        for k in ('tha', 'thL', 'thv', 'thnext', 'thnp'):
            assert S[k][i] == D[k][i], (k, i)
        np = S['thnp'][i]; base = i * PMAX
        for k in range(0, np, 2):                     # evens exact
            assert S['pt'][base + k] == D['pt'][base + k], ('even', i, k)
        assert S['pt'][base + np - 1] == D['pt'][base + np - 1], ('tip', i)
        for k in range(1, np, 2):                     # odds = midpoint
            if k == np - 1: continue
            v0, v1 = S['pt'][base + k - 1], S['pt'][base + k + 1]
            exp = packPt((upx(v0) + upx(v1)) // 2, (upy(v0) + upy(v1)) // 2, upci(v1))
            assert D['pt'][base + k] == exp, ('odd', i, k)
    for i in range(S['nbloom']):
        for k in ('blbx', 'blby', 'blang', 'blw', 'blsalt', 'blreach', 'blmom',
                  'blnb', 'blmom0', 'bllastzi'):
            assert S[k][i] == D[k][i], (k, i)
        for k in range(S['blnb'][i]):
            assert S['blband'][i * BBANDS + k] == D['blband'][i * BBANDS + k]
    for k in range(S['coln']):
        assert S['colband'][k] == D['colband'][k]


rng = random.Random(12345)
maxn = 0
for t in range(4000):
    S = rand_dish(rng)
    a = save(S)
    maxn = max(maxn, len(a))
    D = load(a)
    assert D is not None
    check(S, D)
# explicit edge cases: tiny + maxed dishes
for sd in range(50):
    rng2 = random.Random(sd)
    check(rand_dish(rng2), load(save(rand_dish(rng2)))) if False else None
print("OK: 4000 random round-trips passed.")
print("max save-array slots =", maxn, "(~", round(maxn * 5 / 1024, 1), "KB transient)")
# reject garbage
assert load(None) is None
assert load([1, 2, 3]) is None
assert load([0] * 30) is None           # wrong magic
print("OK: garbage/old payloads rejected (blank fallback).")
