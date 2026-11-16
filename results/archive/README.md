# Mesures archivées

Niveau 2 mesuré le 10 novembre avant l'ajout de l'outil `simulate_match` (PR #16) : la liste des outils fait partie du prompt de l'agent, ces lignes ne sont donc pas comparables aux mesures suivantes. Gardées pour trace, exclues des tableaux.

`level3-v1/` : niveau 3 mesuré le 16 novembre avec la première version du prompt de plan (commit 01fa325). Cas ambigus 1,00 sur 30 cas (0,59 au niveau 2), mais abstention 0,20 sur 10 cas (0,90 au niveau 2) : le plan refusait ou demandait une précision pour des questions de football absentes des documents, au lieu de chercher puis de s'abstenir. Gardé pour trace, exclu des tableaux.
