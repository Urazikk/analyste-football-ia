"""Monte la vidéo de démonstration : python docs/video/monter.py <prises interface> <séquences animées> <sortie.mp4>

Ordre : ouverture animée, scènes de l'interface (coupées d'après marks.json), trace, résultats, fermeture.
Chaque plan est converti en H.264 1920 x 1080 à 30 images/s avec un fondu, puis une musique synthétisée
(aucun droit d'auteur) est mêlée à faible volume. ffmpeg requis.
"""
from __future__ import annotations

import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

FPS, FADE = 30, 0.4


def duree(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def plan(src: Path, dst: Path, debut: float = 0.0, fin: float | None = None) -> float:
    """Extrait [debut, fin] de src, fondu d'entrée et de sortie ; renvoie la durée du plan."""
    fin = duree(src) if fin is None else fin
    d = fin - debut
    vf = (f"fps={FPS},scale=1920:1080,format=yuv420p,fade=t=in:st=0:d={FADE},fade=t=out:st={d - FADE:.3f}:d={FADE}")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{debut:.3f}", "-t", f"{d:.3f}", "-i", str(src), "-vf", vf,
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-an", str(dst)], check=True)
    return d


def musique(path: Path, d: float, sr: int = 44100) -> None:
    """Nappe d'accords lente et quelques notes égrenées, synthétisées."""
    n = int(sr * d)
    out = np.zeros(n)
    note = lambda m: 440 * 2 ** ((m - 69) / 12)  # noqa: E731
    accords = [[50, 57, 62, 66], [47, 54, 59, 62], [43, 50, 55, 59], [45, 52, 57, 61]]  # ré, si mineur, sol, la
    mesure = 4 * 60 / 84 * 2
    k, t0 = 0, 0.0
    while t0 < d:
        ch = accords[k % 4]
        m = int(min(mesure + 1.2, d - t0) * sr)
        if m <= 0:
            break
        t = np.arange(m) / sr
        env = np.minimum(1, t / 1.0) * np.minimum(1, (t[-1] - t) / 1.2)
        seg = sum(np.sin(2 * np.pi * note(x) * t) + 0.25 * np.sin(2 * np.pi * note(x) * 2.002 * t) for x in ch) / len(ch) * env * 0.32
        seg += np.sin(2 * np.pi * note(ch[0] - 12) * t) * env * 0.22
        pas = 60 / 84 / 2
        for j, x in enumerate((ch[1:] + [ch[1] + 12]) * 8):
            s0 = int(j * pas * sr)
            if s0 >= m or j * pas > mesure:
                break
            ln = min(int(0.7 * sr), m - s0)
            u = np.arange(ln) / sr
            seg[s0:s0 + ln] += np.sin(2 * np.pi * note(x + 12) * u) * np.exp(-u * 4.5) * 0.10
        i0 = int(t0 * sr)
        out[i0:i0 + m] += seg[:n - i0]
        t0 += mesure
        k += 1
    out *= np.minimum(1, np.arange(n) / (2 * sr)) * np.minimum(1, (n - np.arange(n)) / (3 * sr))
    out = out / np.max(np.abs(out)) * 0.5
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((out * 32767).astype(np.int16).tobytes())


def monter(ui: Path, motion: Path, sortie: Path) -> None:
    marks = json.loads((ui / "marks.json").read_text(encoding="utf-8"))
    tmp = sortie.parent / "_plans"
    tmp.mkdir(parents=True, exist_ok=True)
    ordre = [("intro", motion / "intro.webm", 0.3, None)]
    for s in ("s1", "s2", "s3"):
        ordre.append((s, ui / f"{s}.webm", marks[s]["start"] + 0.2, marks[s]["end"]))
    ordre.append(("trace", motion / "trace.webm", 0.3, None))
    ordre.append(("s4", ui / "s4.webm", marks["s4"]["start"] + 0.2, marks["s4"]["end"]))
    s5 = marks["s5"]  # on garde le dernier essai du niveau 2, puis le niveau 3
    ordre.append(("s5", ui / "s5.webm", max(s5["info"]["last"] - 0.4, s5["start"] + 0.2), s5["end"]))
    ordre += [("resultats", motion / "resultats.webm", 0.3, None), ("fin", motion / "fin.webm", 0.3, None)]
    total, liste = 0.0, []
    for nom, src, a, b in ordre:
        d = plan(src, tmp / f"{nom}.mp4", a, b)
        print(f"{nom:10s} {d:6.1f} s")
        total += d
        liste.append(f"file '{(tmp / (nom + '.mp4')).resolve()}'")
    (tmp / "liste.txt").write_text("\n".join(liste) + "\n", encoding="utf-8")
    musique(tmp / "fond.wav", total)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "liste.txt"),
                    "-i", str(tmp / "fond.wav"), "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-filter:a", "volume=0.55",
                    "-shortest", "-movflags", "+faststart", str(sortie)], check=True)
    print(f"{sortie} : {int(total // 60)} min {total % 60:.0f} s")


if __name__ == "__main__":
    monter(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
