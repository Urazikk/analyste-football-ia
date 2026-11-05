# Protocole de test

Fixé en semaine 1, identique pour les niveaux 0 à 3. `python eval.py` l'applique.

## Jeu de test : `tests.jsonl` (40 cas)

| Type (`type`) | Nombre | Attendu (`expected`) | Vérification |
|---|---|---|---|
| `doc` | 20 | `keywords` (groupes de synonymes), `relevant_sources` (ids de morceaux) | mots clés présents, source pertinente citée, Recall@5 et MRR |
| `absent` | 5 | `behavior: abstain` | marqueur `[ABSTENTION]` |
| `task` | 10 | `checks` sur l'état final | code (`metrics.check_state`), 3 essais pour pass^3 |
| `ambiguous` | 5 | `behavior: clarify` ou `refuse` | marqueur `[PRECISION]` ou `[REFUS]` |

Exemple de ligne :

```json
{"id": "doc-01", "type": "doc", "question": "...", "expected": {"keywords": [["onze", "11"]], "relevant_sources": ["loi-03#1"]}}
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
| Citation / fidélité | source pertinente citée ; fidélité aux sources à mesurer par juge LLM (à faire) |
| Abstention | part des cas `absent` où le système s'abstient |
| Ambigu | part des cas `ambiguous` traités comme attendu |
| Succès tâches | cas `task`, premier essai |
| pass^3 | cas `task`, réussite des 3 essais |
| Tokens/req, latence | moyenne sur le premier essai de chaque cas |
