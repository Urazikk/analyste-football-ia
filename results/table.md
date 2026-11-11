| niveau | modèle | Cas | Recall@5 | MRR | Exactitude | Citation | Fidélité | Abstention | Ambigu | Succès tâches | Chiffres non soutenus | pass^3 | Injection obéie | Erreurs | Coût/req ($) | Tokens/req | Latence (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | openai/gpt-oss-120b | 50 | — | — | 0.65 [0.50 ; 0.80] | — | — | 0.50 [0.20 ; 0.80] | — | — | — | — | — | 0 | 0.00016 | 396.96 | 1.23 |
| 1 | openai/gpt-oss-120b | 50 | 0.89 [0.79 ; 0.97] | 0.75 [0.63 ; 0.86] | 0.85 [0.72 ; 0.95] | 0.88 [0.78 ; 0.97] | 0.89 [0.78 ; 0.97] | 0.90 [0.70 ; 1.00] | — | — | — | — | — | 0 | 0.00026 | 1134.00 | 8.04 |
| 2 | openai/gpt-oss-120b | 50 | 0.71 [0.57 ; 0.86] | 0.56 [0.42 ; 0.70] | 0.86 [0.75 ; 0.94] | 0.75 [0.61 ; 0.89] | 0.71 [0.57 ; 0.86] | — | — | — | — | — | — | 14 | 0.00082 | 4430.50 | 23.31 |

Entre crochets : intervalle de confiance à 95 % (bootstrap, 2000 tirages, graine fixée).
