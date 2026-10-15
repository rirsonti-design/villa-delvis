# Villa Delvis — modello 3D

Modello 3D ricavato dalle due piantine (piano terra e primo piano), con la stessa struttura del progetto «Casa 3D».
**Non è collegato a Home Assistant** e non ha dipendenze: funziona offline.

## Come aprirlo
Doppio clic su uno dei due file (si aprono nel browser, nessun server):
- `modello_pieno.html` — modello pieno con texture, ombre, esploso, sezione dei muri, nomi dei locali, doppio clic = coordinate.
- `vista_a_fili.html` — vista a fili verde con piani, tetti, finestre, locali (stesso stile di Casa 3D). Il pulsante «Modello pieno ›» passa all'altro.
- `villa_delvis.glb` — lo stesso modello in glTF (Blender, ecc.).

## Cartella
| File | Ruolo |
|---|---|
| `sorgenti/genera_villa.py` | Genera tutto dal codice (muri, aperture, solai, tetto, scala…). **Si modifica questo** |
| `sorgenti/vista_template.html`, `modello_template.html`, `texture.py` | Modelli dei visualizzatori e texture procedurali |
| `sorgenti/piantina_*.jpg` | Le piantine di partenza |
| `nomi_stanze.json` | Nomi mostrati sui locali (chiave = id) |
| `posizioni.json` | Telecamere/sensori (vuoto; stesso formato di Casa 3D) |
| `vendor/three.min.js` | three.js r160 (incorporato nei file html) |
| `verifica.py` | Controlli di coerenza |

Dopo ogni modifica: `python3 sorgenti/genera_villa.py` (serve Python 3 con numpy) e `python3 verifica.py`.

## Assi e quote
X est (destra del disegno), Z sud (basso del disegno), Y su; origine = angolo NO della terrazza.
Piano terra 0 m, primo piano 2,90 m, gronda 5,60 m, colmo ≈ 6,64 m.

## Ipotesi (le piantine non hanno scala né quote)
- Scala calibrata sulla misura reale della sala (soggiorno) 9,0 × 5,5 m: primo piano 0,0201 m/px, piano terra 0,0296 m/px; le due piante sono allineate sullo spigolo SO del soggiorno (la terrazza copre l'autorimessa). Le altre misure ne derivano (±0,3–0,5 m).
- Altezze: muri piano terra 2,60 m, primo piano 2,70 m, solaio 0,30 m; tetto a due falde con corpo trasversale sul soggiorno, pendenza 22°.
- Le zone tratteggiate attorno alla terrazza sono rese come fioriere/bordi alti 0,90 m; balcone e terrazza con ringhiera da 1 m.
- Scala esterna (16 alzate) dal cortile al pianerottolo davanti alla porta d'ingresso; posizione e pendenza dedotte.
- Porte interne come semplici varchi; finestre con dimensioni lette dalla piantina; nessun arredo, giardino e cortile solo indicativi.
