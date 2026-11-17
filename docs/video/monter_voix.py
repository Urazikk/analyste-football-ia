"""Montage de la vidéo avec voix off : python docs/video/monter_voix.py <prises interface> <animations> <voix> <sortie.mp4>

Chaque plan est calé sur sa voix (docs/video/voix.json) : les prises de l'interface sont accélérées jusqu'à
2 fois pour supprimer les attentes, puis prolongées sur la dernière image si la voix dure plus longtemps.
Musique synthétisée à 112 battements par minute, baissée automatiquement sous la voix. ffmpeg requis.
"""
from __future__ import annotations

import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
FPS, FADE, MARGE = 30, 0.25, 1.2
ORDRE = ["hook", "intro", "s0", "s1", "s2", "s3", "trace", "s4", "s5", "resultats", "fin"]
ANIMES = {"hook", "intro", "trace", "resultats", "fin"}


def duree(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def coupe(plan: str, ui: Path, marks: dict) -> tuple[float, float]:
    """Début et fin utiles d'une prise de l'interface (temps de la prise)."""
    m = marks[plan]
    if plan == "s5":  # dernier essai du niveau 2, puis le niveau 3
        return max(m["info"]["last"] - 0.4, m["start"] + 0.2), m["end"]
    return m["start"] + 0.2, m["end"]


def plan_video(src: Path, dst: Path, a: float, b: float, vitesse: float, total: float) -> None:
    d = (b - a) / vitesse
    vf = (f"setpts=(PTS-STARTPTS)/{vitesse:.4f},fps={FPS},scale=1920:1080,format=yuv420p,"
          f"tpad=stop_mode=clone:stop_duration={max(total - d, 0):.3f},"
          f"fade=t=in:st=0:d={FADE},fade=t=out:st={total - FADE:.3f}:d={FADE}")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(src), "-vf", vf,
                    "-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-an", str(dst)], check=True)


