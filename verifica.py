#!/usr/bin/env python3
"""Controlli di coerenza (sola lettura). Uscita 0 = tutto ok."""
import json, os, struct
D = os.path.dirname(os.path.abspath(__file__)); ERR = []
def ok(c, m):
    print(('  ok  ' if c else '  KO  ') + m)
    if not c: ERR.append(m)
g = open(os.path.join(D, 'villa_delvis.glb'), 'rb').read()
ok(g[:4] == b'glTF' and struct.unpack('<I', g[8:12])[0] == len(g), 'villa_delvis.glb valido')
ci = json.load(open(os.path.join(D, 'villa_delvis.json'), encoding='utf-8'))
nomi = json.load(open(os.path.join(D, 'nomi_stanze.json'), encoding='utf-8'))
ok(not [n for n in ci['stanze'] if n not in nomi], f"tutte le {len(ci['stanze'])} stanze hanno un nome")
ok(not [n for n in nomi if n not in ci['stanze']], 'nessun nome orfano')
for f, k in (('vista_a_fili.html', '"layers"'), ('modello_pieno.html', 'THREE')):
    t = open(os.path.join(D, f), encoding='utf-8').read()
    ok('/*DATI*/null' not in t and '/*GLB*/' not in t and '/*META*/' not in t and k in t, f'{f}: dati incorporati')
ok(os.path.getsize(os.path.join(D, 'modello_pieno.html')) > 500000, 'modello_pieno.html include three.js e il modello')
print('RISULTATO:', 'OK' if not ERR else f'{len(ERR)} PROBLEMI')
raise SystemExit(1 if ERR else 0)
