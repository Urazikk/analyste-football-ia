| niveau | modèle | Cas | Recall@5 | MRR | Exactitude | Citation | Fidélité | Abstention | Ambigu | Succès tâches | Chiffres non soutenus | pass^3 | Erreurs | Coût/req ($) | Tokens/req | Latence (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | openai/gpt-oss-120b | 25 | — | — | 0.75 [0.55 ; 0.90] | — | — | 0.40 [0.00 ; 0.80] | — | — | — | — | 0 | 0.00014 | 373.92 | 0.79 |
| 1 | openai/gpt-oss-120b | 25 | 1.00 [1.00 ; 1.00] | 0.89 [0.78 ; 0.97] | 0.95 [0.85 ; 1.00] | 1.00 [1.00 ; 1.00] | 1.00 [1.00 ; 1.00] | 0.80 [0.40 ; 1.00] | — | — | — | — | 0 | 0.00026 | 1139.16 | 6.06 |
| 2 | openai/gpt-oss-120b | 13 | 0.62 [0.38 ; 0.85] | 0.39 [0.18 ; 0.59] | 0.85 [0.62 ; 1.00] | 0.77 [0.54 ; 1.00] | 0.77 [0.54 ; 1.00] | — | — | — | — | — | 2 | 0.00072 | 3708.62 | 19.13 |

Entre crochets : intervalle de confiance à 95 % (bootstrap, 2000 tirages, graine fixée).
