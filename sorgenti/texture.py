#!/usr/bin/env python3
"""Texture procedurali 256x256 (PNG, ripetibili) per il modello pieno. Solo numpy + zlib.

I colori di base vengono dalla foto satellitare (Bing, 14/10/2026): tetti, acqua, prato, ghiaia, cortile.
Facciata: giallo ocra. Earth 3D dall'alto (241,220,170 al sole) e Street View sul muro di cinta (194,146,61 all'ombra) -> mediato (222,190,118).
"""
import struct, zlib
import numpy as np

N = 256

def png(arr):
    h, w, _ = arr.shape
    raw = b''.join(b'\x00' + arr[i].tobytes() for i in range(h))
    def chunk(t, d):
        c = struct.pack('>I', len(d)) + t + d
        return c + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))

def pnoise(cells, rng):
    g = rng.random((cells, cells))
    x = np.arange(N) / N * cells
    i0 = np.floor(x).astype(int) % cells; i1 = (i0 + 1) % cells
    f = x - np.floor(x); f = (1 - np.cos(f * np.pi)) / 2
    a = g[np.ix_(i0, i0)]; b = g[np.ix_(i0, i1)]; c = g[np.ix_(i1, i0)]; d = g[np.ix_(i1, i1)]
    fx = f[None, :]; fy = f[:, None]
    return a*(1-fx)*(1-fy) + b*fx*(1-fy) + c*(1-fx)*fy + d*fx*fy

def fbm(rng, octaves=((4, .5), (8, .3), (16, .2), (32, .1))):
    s = sum(w * pnoise(c, rng) for c, w in octaves)
    s = s / sum(w for _, w in octaves)
    return (s - s.mean()) / (s.std() + 1e-9)          # media 0, dev.std 1

def to8(rgb):
    return np.clip(rgb, 0, 255).astype(np.uint8)

def solid(base, var, rng, fine=0.0):
    n = fbm(rng)[..., None]
    out = np.array(base, float)[None, None, :] * (1 + var * n)
    if fine:
        out = out * (1 + fine * rng.standard_normal((N, N, 1)))
    return to8(out)

