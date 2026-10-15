#!/usr/bin/env python3
"""Villa Delvis: genera il modello 3D dalle due piantine (piano terra e primo piano).

Le piantine non hanno scala. Quella usata e' dedotta dalle porte (~0,9 m) e dal soggiorno:
  - primo piano   : 0,0135 m/px
  - piano terra   : 0,0199 m/px   (immagine ridotta: lo "sgombero" sotto il soggiorno e' largo uguale)
Le due piante sono allineate sullo spigolo SO del soggiorno e sul muro sud (verificato: la terrazza
del primo piano copre l'autorimessa del piano terra, 12,6 m contro 13,1 m).

Modello: metri, Y verso l'alto, X verso est (destra del disegno), Z verso sud (basso del disegno).
Origine = angolo nord-ovest della terrazza.   Esegue: python3 genera_villa.py  (scrive nella cartella superiore).
"""
import json, math, struct, os, base64, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

# ---------------------------------------------------------------- quote (m)
H_PT = 2.60               # muri piano terra (h 2,40-2,50 nelle piantine: locali accessori)
SOL = 0.30                # spessore solaio
Y1 = H_PT + SOL           # pavimento primo piano = 2,90
H_P1 = 2.70               # muri primo piano -> gronda 5,60
HG = Y1 + H_P1
PITCH = math.radians(22)
TERR = -0.30              # quota del terreno

class Fr:
    """pixel di una piantina -> metri (X, Z)"""
    def __init__(s, sc, ox, oy, mx, mz): s.s, s.ox, s.oy, s.mx, s.mz = sc, ox, oy, mx, mz
    def P(s, x, y): return (s.mx + (x - s.ox) * s.s, s.mz + (y - s.oy) * s.s)
# Misura reale: la sala (soggiorno) e' 9,0 x 5,5 m -> fattore K rispetto alla stima iniziale
K = 1.489
PL1 = Fr(0.0135*K, 190, 25, 0.0, 0.0)          # primo piano
PL2 = Fr(0.0199*K, 220, 762, 1.01*K, 11.5*K)   # piano terra

# ---------------------------------------------------------------- mesh
class Mesh:
    def __init__(self, name, mat):
        self.name, self.mat = name, mat
        self.v, self.n, self.i, self.f = [], [], [], []
    def tri(self, a, b, c):
        ux, uy, uz = b[0]-a[0], b[1]-a[1], b[2]-a[2]
        vx, vy, vz = c[0]-a[0], c[1]-a[1], c[2]-a[2]
        nx, ny, nz = uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx
        l = math.sqrt(nx*nx+ny*ny+nz*nz)
        if l < 1e-12: return
        nn = (nx/l, ny/l, nz/l)
        self.f.append((a, b, c))
        k = len(self.v)
        self.v += [a, b, c]; self.n += [nn]*3
        self.i += [k, k+1, k+2]
    def quad(self, a, b, c, d):
        self.tri(a, b, c); self.tri(a, c, d)
    def tri_up(self, a, b, c):
        ny = (b[2]-a[2])*(c[0]-a[0]) - (b[0]-a[0])*(c[2]-a[2])
        self.tri(a, b, c) if ny >= 0 else self.tri(a, c, b)
    def quad_up(self, a, b, c, d):
        self.tri_up(a, b, c); self.tri_up(a, c, d)
    def tri_out(self, a, b, c, ref):
        n = ((b[1]-a[1])*(c[2]-a[2])-(b[2]-a[2])*(c[1]-a[1]), (b[2]-a[2])*(c[0]-a[0])-(b[0]-a[0])*(c[2]-a[2]), (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))
        d = (ref[0]-a[0], ref[1]-a[1], ref[2]-a[2])
        self.tri(a, b, c) if n[0]*d[0]+n[1]*d[1]+n[2]*d[2] <= 0 else self.tri(a, c, b)

def sgn_area(pts):
    return sum(pts[i][0]*pts[(i+1) % len(pts)][1]-pts[(i+1) % len(pts)][0]*pts[i][1] for i in range(len(pts)))/2

