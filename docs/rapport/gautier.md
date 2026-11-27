# Sections de Gautier (à intégrer dans rapport.md le 28 novembre)

Brouillon du 16 novembre. Les passages [EN ATTENTE] se remplissent avec les mesures en cours (benchmark gpt-oss-120b, modèle Ollama).

## Agent et outils (niveau 2)

La boucle de l'agent est écrite à la main (`src/agent.py`), sans framework. À chaque pas, le modèle reçoit les schémas JSON des 9 outils et choisit d'appeler un outil ou de répondre. La boucle s'arrête à 8 pas ou 20 000 tokens. Une erreur d'outil (équipe inconnue, argument hors schéma, outil inexistant) n'arrête pas l'exécution : elle est renvoyée au modèle, qui corrige au pas suivant.

| Outil | Effet | Rôle |
|---|---|---|
| `search_rules` | read | extraits des lois du jeu (RAG du niveau 1) |
| `list_matches`, `match_events` | read | matchs et événements StatsBomb (262 matchs, 5 compétitions) |
| `team_stats`, `team_form`, `head_to_head`, `simulate_match` | compute | statistiques d'un match, forme sur 5 matchs, confrontations, pronostic Elo + Poisson |
| `plot_shots` | compute | carte des tirs (PNG) |
| `publish_report` | irreversible | publication du rapport d'avant-match |

`publish_report` est la seule action irréversible. Elle passe d'abord par des règles métier vérifiées par du code : les équipes existent dans les données, elles sont différentes, le rapport fait au moins 200 caractères, il cite au moins un chiffre et aucun rapport n'existe déjà pour cette affiche. Elle passe ensuite par la validation de l'utilisateur dans l'interface. La validation et le refus sont écrits dans la trace JSONL du run. À la publication, le code ajoute lui-même les sections chiffrées du rapport (forme, confrontations, cartes des tirs, pronostic) : le modèle n'écrit que l'analyse.

## Benchmark de modèles (niveau 2, 20 tâches, 3 essais)

| Modèle | Poids | Succès tâches | pass^3 | Chiffres non soutenus | Tokens par tâche | Latence médiane |
|---|---|---|---|---|---|---|
| gpt-6-luna (OpenAI) | fermés | 1,00 | 1,00 | 0,00 | 7 945 | 3,0 s |
| gpt-oss-120b (Groq) | ouverts | [EN ATTENTE : 20 essais sur 60 mesurés] | [EN ATTENTE] | 3 rapports sur 12 | 8 367 | 14,5 s |
| [modèle Ollama local] | ouverts | [EN ATTENTE] | | | | |

Lecture provisoire : sur les tâches déjà mesurées, gpt-oss-120b échoue uniquement en inversant l'affiche (7 essais sur 7, voir les échecs) et cite parfois des chiffres absents des outils. gpt-6-luna ne fait ni l'un ni l'autre. Le choix de gpt-6-luna pour le tableau est contraint par le quota gratuit de Groq (200 000 tokens par jour, environ 25 tâches de niveau 2). Le sujet conseille un modèle ouvert : gpt-oss-120b reste la référence ouverte du benchmark.

## Coût

Tarifs : gpt-6-luna 0,10 $ en entrée et 0,50 $ en sortie par million de tokens (relevé du 16 novembre 2026) ; gpt-oss-120b sur Groq 0,15 $ et 0,60 $ (tarif payant équivalent ; l'offre utilisée est gratuite). Coût moyen par requête, premier essai, 80 cas :

| Niveau | gpt-6-luna : tokens / coût pour 1 000 requêtes | gpt-oss-120b : tokens / coût pour 1 000 requêtes |
|---|---|---|
| 0, LLM seul | 161 / 0,03 $ | 414 / 0,16 $ |
| 1, RAG | 759 / 0,09 $ | 964 / 0,22 $ |
| 2, agent | 4 212 / 0,50 $ | 5 524 / 1,04 $ |
| 3, planification | 4 333 / 0,51 $ | non mesuré |

L'agent coûte environ 5,5 fois le RAG. Sur les questions de règles, il répond plus juste (exactitude 0,95 contre 0,82), mais il cite moins fidèlement (fidélité 0,82 contre 0,97) et retrouve moins bien les passages (MRR 0,54 contre 0,75). Ce surcoût se justifie surtout pour les tâches, où il est le seul à publier un rapport juste (1,00 contre 0,25 aux niveaux 0 et 1, qui ne réussissent que les tâches sans publication). Une tâche coûte environ 7 900 tokens, soit 0,001 $ avec gpt-6-luna. Le niveau 3 n'ajoute que 3 % de tokens au niveau 2.

## Analyse de cinq échecs

Détail, preuves et traces : `docs/echecs.md`.

1. **Affiche inversée** (gpt-oss-120b, les 7 échecs de tâches) : l'agent recopie l'ordre domicile/extérieur du dernier match renvoyé par `list_matches` au lieu de celui demandé. Les règles métier ne vérifient pas l'ordre.
2. **Publication sur une affiche choisie par l'agent** (gpt-6-luna, amb-08) : « le rapport de la Coupe du monde 2026 » devient un rapport États-Unis - Mexique publié. Toutes les règles passent, et seule la validation humaine protège. 4 publications non demandées sur 90 essais ambigus au niveau 2, 0 au niveau 3.
3. **Supposition au lieu d'une question** (gpt-6-luna) : « Qui a gagné le match ? » reçoit la réponse du dernier match des données. Ambigu 0,92 au niveau 0, 0,59 au niveau 2, 0,98 au niveau 3. Disposer d'outils pousse l'agent à agir avant de demander.
4. **Chiffres non soutenus** (gpt-oss-120b, 3 rapports sur 12) : un score inventé (« 5‑0 contre le Brésil ») et des moyennes de possession estimées. La tâche est pourtant comptée réussie : le succès vérifie la présence des faits attendus, pas l'absence d'invention.
5. **Boucle de recherche** (gpt-oss-120b, 5 cas sur 50) : 6 à 7 appels à `search_rules`, de plus en plus en anglais, jusqu'à la borne de 20 000 tokens, sans réponse. La borne contient l'échec.

## Limites

- **Mesure des tâches** : le succès vérifie des mots et nombres attendus dans le rapport publié. Il ne détecte ni une invention à côté des faits attendus, ni une analyse creuse.
- **Effet plafond** : avec gpt-6-luna, tâches et pass^3 valent 1,00 au niveau 2. Le niveau 3 ne peut se mesurer que sur les cas ambigus et sur l'absence de régression.
- **Confirmation automatique en évaluation** : les publications non demandées (échec 2) ne seraient évitées en usage réel que par la vigilance de l'utilisateur.
- **Données** : les données StatsBomb ouvertes s'arrêtent en 2024 et ne couvrent que 5 compétitions de sélections. Le rapport d'avant-match porte donc sur des affiches hypothétiques à partir des derniers matchs disponibles. La possession est estimée par la part des passes.
- **Modèle** : le tableau repose sur un modèle fermé, accessible par une clé prêtée. Les mesures gpt-oss-120b montrent l'écart avec un modèle ouvert.
