# Protocole de test

Fixé en semaine 1, identique pour les niveaux 0 à 3. `python eval.py` l'applique.

## Jeu de test : `tests.jsonl` (40 cas)

| Type (`type`) | Nombre | Attendu (`expected`) | Vérification |
|---|---|---|---|
| `doc` | 20 | `keywords` (groupes de synonymes), `relevant_sources` (ids de document ou de section, ex. `ifab-loi-11` ou `ifab-loi-11#1-position-de-hors-jeu` ; un morceau compte s'il commence par l'un d'eux) | mots clés présents, source pertinente citée, Recall@5 et MRR |
| `absent` | 5 | `behavior: abstain` | marqueur `[ABSTENTION]` |
| `task` | 10 | `checks` sur l'état final (`report_published` avec `report` = `<domicile>-vs-<exterieur>`, `must_contain` : mots ou groupes de synonymes dont un seul suffit ; `no_report`) | code (`metrics.check_state`), 3 essais pour pass^3 |
| `ambiguous` | 5 | `behavior: clarify` ou `refuse` | marqueur `[PRECISION]` ou `[REFUS]` |

Exemple de ligne :

```json
{"id": "doc-01", "type": "doc", "question": "...", "expected": {"keywords": [["onze", "11"]], "relevant_sources": ["ifab-loi-03"]}}
```

## Règles

- Température 0, graine fixée (`SEED`), même modèle pour tous les niveaux.
- Chaque essai de tâche part d'un état vide (dossier temporaire `STATE_DIR`).
- En évaluation, l'utilisateur simulé valide toute action demandée : on mesure si l'état final est correct, y compris quand aucune publication n'était attendue (`no_report`).
- Le jeu de test n'est pas modifié après les premières mesures. Tout ajout est daté dans `docs/decisions.md`.

## Métriques

| Métrique | Calcul |
|---|---|
| Recall@5, MRR | sur les cas `doc`, à partir de `Result.retrieved` (niveaux 1 et plus) |
| Exactitude | cas `doc` : règles par mots clés. Juge LLM à calibrer sur 20 cas annotés si les règles ne suffisent pas |
| Citation | source pertinente citée (id attendu parmi les sources de la réponse) |
| Fidélité | cas `doc` répondus (sans abstention), niveaux 1 et plus : juge LLM (`src/judge.py`, `JUDGE_MODEL`, autre famille que le modèle évalué) qui vérifie que chaque affirmation est soutenue par les extraits cités. Réponse sans citation : non fidèle. Juge calibré sur 20 réponses annotées à la main (`scripts/calibrate_judge.py`) |
| Abstention | part des cas `absent` où le système s'abstient |
| Ambigu | part des cas `ambiguous` traités comme attendu |
| Succès tâches | cas `task`, premier essai |
| pass^3 | cas `task`, réussite des 3 essais |
| Tokens/req, latence | moyenne sur le premier essai de chaque cas |

## Incertitude et comparaison des niveaux

- Chaque métrique de qualité du tableau est donnée avec son intervalle de confiance à 95 % (bootstrap percentile, 2000 tirages, graine `SEED`).
- `python scripts/compare_levels.py` compare les niveaux deux à deux sur les mêmes cas (bootstrap apparié) : différence, intervalle, et part des tirages où le niveau supérieur ne fait pas mieux. Un niveau « aide » si l'intervalle de la différence est au-dessus de 0.