def ear_tris(pts):
    """triangolazione per ear clipping di un poligono semplice (anche concavo) -> lista di terne di indici"""
    n = len(pts); idx = list(range(n))
    if sgn_area(pts) < 0: idx.reverse()
    cr = lambda o, a, b: (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    def inside(p, a, b, c):
        d1, d2, d3 = cr(a, b, p), cr(b, c, p), cr(c, a, p)
        return d1 >= -1e-9 and d2 >= -1e-9 and d3 >= -1e-9
    out = []; guard = 0
    while len(idx) > 3 and guard < 5000:
        guard += 1
        for k in range(len(idx)):
            i0, i1, i2 = idx[k-1], idx[k], idx[(k+1) % len(idx)]
            a, b, c = pts[i0], pts[i1], pts[i2]
            if cr(a, b, c) <= 1e-12: continue
            if any(inside(pts[j], a, b, c) for j in idx if j not in (i0, i1, i2)): continue
            out.append((i0, i1, i2)); idx.pop(k); break
        else:
            break
    if len(idx) == 3: out.append(tuple(idx))
    return out

def prism(m, pts, y0, y1):
    """estrude un poligono (X,Z in metri) tra y0 e y1, normali verso l'esterno"""
    tr = ear_tris(pts)
    cr = lambda a, b, c: (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    for (i, j, k) in tr:
        a, b, c = pts[i], pts[j], pts[k]
        up = [(p[0], y1, p[1]) for p in (a, b, c)]; dn = [(p[0], y0, p[1]) for p in (a, b, c)]
        m.tri_up(*up)
        # faccia inferiore con normale verso il basso
        n_ = cr(a, b, c)
        (m.tri(dn[0], dn[1], dn[2]) if n_ > 0 else m.tri(dn[0], dn[2], dn[1]))
    sg = sgn_area(pts)
    for k in range(len(pts)):
        a, b = pts[k], pts[(k+1) % len(pts)]
        lo0, lo1 = (a[0], y0, a[1]), (b[0], y0, b[1]); hi0, hi1 = (a[0], y1, a[1]), (b[0], y1, b[1])
        # per un poligono antiorario (in X,Z) la normale esterna e' a destra del verso di percorrenza
        (m.quad(lo1, lo0, hi0, hi1) if sg > 0 else m.quad(lo0, lo1, hi1, hi0))

def box_m(m, a, b, t, y0, y1, ext=0.0):
    """scatola lungo il segmento a->b (X,Z m), spessore t m, quote y0..y1"""
    dx, dz = b[0]-a[0], b[1]-a[1]
    L = math.hypot(dx, dz)
    if L < 1e-6: return
    ux, uz = dx/L, dz/L; nx, nz = -uz, ux; h = t/2
    A = (a[0]-ux*ext, a[1]-uz*ext); B = (b[0]+ux*ext, b[1]+uz*ext)
    prism(m, [(A[0]+nx*h, A[1]+nz*h), (B[0]+nx*h, B[1]+nz*h), (B[0]-nx*h, B[1]-nz*h), (A[0]-nx*h, A[1]-nz*h)], y0, y1)

def abox(m, x0, x1, z0, z1, y0, y1):
    prism(m, [(x0, z0), (x1, z0), (x1, z1), (x0, z1)], y0, y1)

def flat_poly(m, pts, y):
    for (i, j, k) in ear_tris(pts):
        m.tri_up(*[(pts[q][0], y, pts[q][1]) for q in (i, j, k)])

def panel(m, a, b, y0, h):
    """pannello verticale tra due punti (x,z) con quote y0..y0+h (ringhiere)"""
    m.quad((a[0], y0, a[1]), (b[0], y0, b[1]), (b[0], y0+h, b[1]), (a[0], y0+h, a[1]))

# ---------------------------------------------------------------- contenitori
groups = {}
def M(group, name, mat):
    m = Mesh(name, mat); groups.setdefault(group, []).append(m); return m

windows_info = []
RENDER = {'terra': {'ext': [], 'int': [], 'fin': [], 'face': [], 'win': [], 'door': [], 'iface': []},
          'primo': {'ext': [], 'int': [], 'fin': [], 'face': [], 'win': [], 'door': [], 'iface': []},
          'tetto': {'ln': [], 'raf': [], 'face': []}, 'esterno': {'ln': []},
          'giardino': {'rec': [], 'alb': [], 'pis': [], 'str': [], 'pols': {'lotto': [], 'strada': [], 'acqua': []}}}
CUT = 1.10   # quota di taglio dei muri interni (vista a fili)

def wall(group, fr, p1, p2, t, y0, h, ops=(), ex=False):
    """parete su segmento p1->p2 (pixel della piantina), spessore t px, aperture ops=[(a,b,sill,head,kind)]
    lungo l'asse dominante (px). ex=True: muro esterno (infissi, vetri, porte)."""
    s = fr.s; a, b = p1, p2
    dx, dy = b[0]-a[0], b[1]-a[1]
    horiz = abs(dx) >= abs(dy)
    tm = t*s; ext = tm/2; ep = t/2
    tag = 'terra' if group == 'piano_terra' else 'primo'
    wm = M(group, 'muri_'+group, 'muro'); gm = M(group, 'vetri_'+group, 'vetro')
    fm_ = M(group, 'infissi_'+group, 'telaio'); sm_ = M(group, 'davanzali_'+group, 'bordo')
    dm_ = M(group, 'porte_'+group, 'porta'); bm_ = M(group, 'basculanti_'+group, 'basculante')
    def at(c):
        k = (c-a[0])/dx if horiz else (c-a[1])/dy
        return (a[0]+dx*k, a[1]+dy*k)
    pm = lambda c: fr.P(*at(c))
    lo_c, hi_c = (a[0], b[0]) if horiz else (a[1], b[1])
    lo_e, hi_e = min(lo_c, hi_c), max(lo_c, hi_c)
    cl = sorted(c for c in [(max(min(o[0], o[1]), lo_e), min(max(o[0], o[1]), hi_e), o[2], o[3], o[4]) for o in ops] if c[1] > c[0])
    def seg(c0, c1, ya, yb, mesh, thick=None, e=0.0):
        if c1-c0 < 0.5 or yb-ya < 0.005: return
        box_m(mesh, pm(c0), pm(c1), tm if thick is None else thick, ya, yb, e)
    # ---- vista a fili
    R = RENDER[tag]
    def pt3(c, yy): X, Z = pm(c); return (X, yy, Z)
    def ln(arr, c0_, c1_, yy0, yy1=None):
        if c1_-c0_ < 0.5: return
        arr.append((pt3(c0_, yy0), pt3(c1_, yy0 if yy1 is None else yy1)))
    if ex:
        ln(R['ext'], lo_e-ep, hi_e+ep, y0+h)
        pos = lo_e-ep
        for (c0_, c1_, sl_, hd_, kd_) in cl:
            if kd_ == 'd': ln(R['ext'], pos, c0_, y0); pos = c1_
        ln(R['ext'], pos, hi_e+ep, y0)
        for cc in (lo_e-ep, hi_e+ep): R['ext'].append((pt3(cc, y0), pt3(cc, y0+h)))
        R['face'].append((pt3(lo_e-ep, y0), pt3(hi_e+ep, y0), pt3(hi_e+ep, y0+h), pt3(lo_e-ep, y0+h)))
        for (c0_, c1_, sl_, hd_, kd_) in cl:
            if kd_ == 'w':
                R['win'].append((pt3(c0_, y0+sl_), pt3(c1_, y0+sl_), pt3(c1_, y0+hd_), pt3(c0_, y0+hd_)))
                ln(R['fin'], c0_, c1_, y0+sl_); ln(R['fin'], c0_, c1_, y0+hd_)
                for cc in (c0_, c1_): R['fin'].append((pt3(cc, y0+sl_), pt3(cc, y0+hd_)))
            else:
                R['door'].append((pt3(c0_, y0), pt3(c1_, y0), pt3(c1_, y0+hd_), pt3(c0_, y0+hd_)))
                ln(R['fin'], c0_, c1_, y0+hd_)
                for cc in (c0_, c1_): R['fin'].append((pt3(cc, y0), pt3(cc, y0+hd_)))
    else:
        pos = lo_e-ep
        def iq(a_, b_):
            if b_-a_ > 0.5: R['iface'].append((pt3(a_, y0), pt3(b_, y0), pt3(b_, y0+CUT), pt3(a_, y0+CUT)))
        for (c0_, c1_, sl_, hd_, kd_) in cl:
            ln(R['int'], pos, c0_, y0+CUT); iq(pos, c0_); pos = c1_
        ln(R['int'], pos, hi_e+ep, y0+CUT); iq(pos, hi_e+ep)
    # ---- solidi
    cur = lo_e; end = hi_e
    for (c0, c1, sill, head, kind) in cl:
        c0 = max(c0, cur); c1 = min(c1, end)
        if c0 > cur: seg(cur, c0, y0, y0+h, wm, e=(ext if abs(cur-lo_e) < 1e-6 else 0.0))
        if sill > 0: seg(c0, c1, y0, y0+sill, wm)
        if head < h: seg(c0, c1, y0+head, y0+h, wm)
        wid = (c1-c0)*s
        if ex and kind == 'd' and wid > 2.0: seg(c0+0.05/s, c1-0.05/s, y0, y0+head-0.04, bm_, thick=0.09)
        elif ex and kind == 'd': seg(c0+0.04/s, c1-0.04/s, y0, y0+head-0.03, dm_, thick=0.07)
        if ex and kind == 'w':
            fw = 0.06/s
            seg(c0, c0+fw, y0+sill, y0+head, fm_, thick=0.09); seg(c1-fw, c1, y0+sill, y0+head, fm_, thick=0.09)
            seg(c0, c1, y0+head-0.06, y0+head, fm_, thick=0.09); seg(c0, c1, y0+sill, y0+sill+0.06, fm_, thick=0.09)
            if wid > 1.0: seg((c0+c1)/2-fw/2, (c0+c1)/2+fw/2, y0+sill, y0+head, fm_, thick=0.07)
            seg(c0-0.05/s, c1+0.05/s, y0+sill-0.05, y0+sill, sm_, thick=tm+0.14)      # davanzale
        if kind == 'w':
            seg(c0, c1, y0+sill, y0+head, gm, thick=0.04)
            X, Z = pm((c0+c1)/2)
            windows_info.append({'gruppo': group, 'x': round(X, 2), 'z': round(Z, 2), 'y': round(y0+(sill+head)/2, 2), 'larghezza_m': round(wid, 2)})
        cur = c1
    if end > cur: seg(cur, end, y0, y0+h, wm, e=ext)

def Wd(a, b, sill=0.90, head=2.10): return (a, b, sill, head, 'w')
def Dr(a, b, head=2.15): return (a, b, 0.0, head, 'd')

# ================================================================= PIANO TERRA (tavola IMG_8307, PL2)
g = 'piano_terra'; E2, I2 = 14, 10     # spessori px (0,28 m / 0,20 m)
wall(g, PL2, (180, 188), (808, 188), E2, 0, H_PT, ex=True)                       # nord
wall(g, PL2, (808, 188), (808, 530), E2, 0, H_PT, ex=True)                       # est
wall(g, PL2, (680, 530), (808, 530), E2, 0, H_PT, [Wd(720, 770, 1.0, 2.0)], ex=True)   # sgombero est, lato sud
wall(g, PL2, (555, 565), (645, 565), E2, 0, H_PT, ex=True)                       # lavanderia, lato sud
wall(g, PL2, (555, 565), (555, 762), E2, 0, H_PT, [Wd(620, 672, 1.0, 2.1)], ex=True)   # sgombero sud, est
wall(g, PL2, (225, 762), (555, 762), E2, 0, H_PT, ex=True)                       # sgombero sud, lato sud
wall(g, PL2, (225, 565), (225, 762), E2, 0, H_PT, [Wd(630, 685, 1.0, 2.1)], ex=True)   # sgombero sud, ovest
wall(g, PL2, (152, 525), (225, 565), E2, 0, H_PT, [Dr(160, 218, 2.30)], ex=True)  # porta garage (lato diagonale)
wall(g, PL2, (152, 365), (152, 525), E2, 0, H_PT, ex=True)                       # ovest
wall(g, PL2, (152, 363), (180, 363), E2, 0, H_PT, ex=True)
wall(g, PL2, (180, 188), (180, 363), E2, 0, H_PT, ex=True)
# interni
wall(g, PL2, (225, 565), (555, 565), 12, 0, H_PT, [Dr(330, 385)])               # autorimessa / sgombero
wall(g, PL2, (480, 328), (680, 328), I2, 0, H_PT)
wall(g, PL2, (672, 328), (672, 530), I2, 0, H_PT, [Dr(385, 425)])               # passaggio coperto / sgombero est
wall(g, PL2, (680, 355), (808, 355), I2, 0, H_PT)
wall(g, PL2, (525, 365), (640, 365), 12, 0, H_PT)                                # cantina
wall(g, PL2, (525, 365), (525, 462), 12, 0, H_PT, [Dr(400, 440)])
wall(g, PL2, (495, 464), (640, 464), 12, 0, H_PT)
wall(g, PL2, (495, 464), (495, 565), 12, 0, H_PT)                                # lavanderia
wall(g, PL2, (640, 365), (640, 565), 12, 0, H_PT, [Dr(520, 558)])

# ================================================================= PRIMO PIANO (tavola IMG_8306, PL1)
g = 'primo_piano'; Y = Y1; E1, I1 = 22, 14
wall(g, PL1, (181, 285), (181, 662), E1, Y, H_P1, [Wd(525, 572)], ex=True)        # ovest (cucina)
wall(g, PL1, (172, 294), (898, 294), E1, Y, H_P1, [Wd(275, 325), Wd(440, 475), Wd(573, 620), Wd(750, 805)], ex=True)   # nord
wall(g, PL1, (886, 294), (886, 625), E1, Y, H_P1, [Wd(537, 572)], ex=True)        # est (bagno)
wall(g, PL1, (757, 620), (897, 620), 20, Y, H_P1, ex=True)                        # bagno, lato sud
wall(g, PL1, (754, 620), (754, 872), E1, Y, H_P1, [Wd(672, 740)], ex=True)        # soggiorno, est
wall(g, PL1, (265, 862), (768, 862), E1, Y, H_P1, [Wd(445, 527)], ex=True)        # soggiorno, sud
wall(g, PL1, (278, 660), (278, 875), E1, Y, H_P1, [Dr(715, 782, 2.20)], ex=True)  # soggiorno, ovest (porta d'ingresso)
wall(g, PL1, (170, 660), (278, 660), 20, Y, H_P1, ex=True)                        # cucina, lato sud
# interni
wall(g, PL1, (400, 573), (755, 573), 18, Y, H_P1)                                 # soggiorno / disimpegno
wall(g, PL1, (345, 455), (345, 620), I1, Y, H_P1, [Dr(500, 565)])                 # cucina
wall(g, PL1, (190, 455), (350, 455), I1, Y, H_P1)
for xx in (390, 524, 683):
    wall(g, PL1, (xx, 298), (xx, 490), 12, Y, H_P1)                               # tramezzi camere / bagno
for (x0, x1) in ((385, 445), (483, 570), (603, 707), (745, 886)):
    wall(g, PL1, (x0, 490), (x1, 490), 10, Y, H_P1)
wall(g, PL1, (757, 490), (757, 622), I1, Y, H_P1, [Dr(500, 555)])                 # bagno est

# ================================================================= SOLAI, TERRAZZA, SCALA
def poly_m(fr, pts): return [fr.P(*p) for p in pts]
GROUND = poly_m(PL2, [(180, 190), (808, 185), (812, 530), (680, 530), (680, 565), (555, 565), (555, 762), (225, 762), (225, 565), (152, 525), (152, 365), (180, 360)])
SLAB1 = poly_m(PL1, [(175, 25), (1120, 25), (1155, 580), (1080, 580), (1080, 675), (865, 675), (865, 975), (175, 975)])
LAND = [(-1.15*K, 8.45*K), (-0.20*K, 8.45*K), (-0.20*K, 9.95*K), (-1.15*K, 9.95*K)]       # pianerottolo scala esterna

sl = M('solai_terra', 'solaio_terra', 'pavimento'); prism(sl, GROUND, TERR, 0.0)
sl = M('solai_terra', 'solaio_primo_sotto', 'muro'); prism(sl, GROUND, H_PT, Y1-0.02)
tz = M('terrazza', 'piano_primo', 'pavimento'); prism(tz, SLAB1, H_PT, Y1)
pi = M('terrazza', 'pianerottolo', 'pavimento'); prism(pi, LAND, H_PT, Y1)
RENDER['terra']['pols'] = [[[round(a, 2), round(b, 2)] for a, b in GROUND]]
RENDER['primo']['pols'] = [[[round(a, 2), round(b, 2)] for a, b in SLAB1], [[round(a, 2), round(b, 2)] for a, b in LAND]]

# fioriere / bordi rialzati della terrazza (zone tratteggiate della piantina): h 0,90 m
fio = M('terrazza', 'fioriere', 'siepe')
PLANT = [poly_m(PL1, q) for q in ([(190, 25), (1120, 25), (1050, 105), (260, 105)], [(190, 25), (260, 105), (260, 285), (190, 285)], [(1120, 25), (1155, 580), (1080, 580), (1050, 105)])]
for q in PLANT:
    prism(fio, q, Y1, Y1+0.90)
    for k in range(len(q)):
        a_, b_ = q[k], q[(k+1) % len(q)]
        RENDER['primo']['int'] += [((a_[0], Y1+0.9, a_[1]), (b_[0], Y1+0.9, b_[1]))]
    for a_ in q: RENDER['primo']['int'].append(((a_[0], Y1, a_[1]), (a_[0], Y1+0.9, a_[1])))

# ringhiere del balcone (h 1,00 m)
rg = M('terrazza', 'ringhiere', 'ringhiera')
def rail(pts, h=1.0, spacing=1.2):
    for a, b in zip(pts, pts[1:]):
        L = math.hypot(b[0]-a[0], b[1]-a[1]); n = max(1, round(L/spacing))
        box_m(rg, a, b, 0.04, Y1+h-0.05, Y1+h)
        box_m(rg, a, b, 0.03, Y1+0.35, Y1+0.38)
        RENDER['primo']['int'] += [((a[0], Y1+h, a[1]), (b[0], Y1+h, b[1]))]
        for i in range(n+1):
            t = i/n; p = (a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t)
            abox(rg, p[0]-0.025, p[0]+0.025, p[1]-0.025, p[1]+0.025, Y1, Y1+h)
            RENDER['primo']['int'].append(((p[0], Y1, p[1]), (p[0], Y1+h, p[1])))
rail([PL1.P(1080, 580), PL1.P(1080, 675), PL1.P(865, 675), PL1.P(865, 975), PL1.P(175, 975)])
rail([(-1.15*K, 9.95*K), (-1.15*K, 8.45*K), (-0.20*K, 8.45*K)])

# pilastri sotto il balcone e sotto la terrazza oltre l'autorimessa
pil = M('terrazza', 'pilastri', 'muro')
for (px_, py_) in [(865, 975), (865, 675), (1080, 675), (175, 975), (1155, 580)]:
    X, Z = PL1.P(px_, py_)
    abox(pil, X-0.30, X, Z-0.30, Z, TERR, H_PT)
for (X, Z) in [(-1.15*K, 8.45*K), (-0.20*K, 8.45*K)]:
    abox(pil, X-0.05 if X < -1 else X-0.15, X+0.15 if X > -1 else X+0.05, Z-0.05, Z+0.15, TERR, H_PT)

# scala esterna (16 alzate, dal cortile al pianerottolo): X -1.15..-0.25, sale verso nord
st = M('terrazza', 'scala_esterna', 'pietra')
NST = 16; RIS = (Y1-0.0)/NST; PED = 0.26; ZB = 9.95*K
for i in range(NST-1):
    zf = ZB + (NST-1-i)*PED                              # bordo anteriore (sud) del gradino i
    top = RIS*(i+1)
    abox(st, -1.15*K, -0.25*K, zf-PED, zf, TERR, top)
    RENDER['esterno']['ln'] += [((-1.15*K, top, zf-PED), (-0.25*K, top, zf-PED)), ((-1.15*K, top, zf), (-0.25*K, top, zf)),
                                ((-1.15*K, top, zf-PED), (-1.15*K, top, zf)), ((-0.25*K, top, zf-PED), (-0.25*K, top, zf))]
STAIR_END_Z = ZB + (NST-1)*PED
sr = M('terrazza', 'ringhiera_scala', 'ringhiera')
for X in (-1.15*K, -0.25*K):
    sr.quad((X, 0.0+0.9, STAIR_END_Z), (X, Y1+0.9, ZB), (X, Y1+1.0, ZB), (X, 1.0, STAIR_END_Z))
    RENDER['esterno']['ln'] += [((X, 0.9, STAIR_END_Z), (X, Y1+0.9, ZB))]

# ================================================================= STANZE
def centroid(pts):
    a = 0; cx = cz = 0
    for i in range(len(pts)):
        x0, z0 = pts[i]; x1, z1 = pts[(i+1) % len(pts)]
        c = x0*z1-x1*z0; a += c; cx += (x0+x1)*c; cz += (z0+z1)*c
    a /= 2
    return (cx/(6*a), cz/(6*a)) if abs(a) > 1e-9 else pts[0]
def rect(x0, y0, x1, y1): return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
ROOMS = {}
def room(name, floor, fr, pts, y):
    ROOMS[name] = (floor, y, poly_m(fr, pts))
# piano terra
room('autorimesse', 'terra', PL2, [(186, 196), (803, 193), (803, 350), (676, 350), (676, 326), (500, 326), (500, 560), (230, 560), (160, 522), (160, 370), (186, 366)], 0)
room('cantina', 'terra', PL2, rect(530, 370, 636, 458), 0)
room('lavanderia', 'terra', PL2, rect(500, 470, 636, 560), 0)
room('passaggio_coperto', 'terra', PL2, rect(646, 334, 668, 560), 0)
room('sgombero_est', 'terra', PL2, rect(684, 360, 804, 526), 0)
room('sgombero', 'terra', PL2, rect(230, 570, 550, 756), 0)
# primo piano
room('camera_ovest', 'primo', PL1, rect(197, 305, 383, 452), Y1)
room('bagno_nord', 'primo', PL1, rect(399, 305, 516, 484), Y1)
room('camera_centro', 'primo', PL1, rect(532, 305, 675, 484), Y1)
room('camera_est', 'primo', PL1, rect(692, 305, 872, 484), Y1)
room('cucina', 'primo', PL1, rect(197, 463, 340, 651), Y1)
room('disimpegno', 'primo', PL1, rect(352, 498, 750, 566), Y1)
room('bagno_est', 'primo', PL1, rect(772, 500, 876, 614), Y1)
room('soggiorno', 'primo', PL1, rect(296, 584, 748, 856), Y1)
room('balcone', 'primo', PL1, [(180, 884), (768, 884), (768, 680), (862, 680), (862, 970), (180, 970)], Y1)
room('terrazza', 'primo', PL1, [(262, 108), (1048, 108), (1078, 578), (1078, 672), (892, 672), (892, 286), (262, 286)], Y1)

def area(poly): return abs(sgn_area(poly))
room_info = {}
for name, (fl, y, pts) in ROOMS.items():
    mesh = M('stanze_'+fl, 'stanza_'+name, 'pav_terra' if fl == 'terra' else 'pav_primo')
    flat_poly(mesh, pts, y+0.012 if y else 0.012)
    cx_, cz_ = centroid(pts)
    room_info[name] = {'piano': fl, 'x': round(cx_, 2), 'z': round(cz_, 2), 'y_pavimento': y, 'area_m2': round(area(pts), 1)}

# ================================================================= TETTO
roof = M('tetto', 'falde_tetto', 'coppi'); gab = M('tetto', 'timpani', 'muro')
colmo = M('tetto', 'colmi', 'colmo'); gr = M('tetto', 'grondaie', 'rame')
OVH = 0.45
mx0, mx1 = PL1.P(172, 0)[0], PL1.P(898, 0)[0]
mz0, mz1 = PL1.P(0, 285)[1], PL1.P(0, 668)[1]
wx0, wx1 = PL1.P(265, 0)[0], PL1.P(768, 0)[0]
wz1 = PL1.P(0, 877)[1]
tm_ = math.tan(PITCH)
hm = (mz1-mz0)/2
HR = HG + hm*tm_                               # colmo
zmid = (mz0+mz1)/2
tw_ = (HR-HG)/((wx1-wx0)/2)                    # pendenza del corpo trasversale (stesso colmo)
xc = (wx0+wx1)/2
Hm_e = HG - OVH*tm_; Hw_e = HG - OVH*tw_
ref = (xc, HG, zmid)
# corpo principale (colmo E-O)
A = (mx0-OVH, Hm_e, mz0-OVH); B = (mx1+OVH, Hm_e, mz0-OVH); C = (mx1+OVH, HR+0, zmid); Dd = (mx0-OVH, HR+0, zmid)
# i punti del colmo sono a quota HR: la falda sale da Hm_e (a mz0-OVH) fino a HR (a zmid)
Rn0 = (mx0-OVH, HR, zmid); Rn1 = (mx1+OVH, HR, zmid)
roof.quad_up((mx0-OVH, Hm_e, mz0-OVH), (mx1+OVH, Hm_e, mz0-OVH), Rn1, Rn0)
roof.quad_up((mx0-OVH, Hm_e, mz1+OVH), (mx1+OVH, Hm_e, mz1+OVH), Rn1, Rn0)
gab.tri_out((mx0, HG, mz0), (mx0, HG, mz1), (mx0, HR, zmid), (mx0+1, HG, zmid))
gab.tri_out((mx1, HG, mz0), (mx1, HG, mz1), (mx1, HR, zmid), (mx1-1, HG, zmid))
# corpo trasversale (colmo N-S) sul soggiorno
z_end = wz1+OVH
W0 = (wx0-OVH, Hw_e, z_end); W1 = (wx0-OVH, Hw_e, zmid); W2 = (xc, HR, zmid); W3 = (xc, HR, z_end)
roof.quad_up(W0, W1, W2, W3)
V0 = (wx1+OVH, Hw_e, z_end); V1 = (wx1+OVH, Hw_e, zmid)
roof.quad_up(V0, V1, W2, W3)
gab.tri_out((wx0, HG, wz1), (wx1, HG, wz1), (xc, HR, wz1), (xc, HG, wz1-1))
# colmi e grondaie
box_m(colmo, (mx0-OVH, zmid), (mx1+OVH, zmid), 0.36, HR-0.05, HR+0.14)
box_m(colmo, (xc, zmid), (xc, z_end), 0.36, HR-0.05, HR+0.14)
for (p1_, p2_, hh) in [((mx0-OVH, mz0-OVH), (mx1+OVH, mz0-OVH), Hm_e), ((mx0-OVH, mz1+OVH), (wx0-OVH, mz1+OVH), Hm_e), ((wx1+OVH, mz1+OVH), (mx1+OVH, mz1+OVH), Hm_e),
                       ((wx0-OVH, zmid), (wx0-OVH, z_end), Hw_e), ((wx1+OVH, zmid), (wx1+OVH, z_end), Hw_e)]:
    box_m(gr, p1_, p2_, 0.11, hh-0.10, hh+0.02)
for (px_, pz_) in [(mx0-OVH+0.05, mz0-OVH+0.05), (mx1+OVH-0.05, mz0-OVH+0.05), (wx0-OVH+0.05, z_end-0.05), (wx1+OVH-0.05, z_end-0.05)]:
    abox(gr, px_-0.045, px_+0.045, pz_-0.045, pz_+0.045, Y1, Hm_e-0.1)
# vista a fili
RT = RENDER['tetto']
def rl(a, b): RT['ln'].append((a, b))
for (a_, b_) in [((mx0-OVH, Hm_e, mz0-OVH), (mx1+OVH, Hm_e, mz0-OVH)), ((mx0-OVH, Hm_e, mz1+OVH), (mx1+OVH, Hm_e, mz1+OVH)),
                 ((mx0-OVH, Hm_e, mz0-OVH), (mx0-OVH, Hm_e, mz1+OVH)), ((mx1+OVH, Hm_e, mz0-OVH), (mx1+OVH, Hm_e, mz1+OVH)),
                 (Rn0, Rn1), (W0, W3), (V0, W3), (W3, (xc, HR, zmid)), ((wx0-OVH, Hw_e, z_end), (wx1+OVH, Hw_e, z_end)),
                 ((mx0-OVH, Hm_e, mz0-OVH), Rn0), ((mx1+OVH, Hm_e, mz0-OVH), Rn1)]:
    rl(a_, b_)
RT['ln'] += [((mx0-OVH, Hm_e, mz1+OVH), (mx0-OVH, HR, zmid)), ((mx1+OVH, Hm_e, mz1+OVH), (mx1+OVH, HR, zmid))]
RT['face'] = [list(t) for m_ in (roof, gab) for t in m_.f]
# travetti (solo vista a fili)
zz = mz0-OVH+0.9
while zz < mz1+OVH-0.2:
    if abs(zz-zmid) > 0.2:
        fr_ = (zz-(mz0-OVH))/(zmid-(mz0-OVH)) if zz < zmid else ((mz1+OVH)-zz)/((mz1+OVH)-zmid)
        yy = Hm_e+(HR-Hm_e)*fr_
        # linea di falda dalla gronda ovest all'est a quota yy (corrente)
        RT['raf'].append(((mx0-OVH, yy, zz), (mx1+OVH, yy, zz)))
    zz += 0.9

# ================================================================= ESTERNO
ground = M('esterno', 'giardino', 'prato')
GX0, GX1, GZ0, GZ1 = -40, 55, -30, 60
ground.quad_up((GX0, TERR, GZ0), (GX1, TERR, GZ0), (GX1, TERR, GZ1), (GX0, TERR, GZ1))
CORT = [(-1.8*K, 12.0*K), (11.8*K, 12.0*K), (11.8*K, 17.5*K), (-1.8*K, 17.5*K)]
cort = M('esterno', 'cortile', 'pav_cortile'); flat_poly(cort, CORT, -0.02)
RENDER['esterno']['pol'] = [[round(a, 2), round(b, 2)] for a, b in CORT]
RENDER['esterno']['ln'] += [((CORT[i][0], -0.02, CORT[i][1]), (CORT[(i+1) % 4][0], -0.02, CORT[(i+1) % 4][1])) for i in range(4)]

# ================================================================= GLB
MATS = {
    'muro':       dict(c=(1, 1, 1, 1.0), a='OPAQUE', tex='intonaco', sc=3.0),
    'vetro':      dict(c=(0.16, 0.24, 0.30, 0.45), a='BLEND'),
    'pavimento':  dict(c=(0.80, 0.78, 0.74, 1.0), a='OPAQUE', tex='pietra', sc=1.5),
    'pav_terra':  dict(c=(0.62, 0.60, 0.56, 1.0), a='OPAQUE'),
    'pav_primo':  dict(c=(0.76, 0.66, 0.52, 1.0), a='OPAQUE'),
    'coppi':      dict(c=(1, 1, 1, 1.0), a='OPAQUE', tex='tegole', sc=1.6),
    'colmo':      dict(c=(0.62, 0.40, 0.32, 1.0), a='OPAQUE', tex='tegole', sc=1.6),
    'prato':      dict(c=(1, 1, 1, 1.0), a='OPAQUE', tex='prato', sc=4.0),
    'pav_cortile': dict(c=(1, 1, 1, 1.0), a='OPAQUE', tex='lastricato', sc=2.5),
    'bordo':      dict(c=(1, 1, 1, 1.0), a='OPAQUE', tex='pietra', sc=1.2),
    'pietra':     dict(c=(1, 1, 1, 1.0), a='OPAQUE', tex='pietra', sc=1.2),
    'ringhiera':  dict(c=(0.16, 0.18, 0.16, 1.0), a='OPAQUE'),
    'siepe':      dict(c=(1, 1, 1, 1.0), a='OPAQUE', tex='chioma', sc=1.5),
    'telaio':     dict(c=(0.95, 0.94, 0.90, 1.0), a='OPAQUE'),
    'porta':      dict(c=(0.30, 0.19, 0.10, 1.0), a='OPAQUE'),
    'basculante': dict(c=(0.56, 0.58, 0.58, 1.0), a='OPAQUE'),
    'rame':       dict(c=(0.74, 0.46, 0.30, 1.0), a='OPAQUE', met=0.15, rough=0.5),
}
mat_names = list(MATS)

def uv_of(p, n, sc):
    if abs(n[1]) > 0.98:
        t = (1.0, 0.0, 0.0); sv = (0.0, 0.0, 1.0)
    else:
        l = math.hypot(n[0], n[2]) or 1.0
        t = (n[2]/l, 0.0, -n[0]/l)
        sv = (n[1]*t[2]-n[2]*t[1], n[2]*t[0]-n[0]*t[2], n[0]*t[1]-n[1]*t[0])
    return ((p[0]*t[0]+p[1]*t[1]+p[2]*t[2])/sc, (p[0]*sv[0]+p[1]*sv[1]+p[2]*sv[2])/sc)

def build(path):
    import texture
    texs = texture.tutte()
    tex_names = sorted({v['tex'] for v in MATS.values() if 'tex' in v})
    bin_chunks = []; accessors = []; views = []; meshes = []; nodes = []; node_children = []; images = []
    def add_raw(data):
        off = sum(len(c) for c in bin_chunks); bin_chunks.append(data + b'\0'*((-len(data)) % 4)); return off
    for tn in tex_names:
        data = texs[tn]; off = add_raw(data)
        views.append({'buffer': 0, 'byteOffset': off, 'byteLength': len(data)})
        images.append({'bufferView': len(views)-1, 'mimeType': 'image/png', 'name': tn})
    def add_view(data, target):
        off = add_raw(data)
        views.append({'buffer': 0, 'byteOffset': off, 'byteLength': len(data), 'target': target}); return len(views)-1
    for gname, mlist in groups.items():
        gidx = []
        for m in mlist:
            if not m.i: continue
            pos = b''.join(struct.pack('<3f', *p) for p in m.v); nor = b''.join(struct.pack('<3f', *p) for p in m.n)
            idx = struct.pack(f'<{len(m.i)}I', *m.i)
            xs = [p[0] for p in m.v]; ys = [p[1] for p in m.v]; zs = [p[2] for p in m.v]
            va = add_view(pos, 34962); vn = add_view(nor, 34962); vi = add_view(idx, 34963)
            accessors.append({'bufferView': va, 'componentType': 5126, 'count': len(m.v), 'type': 'VEC3', 'min': [min(xs), min(ys), min(zs)], 'max': [max(xs), max(ys), max(zs)]})
            a0 = len(accessors)-1
            accessors.append({'bufferView': vn, 'componentType': 5126, 'count': len(m.n), 'type': 'VEC3'})
            accessors.append({'bufferView': vi, 'componentType': 5125, 'count': len(m.i), 'type': 'SCALAR'})
            attrs = {'POSITION': a0, 'NORMAL': a0+1}
            if 'tex' in MATS[m.mat]:
                uvs = [uv_of(p_, n_, MATS[m.mat]['sc']) for p_, n_ in zip(m.v, m.n)]
                vt = add_view(b''.join(struct.pack('<2f', *q) for q in uvs), 34962)
                accessors.append({'bufferView': vt, 'componentType': 5126, 'count': len(uvs), 'type': 'VEC2'})
                attrs['TEXCOORD_0'] = len(accessors)-1
            meshes.append({'name': m.name, 'primitives': [{'attributes': attrs, 'indices': a0+2, 'material': mat_names.index(m.mat)}]})
            nodes.append({'name': m.name, 'mesh': len(meshes)-1}); gidx.append(len(nodes)-1)
        nodes.append({'name': gname, 'children': gidx}); node_children.append(len(nodes)-1)
    nodes.append({'name': 'villa_delvis', 'children': node_children}); root = len(nodes)-1
    gltf = {
        'asset': {'version': '2.0', 'generator': 'genera_villa.py'},
        'scene': 0, 'scenes': [{'nodes': [root]}], 'nodes': nodes, 'meshes': meshes, 'accessors': accessors, 'bufferViews': views,
        'materials': [dict({'name': n, 'doubleSided': True,
                            'pbrMetallicRoughness': dict({'baseColorFactor': list(MATS[n]['c']), 'metallicFactor': MATS[n].get('met', 0.0),
                                                          'roughnessFactor': MATS[n].get('rough', 0.35 if n == 'vetro' else 0.92)},
                                                         **({'baseColorTexture': {'index': tex_names.index(MATS[n]['tex'])}} if 'tex' in MATS[n] else {})),
                            'alphaMode': MATS[n]['a']}) for n in mat_names],
        'images': images, 'samplers': [{'magFilter': 9729, 'minFilter': 9987, 'wrapS': 10497, 'wrapT': 10497}],
        'textures': [{'source': i, 'sampler': 0} for i in range(len(images))],
        'buffers': [{'byteLength': sum(len(c) for c in bin_chunks)}],
    }
    js = json.dumps(gltf, separators=(',', ':')).encode(); js += b' '*((-len(js)) % 4)
    bn = b''.join(bin_chunks)
    out = struct.pack('<III', 0x46546C67, 2, 12+8+len(js)+8+len(bn))
    out += struct.pack('<II', len(js), 0x4E4F534A) + js + struct.pack('<II', len(bn), 0x004E4942) + bn
    open(path, 'wb').write(out)

def pack(lst):
    seen = {}
    for a_, b_ in lst:
        ia = tuple(round(c*100) for c in a_); ib = tuple(round(c*100) for c in b_)
        if ia != ib: seen[tuple(sorted((ia, ib)))] = 1
    return [list(x)+list(y) for (x, y) in seen]

if __name__ == '__main__':
    glb = os.path.join(OUT, 'villa_delvis.glb')
    build(glb)
    xs = [p[0] for ms in groups.values() for m in ms for p in m.v]; ys = [p[1] for ms in groups.values() for m in ms for p in m.v]
    zs = [p[2] for ms in groups.values() for m in ms for p in m.v]
    nomi = json.load(open(os.path.join(OUT, 'nomi_stanze.json'), encoding='utf-8'))
    info = {
        'unita': 'metri', 'assi': "X verso est (destra del disegno), Y verso l'alto, Z verso sud (basso del disegno)",
        'origine': 'angolo nord-ovest della terrazza',
        'scala_piantine_m_per_px': {'primo_piano': PL1.s, 'piano_terra': PL2.s},
        'ingombro_m': {'x': [round(min(xs), 2), round(max(xs), 2)], 'y': [round(min(ys), 2), round(max(ys), 2)], 'z': [round(min(zs), 2), round(max(zs), 2)]},
        'quote_m': {'pavimento_terra': 0, 'pavimento_primo': Y1, 'gronda': round(HG, 2), 'colmo': round(HR, 2)},
        'stanze': room_info, 'finestre': windows_info,
    }
    json.dump(info, open(os.path.join(OUT, 'villa_delvis.json'), 'w'), indent=1, ensure_ascii=False)
    out = {}
    for fl, dd in RENDER.items():
        out[fl] = {}
        for k, v in dd.items():
            if fl == 'giardino': out[fl][k] = v if k == 'pols' else []; continue
            if k in ('pol', 'pols'): out[fl][k] = v
            elif k in ('face', 'win', 'door', 'iface'): out[fl][k] = [[round(c*100) for p_ in q for c in p_] for q in v]
            else: out[fl][k] = pack(v)
    stanze = {n: {'area': v['area_m2'], 'x': v['x'], 'z': v['z'], 'y': v['y_pavimento'], 'piano': v['piano'],
                  'poly': [[round(a, 2), round(b, 2)] for a, b in ROOMS[n][2]]} for n, v in room_info.items()}
    cx0 = (min(xs)+max(xs))/2
    cfg = {'centro': [round(5.8*K, 2), 1.4, round(8.6*K, 2)], 'gap': 3.2, 'y1': Y1, 'gronda': round(HG, 2), 'etichetta': [-3.2*K, 12.0*K],
           'griglia': [-30, 48, -20, 50], 'fit': 0.78, 'zone': []}
    posizioni = json.load(open(os.path.join(OUT, 'posizioni.json'), encoding='utf-8'))
    data = json.dumps({'layers': out, 'stanze': stanze, 'cfg': cfg, 'nomi': nomi, 'marks': posizioni}, separators=(',', ':'))
    tpl = open(os.path.join(HERE, 'vista_template.html'), encoding='utf-8').read()
    open(os.path.join(OUT, 'vista_a_fili.html'), 'w', encoding='utf-8').write(tpl.replace('/*DATI*/null', data))
    # ---- modello pieno: three.js + glb incorporati in un unico file (si apre con doppio clic, senza server)
    t3 = open(os.path.join(OUT, 'vendor', 'three.min.js'), encoding='utf-8').read()
    tpl3 = open(os.path.join(HERE, 'modello_template.html'), encoding='utf-8').read()
    meta = json.dumps({'stanze': stanze, 'nomi': nomi, 'cfg': cfg}, separators=(',', ':'), ensure_ascii=False)
    html = (tpl3.replace('/*THREE*/', t3.replace('</script', '<\\/script')).replace('/*GLB*/""', '"' + base64.b64encode(open(glb, 'rb').read()).decode() + '"')
            .replace('/*META*/null', meta))
    open(os.path.join(OUT, 'modello_pieno.html'), 'w', encoding='utf-8').write(html)
    print({k: {kk: (len(vv) if not isinstance(vv, dict) else '-') for kk, vv in v.items()} for k, v in out.items()})
    print('ok', os.path.getsize(glb), 'bytes; ingombro', info['ingombro_m'], 'colmo', round(HR, 2))
