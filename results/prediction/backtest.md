# Pronostic évalué sur le passé : matchs internationaux depuis le 2025-01-01


Chaque match est prédit avec les seules données d'avant. Brier : 0 = parfait, 0,667 = uniforme. Une différence négative dans la dernière colonne signifie que la méthode fait mieux que la simulation.


**Tous les matchs** (1803 matchs)

| Méthode | Brier [IC 95 %] | Log-loss | Bons pronostics | Brier − simulation [IC 95 %] |
|---|---|---|---|---|
| Uniforme | 0.667 [0.667 ; 0.667] | 1.099 | 48.2% | +0.170 [+0.151 ; +0.189] |
| Fréquences historiques | 0.629 [0.619 ; 0.639] | 1.044 | 48.2% | +0.132 [+0.117 ; +0.147] |
| Elo seul | 0.506 [0.487 ; 0.525] | 0.872 | 61.6% | +0.009 [+0.005 ; +0.013] |
| Elo + Poisson (calcul) | 0.497 [0.478 ; 0.516] | 0.847 | 61.6% | -0.000 [-0.000 ; +0.000] |
| Elo + Poisson (simulation) | 0.497 [0.478 ; 0.516] | 0.847 | 61.8% | — |

**Matchs officiels (hors amicaux)** (1315 matchs)

| Méthode | Brier [IC 95 %] | Log-loss | Bons pronostics | Brier − simulation [IC 95 %] |
|---|---|---|---|---|
| Uniforme | 0.667 [0.667 ; 0.667] | 1.099 | 47.3% | +0.179 [+0.157 ; +0.201] |
| Fréquences historiques | 0.631 [0.619 ; 0.643] | 1.046 | 47.3% | +0.144 [+0.125 ; +0.161] |
| Elo seul | 0.497 [0.474 ; 0.519] | 0.859 | 62.7% | +0.009 [+0.005 ; +0.014] |
| Elo + Poisson (calcul) | 0.487 [0.465 ; 0.510] | 0.834 | 62.7% | +0.000 [-0.000 ; +0.000] |
| Elo + Poisson (simulation) | 0.487 [0.465 ; 0.510] | 0.833 | 63.0% | — |

**Coupe du monde 2026** (104 matchs)

| Méthode | Brier [IC 95 %] | Log-loss | Bons pronostics | Brier − simulation [IC 95 %] |
|---|---|---|---|---|
| Uniforme | 0.667 [0.667 ; 0.667] | 1.099 | 47.1% | +0.164 [+0.092 ; +0.239] |
| Fréquences historiques | 0.638 [0.606 ; 0.668] | 1.057 | 47.1% | +0.135 [+0.078 ; +0.192] |
| Elo seul | 0.490 [0.417 ; 0.561] | 0.827 | 64.4% | -0.013 [-0.032 ; +0.003] |
| Elo + Poisson (calcul) | 0.503 [0.427 ; 0.575] | 0.861 | 64.4% | -0.000 [-0.002 ; +0.001] |
| Elo + Poisson (simulation) | 0.503 [0.428 ; 0.575] | 0.862 | 64.4% | — |

**Calibration de la simulation** (voir calibration.png)

| Probabilité annoncée | Cas | Fréquence observée |
|---|---|---|
| 0-10 % | 740 | 3.5% |
| 10-20 % | 873 | 15.7% |
| 20-30 % | 1691 | 25.4% |
| 30-40 % | 476 | 35.1% |
| 40-50 % | 451 | 45.2% |
| 50-60 % | 332 | 55.7% |
| 60-70 % | 268 | 65.3% |
| 70-80 % | 246 | 73.2% |
| 80-90 % | 190 | 88.4% |
| 90-100 % | 142 | 93.0% |