def tegole(rng, base=(186, 134, 108)):
    x = np.arange(N)[None, :]; y = np.arange(N)[:, None]
    cx = (x % 32) / 32.0                                   # 8 coppi per tessera
    conv = 0.70 + 0.30 * np.sin(np.pi * cx)                # coppo convesso: bordi in ombra
    ry = (y % 64) / 64.0                                   # 4 file per tessera, sovrapposte
    course = 0.78 + 0.22 * (ry ** 0.6)
    tid = ((x // 32) * 7 + (y // 64) * 13) % 31
    jit = (np.array([rng.random() for _ in range(31)])[tid] - 0.5) * 0.34 + 1.0
    mottle = 1 + 0.10 * fbm(rng)
    patina = (np.array([rng.random() for _ in range(31)])[(tid * 5 + 3) % 31] > 0.82) * 0.12   # qualche coppo piu' scuro/invecchiato
    shade = (conv * course * jit * mottle * (1 - patina))[..., None]
    col = np.array(base, float)[None, None, :] * shade
    col[..., 1] *= 1 + 0.04 * fbm(rng)
    return to8(col)

def lastricato(rng, base=(196, 190, 178)):
    out = np.zeros((N, N, 3)); n = fbm(rng)
    bh, bw = 32, 64
    y = np.arange(N)[:, None]; x = np.arange(N)[None, :]
    row = y // bh; xs = (x + (row % 2) * (bw // 2)) % bw
    joint = ((y % bh) < 2) | (xs < 2)
    tid = ((row * 5 + (x + (row % 2) * (bw // 2)) // bw * 11) % 17)
    jit = (np.array([rng.random() for _ in range(17)])[tid] - 0.5) * 0.20 + 1
    for c in range(3):
        out[..., c] = base[c] * jit * (1 + 0.06 * n)
    out[joint] = out[joint] * 0.55
    return to8(out)

def prato(rng):
    n = fbm(rng); fine = rng.standard_normal((N, N))
    base = np.array((124, 160, 92), float)
    out = base[None, None, :] * (1 + 0.16 * n[..., None] + 0.07 * fine[..., None])
    out[..., 0] *= 1 + 0.05 * n; out[..., 2] *= 1 - 0.05 * n
    return to8(out)

def ghiaia(rng):
    out = np.zeros((N, N, 3)); fine = rng.standard_normal((N, N)); n = fbm(rng)
    base = np.array((200, 194, 176), float)
    sp = np.where(rng.random((N, N)) > 0.93, -45, 0)
    for c in range(3):
        out[..., c] = base[c] * (1 + 0.025 * n + 0.09 * fine) + sp
    return to8(out)

def asfalto(rng):
    fine = rng.standard_normal((N, N)); n = fbm(rng)
    base = np.array((104, 102, 98), float)
    out = base[None, None, :] * (1 + 0.07 * n[..., None] + 0.09 * fine[..., None])
    out[rng.random((N, N)) > 0.985] += 55
    return to8(out)

def intonaco(rng, base=(236, 229, 212)):
    n = fbm(rng); fine = rng.standard_normal((N, N))
    out = np.array(base, float)[None, None, :] * (1 + 0.012 * n[..., None] + 0.012 * fine[..., None])
    return to8(out)

def pietra(rng, base=(214, 210, 198)):
    n = fbm(rng); fine = rng.standard_normal((N, N))
    out = np.array(base, float)[None, None, :] * (1 + 0.05 * n[..., None] + 0.03 * fine[..., None])
    return to8(out)

def acqua(rng):
    n = fbm(rng, ((3, .6), (6, .4)))
    base = np.array((52, 134, 132), float)
    out = base[None, None, :] * (1 + 0.10 * n[..., None])
    out[..., 2] *= 1.03
    return to8(out)

def chioma(rng):
    n = fbm(rng); fine = rng.standard_normal((N, N))
    base = np.array((46, 92, 42), float)
    out = base[None, None, :] * (1 + 0.28 * n[..., None] + 0.12 * fine[..., None])
    out[..., 0] *= 1 + 0.07 * n
    return to8(out)

def persiana(rng, base=(72, 128, 84)):
    y = np.arange(N)[:, None]; x = np.arange(N)[None, :]
    slat = (y % 16) / 16.0
    sh = 0.62 + 0.38 * np.sin(np.pi * slat) ** 0.6          # stecche orientabili
    n = fbm(rng)
    out = np.array(base, float)[None, None, :] * (sh * (1 + 0.06 * n))[..., :, None] if False else np.array(base, float)[None, None, :] * (sh + 0 * x)[..., None] * (1 + 0.06 * n[..., None])
    out[(x + 0 * y) % 128 < 3] *= 0.6                          # montanti verticali
    return to8(out)

def corteccia(rng):
    x = np.arange(N)[None, :]; n = fbm(rng)
    stripes = 0.75 + 0.25 * np.sin(x / N * np.pi * 2 * 12 + 3 * n)
    out = np.array((86, 62, 44), float)[None, None, :] * (stripes * (1 + 0.12 * n))[..., None]
    return to8(out)

def tutte(seed=7):
    rng = np.random.default_rng(seed)
    return {
        'tegole': png(tegole(rng)),
        'intonaco': png(intonaco(rng)),
        'prato': png(prato(rng)),
        'ghiaia': png(ghiaia(rng)),
        'asfalto': png(asfalto(rng)),
        'lastricato': png(lastricato(rng)),
        'pietra': png(pietra(rng)),
        'acqua': png(acqua(rng)),
        'chioma': png(chioma(rng)),
        'corteccia': png(corteccia(rng)),
        'persiana': png(persiana(rng)),
    }

if __name__ == '__main__':
    t = tutte()
    print({k: len(v) for k, v in t.items()})
