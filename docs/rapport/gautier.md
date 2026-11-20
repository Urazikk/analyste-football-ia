# Sections de Gautier : agent, benchmark, coût, échecs, limites

Version resserrée le 18 novembre pour tenir en 4 pages ; détail des échecs et traces dans `docs/echecs.md`.

## Agent, outils et contrôle de l'action

La boucle est écrite à la main (`src/agent.py`, sans framework) : à chaque pas, le modèle reçoit les schémas JSON de 9 outils et choisit d'en appeler un ou de répondre ; elle s'arrête à 8 pas ou 20 000 tokens, et une erreur d'outil (équipe inconnue, argument hors schéma, outil inexistant) est renvoyée au modèle, qui se corrige. Outils classés par effet : **read** (`search_rules`, `list_matches`, `match_events`), **compute** (`team_stats`, `team_form`, `head_to_head`, `simulate_match`, `plot_shots`), **irreversible** (`publish_report`). La publication passe par des règles métier vérifiées par du code (équipes existantes et différentes, 200 caractères et au moins un chiffre, un seul rapport par affiche), puis par la validation de l'utilisateur, tracée dans le JSONL du run. Le code ajoute ensuite lui-même les sections chiffrées du rapport (forme, confrontations, cartes des tirs, pronostic).

## Benchmark de modèles et coût

{{benchmark}}

Le modèle ouvert échoue en inversant l'affiche demandée (échec 1) ou en s'arrêtant sans publier, cite plus souvent des chiffres absents des outils, et répond bien plus lentement. Le tableau des niveaux utilise gpt-6-luna, imposé par le quota gratuit de Groq (200 000 tokens par jour, une vingtaine de tâches) ; gpt-oss-120b reste la référence ouverte. {{couts}} L'agent coûte 5,5 fois le RAG : un surcoût justifié par les tâches, qu'il est le seul à réussir.

## Analyse de cinq échecs

1. **Affiche inversée** (gpt-oss-120b, 11 de ses 25 essais ratés) : il recopie l'ordre domicile et extérieur du dernier match renvoyé par `list_matches` au lieu de celui demandé ; les règles métier ne vérifient pas l'ordre. Les 14 autres s'arrêtent sans rien publier, souvent sur la borne de 8 pas.
2. **Publication sur une affiche choisie par l'agent** (gpt-6-luna) : « le rapport de la Coupe du monde 2026 » devient un rapport États-Unis contre Mexique, toutes les règles passent ; 4 publications non demandées sur 90 essais ambigus au niveau 2, aucune au niveau 3.
3. **Supposition au lieu d'une question** (gpt-6-luna) : « Qui a gagné le match ? » reçoit le résultat du dernier match des données. Disposer d'outils pousse l'agent à agir avant de demander ; c'est le défaut qui a motivé l'extension.
4. **Chiffre inventé** (gpt-oss-120b) : « 5-0 contre le Brésil », match absent des sorties d'outils, dans un rapport pourtant compté réussi : le succès vérifie la présence des faits attendus, pas l'absence d'invention.
5. **Boucle de recherche** (gpt-oss-120b, 5 cas sur 50) : 6 à 7 appels à `search_rules`, de plus en plus en anglais, jusqu'à la borne de 20 000 tokens, sans réponse. La borne contient l'échec. Proche : arguments d'outil en JSON invalide, refusés par l'API (4 essais).

## Limites et coût

- **Mesure des tâches** : elle ne voit ni une invention à côté des faits attendus, ni l'ordre de l'affiche hors du nom de fichier ; avec gpt-6-luna, tâches et pass^3 sont au plafond (1,00), d'où la mesure de l'extension sur les cas ambigus.
- **Confirmation automatique en évaluation** : en usage réel, seule la vigilance de l'utilisateur arrête une publication non demandée au niveau 2.
- **Données** : StatsBomb ouvert s'arrête en 2024 et couvre cinq compétitions de sélections ; les rapports portent sur des affiches hypothétiques, et la possession est estimée par la part des passes.
- **Modèle** : le tableau repose sur un modèle fermé, par une clé prêtée ; les mesures de gpt-oss-120b montrent l'écart avec un modèle ouvert.
