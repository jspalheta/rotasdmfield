import pandas as pd, numpy as np, json, datetime as dt
from scipy.optimize import milp, LinearConstraint, Bounds, linear_sum_assignment
from scipy.sparse import lil_matrix
from sklearn.cluster import KMeans

df = pd.read_excel('base.xlsx')
df['CEP'] = df['CEP'].astype(str)
N = len(df)
DEVS = ['Altobeli', 'André', 'Fabricio', 'João Victor', 'Rafael', 'Yucannã']
MAP_EXIST = {'Altobeli': 'Altobeli', 'André': 'André', 'Fabricio': 'Fabricio', 'João': 'João Victor',
             'Rafael': 'Rafael', 'Yucannã': 'Yucannã'}
K = 6
CAP = 18
WD = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex']
# Novembro/2026: feriados 02/11 (Finados) e 20/11 (Consciência Negra); 15/11 cai no domingo
HOL = {dt.date(2026, 11, 2), dt.date(2026, 11, 20)}
DATES = [dt.date(2026, 11, d) for d in range(1, 31)
         if dt.date(2026, 11, d).weekday() < 5 and dt.date(2026, 11, d) not in HOL]
assert len(DATES) == 19
DWD = [WD[d.weekday()] for d in DATES]
NDAYS = {w: DWD.count(w) for w in WD}

opts = [set(s.strip() for s in str(v).split('-')) for v in df['Dia de Visita']]
LAT0 = np.deg2rad(16.68)
X = np.c_[df['Latitude'] * 111.0, df['Longitude'] * 111.0 * np.cos(LAT0)]  # km plane
# coordenadas fora da área atendida -> reposiciona no centro do bairro informado (sinalizado)
df['CoordSuspeita'] = False
center = df[(df['Cidade'] == 'Goiânia')]
for i in df.index:
    la, lo_ = df.at[i, 'Latitude'], df.at[i, 'Longitude']
    if not (-16.85 < la < -16.50 and -49.60 < lo_ < -49.10):
        ref = df[(df['Bairro'].isin(['Setor Central', df.at[i, 'Bairro']])) & (df['Cidade'] == df.at[i, 'Cidade']) & (df['Longitude'] < -49.1) & (df['Latitude'] > -16.85)]
        df.at[i, 'LatOrig'], df.at[i, 'LonOrig'] = la, lo_
        df.at[i, 'Latitude'], df.at[i, 'Longitude'] = ref['Latitude'].median(), ref['Longitude'].median()
        df.at[i, 'CoordSuspeita'] = True
        print('coord suspeita', df.at[i, 'Cod. Cliente'], len(ref))
X = np.c_[df['Latitude'] * 111.0, df['Longitude'] * 111.0 * np.cos(LAT0)]
exist = [MAP_EXIST.get(v) for v in df['Atendido por desenvolvedor']]


def solve_assign(cost, nk, lo, hi, groups_caps, lock, forbid=None):
    """x[i,k] binary; each i to one k; lo<=sum_i x[i,k]<=hi[k]; group caps per k; locks."""
    n = cost.shape[0]
    nv = n * nk
    c = cost.ravel()
    rows = []
    A = lil_matrix((n + 2 * nk + nk * len(groups_caps), nv))
    lb, ub = [], []
    r = 0
    for i in range(n):
        A[r, i * nk:(i + 1) * nk] = 1; lb.append(1); ub.append(1); r += 1
    for k in range(nk):
        for i in range(n): A[r, i * nk + k] = 1
        lb.append(lo[k]); ub.append(hi[k]); r += 1
    for k in range(nk):  # placeholder rows unused
        lb.append(-np.inf); ub.append(np.inf); r += 1
    for (members, capk, lok) in groups_caps:
        for k in range(nk):
            for i in members: A[r, i * nk + k] = 1
            lb.append(lok); ub.append(capk); r += 1
    lbv = np.zeros(nv); ubv = np.ones(nv)
    if forbid is not None: ubv[forbid.ravel()] = 0
    for i, k in lock.items():
        lbv[i * nk:(i + 1) * nk] = 0; ubv[i * nk:(i + 1) * nk] = 0
        lbv[i * nk + k] = 1; ubv[i * nk + k] = 1
    res = milp(c, constraints=LinearConstraint(A.tocsr(), lb, ub), integrality=np.ones(nv),
               bounds=Bounds(lbv, ubv), options={'time_limit': 120})
    assert res.success, res.message
    return res.x.reshape(n, nk).argmax(1)


