"""Voix off de la vidéo avec XTTS v2 (Coqui, modèle ouvert, licence CPML : usage non commercial).

    COQUI_TOS_AGREED=1 python docs/video/voix.py "<voix>" <dossier de sortie> [prises]

Environnement à part : pip install coqui-tts transformers (PyTorch et torchaudio 2.11). Licence acceptée par
Simon le 17 novembre 2026 pour ce projet d'école.

Contre les défauts de XTTS (syllabes avalées, bruit en fin de phrase) : chaque phrase de docs/video/voix.json
est synthétisée seule, en plusieurs prises ; Whisper retranscrit chaque prise et on garde celle dont la
transcription est la plus proche du texte. La fin de chaque prise est coupée après le dernier son de voix.
Sortie : un WAV par clip (<plan>_<n>.wav), phrases séparées par un court silence ; rapport dans prises.json.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from transformers import pipeline
from TTS.api import TTS

SR, PAUSE = 24000, 0.22


def phrases(texte: str) -> list[str]:
    return [p.strip() for p in re.split(r"(?<=[.?!])\s+", texte) if p.strip()]


def mots(s: str) -> list[str]:
    """Mots normalisés ; les nombres écrits en chiffres par Whisper sont remis en lettres."""
    from num2words import num2words

    s = s.replace("%", " pour cent ")
    s = re.sub(r"\d+", lambda m: " " + num2words(int(m.group()), lang="fr") + " ", s)
    s = unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+", s)


def ecart(ref: str, hyp: str) -> float:
    """Taux d'erreur sur les mots (distance d'édition / nombre de mots du texte)."""
    r, h = mots(ref), mots(hyp)
    d = list(range(len(h) + 1))
    for i, a in enumerate(r, 1):
        prec, d[0] = d[0], i
        for j, b in enumerate(h, 1):
            prec, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prec + (a != b))
    return d[len(h)] / max(len(r), 1)


def rogner(x: np.ndarray) -> np.ndarray:
    """Coupe le silence et les bruits après la dernière syllabe : fin de la dernière zone d'énergie soutenue."""
    trame = int(0.02 * SR)
    e = np.array([np.sqrt(np.mean(x[i:i + trame] ** 2)) for i in range(0, len(x) - trame, trame)])
    if not len(e):
        return x
    seuil = max(e.max() * 0.06, 1e-4)
    actif = e > seuil
    fin = len(actif)
    # dernière zone active d'au moins 80 ms (un clic isolé ou un souffle n'est pas une syllabe)
    while fin > 0:
        j = fin - 1
        while j >= 0 and not actif[j]:
            j -= 1
        k = j
        while k >= 0 and actif[k]:
            k -= 1
        if j - k >= 4:
            fin = j + 1
            break
        fin = k + 1 if k >= 0 else 0
    debut = int(np.argmax(actif))
    y = x[max(debut * trame - int(0.03 * SR), 0): min(fin * trame + int(0.09 * SR), len(x))].copy()
    n = min(int(0.06 * SR), len(y))
    y[-n:] *= np.linspace(1, 0, n)
    return y


def main(voix: str, out: Path, prises: int = 3, plans: set[str] | None = None) -> None:
    out.mkdir(parents=True, exist_ok=True)
    segments = json.loads((Path(__file__).parent / "voix.json").read_text(encoding="utf-8"))["segments"]
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    asr = pipeline("automatic-speech-recognition", model="openai/whisper-small", device="cpu")
    rapport = []
    for seg in segments:
        if plans and seg["plan"] not in plans:
            continue
        for n, clip in enumerate(seg["clips"]):
            morceaux = []
            for p in phrases(clip["texte"]):
                essais = []
                for k in range(prises):
                    torch.manual_seed(1000 * len(rapport) + k)
                    x = np.asarray(tts.tts(text=p, speaker=voix, language="fr", temperature=0.6,
                                           repetition_penalty=6.0, top_p=0.85, enable_text_splitting=False),
                                   dtype=np.float32)
                    x = rogner(x)
                    lu = asr({"raw": x, "sampling_rate": SR},
                             generate_kwargs={"language": "french", "task": "transcribe"})["text"]
                    essais.append((ecart(p, lu), len(x), x, lu))
                essais.sort(key=lambda e: (round(e[0], 2), e[1]))
                err, _, x, lu = essais[0]
                rapport.append({"plan": seg["plan"], "phrase": p, "ecart": round(err, 3), "lu": lu.strip()})
                print(f"{seg['plan']:10s} écart {err:.2f}  {p[:60]}")
                morceaux += [x, np.zeros(int(PAUSE * SR), dtype=np.float32)]
            sf.write(out / f"{seg['plan']}_{n}.wav", np.concatenate(morceaux[:-1]), SR)
    ancien = json.loads((out / "prises.json").read_text(encoding="utf-8")) if (out / "prises.json").exists() else []
    garde = [r for r in ancien if not plans or r["plan"] not in plans]
    (out / "prises.json").write_text(json.dumps(garde + rapport, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    # python voix.py <voix> <sortie> [prises] [plan,plan...]  : ne refait que les plans donnés
    main(sys.argv[1], Path(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 3,
         set(sys.argv[4].split(",")) if len(sys.argv) > 4 else None)