def musique(path: Path, d: float, sr: int = 44100, bpm: float = 112) -> None:
    """Pulsation (grosse caisse, charleston), basse et nappe : un fond de pub, sans droits d'auteur."""
    n = int(sr * d)
    out = np.zeros(n)
    note = lambda m: 440 * 2 ** ((m - 69) / 12)  # noqa: E731
    temps = 60 / bpm
    accords = [[50, 57, 62, 66], [47, 54, 59, 62], [43, 50, 55, 59], [45, 52, 57, 61]]
    rng = np.random.default_rng(42)
    t_all = np.arange(n) / sr
    for k in range(int(d / temps) + 1):  # un temps
        i0 = int(k * temps * sr)
        if i0 >= n:
            break
        ln = min(int(0.25 * sr), n - i0)
        t = np.arange(ln) / sr
        f = 50 + 70 * np.exp(-t * 30)  # grosse caisse
        out[i0:i0 + ln] += np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t * 9) * 0.55
        j0 = int((k + 0.5) * temps * sr)  # charleston sur le contretemps
        if j0 < n:
            lh = min(int(0.05 * sr), n - j0)
            out[j0:j0 + lh] += rng.standard_normal(lh) * np.exp(-np.arange(lh) / sr * 90) * 0.10
    mesure = 4 * temps
    for k in range(int(d / mesure) + 1):  # basse et nappe, un accord par mesure
        ch = accords[(k // 2) % 4]
        i0 = int(k * mesure * sr)
        m = min(int(mesure * sr), n - i0)
        if m <= 0:
            break
        t = np.arange(m) / sr
        env = np.minimum(1, t / 0.05) * np.minimum(1, (t[-1] - t) / 0.2)
        pad = sum(np.sin(2 * np.pi * note(x) * t) for x in ch) / len(ch) * env * 0.16
        bass = np.sign(np.sin(2 * np.pi * note(ch[0] - 24) * t)) * 0.10 * env
        bass *= (np.sin(2 * np.pi * t / temps * 2) > -0.2)  # basse hachée en croches
        out[i0:i0 + m] += pad + bass
    out *= np.minimum(1, t_all / 1.5) * np.minimum(1, (d - t_all) / 2.5)
    out = out / np.max(np.abs(out)) * 0.6
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((out * 32767).astype(np.int16).tobytes())


def monter(ui: Path, anim: Path, voix: Path, sortie: Path) -> None:
    marks = json.loads((ui / "marks.json").read_text(encoding="utf-8"))
    segs = {s["plan"]: s["clips"] for s in json.loads((HERE / "voix.json").read_text(encoding="utf-8"))["segments"]}
    tmp = sortie.parent / "_plans_voix"
    tmp.mkdir(parents=True, exist_ok=True)
    t0, liste, poses = 0.0, [], []  # poses : (fichier voix, seconde globale)
    for plan in ORDRE:
        if plan in ANIMES:
            src, (a, b) = anim / f"{plan}.webm", (0.25, duree(anim / f"{plan}.webm"))
        else:
            src, (a, b) = ui / f"{plan}.webm", coupe(plan, ui, marks)
        clips = [(voix / f"{plan}_{i}.wav", c) for i, c in enumerate(segs[plan])]
        dv = [duree(f) for f, _ in clips]
        if plan in ANIMES:
            vitesse = {"trace": 1.2}.get(plan, 1.0)  # la trace défile plus vite, la voix y est courte
        elif len(clips) == 1:  # accélérer l'interface jusqu'à la longueur de la voix
            vitesse = min(max((b - a) / (dv[0] + 0.3 + MARGE), 1.0), 2.0)
        else:
            vitesse = 1.25
        fin_prec, places = 0.0, []
        for (f, c), d in zip(clips, dv):
            voulu = c["offset"] if "offset" in c else (b - a - c["fin_moins"])
            debut = max(voulu / vitesse, fin_prec + 0.25)
            places.append((f, debut))
            fin_prec = debut + d
        total = max((b - a) / vitesse, fin_prec + MARGE)
        plan_video(src, tmp / f"{plan}.mp4", a, b, vitesse, total)
        poses += [(f, t0 + p) for f, p in places]
        liste.append(f"file '{(tmp / (plan + '.mp4')).resolve()}'")
        print(f"{plan:10s} {total:5.1f} s  (vitesse {vitesse:.2f})")
        t0 += total
    (tmp / "liste.txt").write_text("\n".join(liste) + "\n", encoding="utf-8")
    musique(tmp / "musique.wav", t0)
    # piste de voix : chaque phrase posée à sa seconde, voix nettoyée et compressée comme en studio
    entrees = sum((["-i", str(f)] for f, _ in poses), [])
    delais = "".join(f"[{i}:a]aresample=44100,adelay={int(p * 1000)}:all=1[v{i}];" for i, (_, p) in enumerate(poses))
    mix = "".join(f"[v{i}]" for i in range(len(poses))) + f"amix=inputs={len(poses)}:normalize=0,"
    filtre = (delais + mix + "highpass=f=80,equalizer=f=3200:t=q:w=1.2:g=3,"
              "acompressor=threshold=0.08:ratio=4:attack=5:release=120:makeup=2,"
              f"apad=whole_dur={t0:.3f}[voix]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *entrees, "-filter_complex", filtre, "-map", "[voix]",
                    "-t", f"{t0:.3f}", str(tmp / "voix.wav")], check=True)
    # musique baissée sous la voix (compression déclenchée par la voix), puis mélange et niveau final
    filtre = ("[1:a]volume=0.55[m];[2:a]asplit=2[vk][vm];"
              "[m][vk]sidechaincompress=threshold=0.015:ratio=10:attack=15:release=450[md];"
              "[md][vm]amix=inputs=2:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=9[a]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "liste.txt"),
                    "-i", str(tmp / "musique.wav"), "-i", str(tmp / "voix.wav"), "-filter_complex", filtre,
                    "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "slow", "-crf", "24",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-t", f"{t0:.3f}", str(sortie)], check=True)
    print(f"{sortie} : {int(t0 // 60)} min {t0 % 60:.0f} s")


if __name__ == "__main__":
    monter(*(Path(a) for a in sys.argv[1:5]))