# ---------- 1) Territórios ----------
# Hall-type caps for weekday feasibility per developer
def weekday_groups(idx_list):
    groups = []
    subsets = [{w} for w in WD] + [set(o) for o in {frozenset(o) for o in opts if len(o) > 1}]
    for S in subsets:
        mem = [j for j, i in enumerate(idx_list) if opts[i] <= S]
        capS = sum(NDAYS[w] for w in S) * CAP
        groups.append((mem, capS, -np.inf))
    for w in WD:  # minimum workable load on every weekday
        mem = [j for j, i in enumerate(idx_list) if w in opts[i]]
        groups.append((mem, np.inf, NDAYS[w] * 11))
    return groups


all_idx = list(range(N))
g = weekday_groups(all_idx)
lo = [N // K] * K
hi = [N // K + 1] * K
km = KMeans(K, n_init=20, random_state=7).fit(X)
C = km.cluster_centers_
lock = {}
lab = None
for it in range(8):
    cost = np.linalg.norm(X[:, None, :] - C[None, :, :], axis=2)
    lab = solve_assign(cost, K, lo, hi, g, lock)
    newC = np.array([X[lab == k].mean(0) for k in range(K)])
    if it == 2:
        # map developers to territories maximizing existing clients kept (tie-break: distance)
        M = np.zeros((K, K))
        for i, d in enumerate(exist):
            if d: M[DEVS.index(d), lab[i]] -= 1
        r_, c_ = linear_sum_assignment(M)
        dev_of_terr = {c_[j]: r_[j] for j in range(K)}
        # reorder centroids so that index = developer index
        order = [c_[list(r_).index(d)] for d in range(K)]
        newC = newC[order]
        lock = {i: DEVS.index(d) for i, d in enumerate(exist) if d}
    shift = np.abs(newC - C).max()
    C = newC
    print('iter', it, 'shift', round(shift, 3))
cost = np.linalg.norm(X[:, None, :] - C[None, :, :], axis=2)
lab = solve_assign(cost, K, lo, hi, g, lock)
df['Desenvolvedor'] = [DEVS[k] for k in lab]
print(df['Desenvolvedor'].value_counts())
kept = sum(1 for i, d in enumerate(exist) if d and DEVS[lab[i]] == d)
print('kept existing', kept, 'of', sum(1 for d in exist if d))

# ---------- 2) Agenda diária por desenvolvedor ----------
df['Data'] = None
df['Ordem'] = 0
T = len(DATES)
for k, dev in enumerate(DEVS):
    idx = np.where(lab == k)[0]
    n = len(idx)
    Xi = X[idx]
    allowed = np.array([[DWD[t] in opts[i] for t in range(T)] for i in idx])
    # clientes já atendidos que ficam longe do território: concentra num único dia
    cen = Xi.mean(0)
    far = [j for j, i in enumerate(idx) if exist[i] and np.linalg.norm(Xi[j] - cen) > 6]
    if far:
        common = allowed[far].all(0)
        far_allowed_t = np.where(common)[0]
    # init day centroids: kmeans per weekday on clients that can go that weekday
    Cd = np.zeros((T, 2))
    for w in WD:
        ts = [t for t in range(T) if DWD[t] == w]
        pts = Xi[allowed[:, ts[0]]]
        kk = KMeans(len(ts), n_init=10, random_state=1).fit(pts)
        Cd[ts] = kk.cluster_centers_
    big = 1e4
    for it in range(12):
        if far and it == 1:
            fm = Xi[far].mean(0)
            t_star = int(min(far_allowed_t, key=lambda t: np.linalg.norm(Cd[t] - fm)))
            allowed[far] = False; allowed[far, t_star] = True
            print(dev, 'clientes atendidos fora do território agrupados em', DATES[t_star], len(far))
        cost = np.linalg.norm(Xi[:, None, :] - Cd[None, :, :], axis=2)
        cost = np.where(allowed, cost, big)
        # balance: min per day = 8 (soft enough), max 18
        lo_d = [9] * T
        try:
            a = solve_assign(cost, T, lo_d, [CAP] * T, [], {}, ~allowed)
        except AssertionError:
            print('fallback',dev); a = solve_assign(cost, T, [0] * T, [CAP] * T, [], {}, ~allowed)
        newCd = np.array([Xi[a == t].mean(0) if (a == t).any() else Cd[t] for t in range(T)])
        if it > 1 and np.abs(newCd - Cd).max() < 1e-3: break
        Cd = newCd
    assert allowed[np.arange(n), a].all()
    # order dates within same weekday: put "nearest to territory centre" first? keep geographic sweep west->east
    for w in WD:
        ts = [t for t in range(T) if DWD[t] == w]
        cents = sorted(ts, key=lambda t: (Cd[t][1]))  # by longitude-ish
        remap = {old: new for old, new in zip(cents, ts)}
        a = np.array([remap.get(t, t) if DWD[t] == w else t for t in a])
    for j, i in enumerate(idx):
        df.at[i, 'Data'] = DATES[a[j]]


# ---------- 3) Ordem de visita (open-path TSP, NN + 2-opt) ----------
def path_len(P, order):
    return sum(np.linalg.norm(P[order[i]] - P[order[i + 1]]) for i in range(len(order) - 1))


def tsp_open(P):
    n = len(P)
    if n <= 2: return list(range(n))
    D = np.linalg.norm(P[:, None] - P[None], axis=2)
    best = None
    for s in range(n):
        o = [s]; left = set(range(n)) - {s}
        while left:
            nx = min(left, key=lambda j: D[o[-1], j]); o.append(nx); left.remove(nx)
        improved = True
        while improved:
            improved = False
            for i in range(0, n - 1):
                for j in range(i + 1, n):
                    # reverse o[i:j+1]
                    a_ = D[o[i - 1], o[i]] if i > 0 else 0
                    b_ = D[o[j], o[j + 1]] if j < n - 1 else 0
                    a2 = D[o[i - 1], o[j]] if i > 0 else 0
                    b2 = D[o[i], o[j + 1]] if j < n - 1 else 0
                    if a2 + b2 < a_ + b_ - 1e-9:
                        o[i:j + 1] = o[i:j + 1][::-1]; improved = True
        L = sum(D[o[i], o[i + 1]] for i in range(n - 1))
        if best is None or L < best[0]: best = (L, o)
    return best[1], best[0]


ROAD = 1.35
day_stats = []
for dev in DEVS:
    for d in DATES:
        sel = df.index[(df['Desenvolvedor'] == dev) & (df['Data'] == d)].tolist()
        if not sel: continue
        o, L = tsp_open(X[sel]) if len(sel) > 2 else (list(range(len(sel))), np.linalg.norm(X[sel[0]] - X[sel[-1]]) if len(sel) > 1 else 0)
        for pos, j in enumerate(o):
            df.at[sel[j], 'Ordem'] = pos + 1
        day_stats.append({'dev': dev, 'date': d.isoformat(), 'n': len(sel), 'km': round(L * ROAD, 1)})

ds = pd.DataFrame(day_stats)
print(ds.groupby('dev').agg(dias=('n', 'size'), total=('n', 'sum'), mn=('n', 'min'), mx=('n', 'max'),
                            km=('km', 'sum'), kmmax=('km', 'max')))
print(df.groupby(['Desenvolvedor', 'Cidade']).size().unstack(fill_value=0))

# ---------- export ----------
df['DataStr'] = df['Data'].map(lambda d: d.isoformat())
df.to_pickle('result.pkl')
ds.to_pickle('daystats.pkl')
json.dump({'dates': [d.isoformat() for d in DATES]}, open('meta.json', 'w'))
