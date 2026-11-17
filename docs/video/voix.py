"""Voix off de la vidéo avec XTTS v2 (Coqui, modèle ouvert, licence CPML : usage non commercial).

    python docs/video/voix.py "<voix>" <dossier de sortie>      (environnement à part : pip install coqui-tts)

Un fichier WAV par phrase de docs/video/voix.json (<plan>_<n>.wav). La licence du modèle doit avoir été
acceptée (variable COQUI_TOS_AGREED=1) ; elle l'a été par Simon le 17 novembre 2026 pour ce projet d'école.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from TTS.api import TTS

voix, out = sys.argv[1], Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
segments = json.loads((Path(__file__).parent / "voix.json").read_text(encoding="utf-8"))["segments"]
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
for seg in segments:
    for i, clip in enumerate(seg["clips"]):
        f = out / f"{seg['plan']}_{i}.wav"
        if not f.exists():
            tts.tts_to_file(text=clip["texte"], speaker=voix, language="fr", file_path=str(f),
                            temperature=0.75, repetition_penalty=5.0, speed=1.08)  # débit un peu plus vif
            print(f.name)
