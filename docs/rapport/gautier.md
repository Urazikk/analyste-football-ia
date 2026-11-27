# Sections de Gautier : agent, benchmark, coût, échecs, limites

Version finale du 27 novembre (chiffres du benchmark complétés).

## Agent et outils (niveau 2)

La boucle de l'agent est écrite à la main (`src/agent.py`), sans framework. À chaque pas, le modèle reçoit les schémas JSON des 9 outils et choisit d'appeler un outil ou de répondre. La boucle s'arrête à 8 pas ou 20 000 tokens. Une erreur d'outil (équipe inconnue, argument hors schéma, outil inexistant) n'arrête pas l'exécution : elle est renvoyée au modèle, qui corrige au pas suivant.

Les 9 outils sont classés par effet : lecture (`search_rules`, le RAG du niveau 1 ; `list_matches`, `match_events`), calcul (`team_stats`, `team_form`, `head_to_head`, `simulate_match`, `plot_shots`) et action irréversible (`publish_report`).

`publish_report` est la seule action irréversible. Elle passe d'abord par des règles métier vérifiées par du code : les équipes existent dans les données, elles sont différentes, le rapport fait au moins 200 caractères, il cite au moins un chiffre et aucun rapport n'existe déjà pour cette affiche. Elle passe ensuite par la validation de l'utilisateur dans l'interface. La validation et le refus sont écrits dans la trace JSONL du run. À la publication, le code ajoute lui-même les sections chiffrées du rapport (forme, confrontations, cartes des tirs, pronostic) : le modèle n'écrit que l'analyse.

## Benchmark de modèles (niveau 2, 20 tâches, 3 essais)

| Modèle | Poids | Succès tâches | pass^3 | Chiffres non soutenus | Tokens par tâche | Latence moyenne |
|---|---|---|---|---|---|---|
| gpt-6-luna (OpenAI) | fermés | 1,00 | 1,00 | 0,00 | 7 945 | 8,1 s |
| gpt-oss-120b (Groq) | ouverts | 0,60 | 0,46 | 0,33 | 9 844 | 61,6 s |

Source : `results/bench-llm.md`. Pour gpt-oss-120b, 44 essais sur 60 ont abouti ; les 16 autres ont été bloqués par le quota gratuit de Groq et ne sont pas comptés. pass^3 porte sur les 13 tâches dont les 3 essais ont abouti. Ses 20 essais ratés ont trois causes : l'affiche inversée à la publication (11 essais, échec 1 ci-dessous), l'arrêt à la borne de 8 étapes sans publier (6) et une réponse finale sans publication (3). gpt-6-luna ne présente aucun de ces échecs. Le modèle local (Ollama) prévu n'a pas été mesuré : sans GPU, 60 essais de tâches dépassaient le temps disponible. Le tableau des niveaux utilise gpt-6-luna ; gpt-oss-120b, à poids ouverts comme le conseille le sujet, reste la référence ouverte.

## Coût

Tarifs relevés le 16 novembre 2026 (USD par million de tokens) : gpt-6-luna 0,10 en entrée et 0,50 en sortie ; gpt-oss-120b sur Groq 0,15 et 0,60 (tarif payant équivalent, l'offre utilisée étant gratuite). Pour 1 000 requêtes, gpt-6-luna coûte 0,03 $ au niveau 0, 0,09 $ au niveau 1, 0,50 $ au niveau 2 et 0,51 $ au niveau 3 ; gpt-oss-120b, plus bavard, 0,16 $, 0,22 $ et 1,04 $ (niveau 3 non mesuré). L'agent coûte environ 5,5 fois le RAG : ce surcoût se justifie pour les tâches, où il est le seul à publier un rapport juste (1,00 contre 0,25), beaucoup moins pour les questions de règles. Une tâche coûte environ 7 900 tokens, soit 0,001 $ ; le niveau 3 n'ajoute que 3 % de tokens au niveau 2.

## Analyse de cinq échecs

Détail, preuves et traces : `docs/echecs.md`.

1. **Affiche inversée** (gpt-oss-120b, 11 des 20 essais de tâches ratés) : l'agent recopie l'ordre domicile/extérieur du dernier match renvoyé par `list_matches` au lieu de celui demandé. Les règles métier ne vérifient pas l'ordre.
2. **Publication sur une affiche choisie par l'agent** (gpt-6-luna, amb-08) : « le rapport de la Coupe du monde 2026 » devient un rapport États-Unis - Mexique publié. Toutes les règles passent, et seule la validation humaine protège. 4 publications non demandées sur 90 essais ambigus au niveau 2, 0 au niveau 3.
3. **Supposition au lieu d'une question** (gpt-6-luna) : « Qui a gagné le match ? » reçoit la réponse du dernier match des données. Ambigu 0,92 au niveau 0, 0,59 au niveau 2, 0,98 au niveau 3. Disposer d'outils pousse l'agent à agir avant de demander.
4. **Chiffres non soutenus** (gpt-oss-120b, 9 rapports publiés sur 26) : un score inventé (« 5‑0 contre le Brésil ») et des moyennes de possession estimées. La tâche est pourtant comptée réussie : le succès vérifie la présence des faits attendus, pas l'absence d'invention.
5. **Boucle de recherche** (gpt-oss-120b, 5 cas sur 50) : 6 à 7 appels à `search_rules`, de plus en plus en anglais, jusqu'à la borne de 20 000 tokens, sans réponse. La borne contient l'échec.

## Limites

- **Petits effectifs** : 10 cas absents et 10 cas ambigus dans le jeu principal, donc un cas vaut 0,10. Les intervalles sont donnés, les comparaisons sont appariées, et ces deux critères ont été remesurés sur des jeux complémentaires.
- **Ce que mesurent les métriques** : l'exactitude est vérifiée par mots clés, le succès des tâches par la présence des faits attendus dans le rapport publié. Ni l'un ni l'autre ne détecte une invention à côté des faits attendus. La fidélité est jugée par un modèle d'une autre famille, calibré sur 30 annotations humaines (accord 30/30, deux annotateurs), dont 10 erreurs injectées assez nettes.
- **Effet plafond** : avec gpt-6-luna, tâches et pass^3 valent 1,00 au niveau 2. Le niveau 3 ne se mesure que sur les cas ambigus et sur l'absence de régression. Son prompt a été réglé une fois sur les 10 cas absents du jeu principal, d'où la vérification sur 10 cas absents nouveaux.
- **Variabilité** : malgré la température 0, 13 cas ambigus sur 30 ne donnent pas le même résultat à leurs 3 essais au niveau 2.
- **Confirmation automatique en évaluation** : les publications non demandées (échec 2) ne seraient évitées en usage réel que par la vigilance de l'utilisateur.
- **Données et modèle** : les données StatsBomb ouvertes s'arrêtent en 2024 (5 compétitions de sélections) ; le rapport d'avant-match porte donc sur des affiches hypothétiques, et la possession est estimée par la part des passes. Le tableau repose sur un modèle fermé, accessible par une clé prêtée ; gpt-oss-120b mesure l'écart avec un modèle ouvert.
