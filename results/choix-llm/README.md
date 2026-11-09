# Choix du LLM : 25 cas (20 doc, 5 absents), niveaux 0 et 1, Groq, 9 novembre 2026

Commande : `python eval.py --levels 0 1 --types doc absent --model <modèle>`.
Citation de gpt-oss recalculée après correction de la lecture des citations 【id】 (sans nouvel appel).

| Modèle | Niveau | Exactitude | Citation | Abstention | Tokens/req | Latence (s) |
|---|---|---|---|---|---|---|
| qwen/qwen3.8-27b | 0 | 0,10 | — | 0,60 | 156 | 0,70 |
| qwen/qwen3.8-27b | 1 | 0,95 | 0,90 | 1,00 | 992 | 8,87 |
| openai/gpt-oss-120b | 0 | 0,75 | — | 0,40 | 374 | 0,79 |
| openai/gpt-oss-120b | 1 | 0,95 | 1,00 | 0,80 | 1143 | 8,39 |

Latence du niveau 1 gonflée par les attentes sur la limite de 8000 tokens par minute de l'offre gratuite.
