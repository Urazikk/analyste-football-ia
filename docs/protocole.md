# Protocole de test

Fixé en semaine 1, identique pour les niveaux 0 à 3. `python eval.py` l'applique. Les ajouts sont datés en fin de fichier et dans `docs/decisions.md`.

## Jeu de test : `tests.jsonl` (80 cas depuis le 9 novembre, 40 au départ)

| Type (`type`) | Nombre | Attendu (`expected`) | Vérification |
|---|---|---|---|
| `doc` | 40 | `keywords` (groupes de synonymes), `relevant_sources` (ids de document ou de section, ex. `ifab-loi-11` ou `ifab-loi-11#1-position-de-hors-jeu` ; un morceau compte s'il commence par l'un d'eux) | mots clés présents, source pertinente citée, Recall@5 et MRR |
| `absent` | 10 | `behavior: abstain` | marqueur `[ABSTENTION]` |
| `task` | 20 | `checks` sur l'état final (`report_published` avec `report` = `<domicile>-vs-<exterieur>`, `must_contain` : mots ou groupes de synonymes dont un seul suffit ; `no_report`) | code (`metrics.check_state`), 3 essais pour pass^3 |
| `ambiguous` | 10 | `behavior: clarify` ou `refuse` | marqueur `[PRECISION]` ou `[REFUS]` |

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
| Chiffres non soutenus | part des rapports publiés (premier essai) qui citent un nombre absent des sorties d'outils du run ; une probabilité citée en pourcentage est soutenue. Diagnostic, ne change pas le succès |
| Tokens/req, coût, latence | moyenne sur le premier essai de chaque cas ; coût au tarif du modèle (`config.PRICES`) |

## Incertitude et comparaison des niveaux

- Chaque métrique de qualité du tableau est donnée avec son intervalle de confiance à 95 % (bootstrap percentile, 2000 tirages, graine `SEED`).
- `python scripts/compare_levels.py` compare les niveaux deux à deux sur les mêmes cas (bootstrap apparié) : différence, intervalle, et part des tirages où le niveau supérieur ne fait pas mieux. Un niveau « aide » si l'intervalle de la différence est au-dessus de 0.
- Les cas en erreur d'infrastructure (quota, réseau) ne sont pas des mesures : ils sont exclus des métriques de qualité, comptés dans la colonne Erreurs, et relancés avec `--resume`. pass^3 ne porte que sur les tâches dont les 3 essais ont abouti.

## Jeux complémentaires (ajouts datés)

`tests.jsonl` n'est pas modifié. Chaque jeu complémentaire est un fichier séparé, relu par Simon avant toute mesure (champ `relu`, vérifié par un test), avec ses résultats dans son propre dossier.

| Date | Fichier | Cas | Rôle | Commande | Résultats |
|---|---|---|---|---|---|
| 9 nov. | `tests_robustesse.jsonl` | 40 reformulations de doc-01 à doc-20 (familier avec fautes, mise en situation) | stabilité des réponses | `python eval.py --tests tests_robustesse.jsonl --out results/robustesse`, puis `python scripts/robustesse.py` | `results/robustesse/` |
| 9 nov. | `tests_injection.jsonl` | 10 cas : 5 documents piégés, 5 sorties d'outils piégées | part des consignes injectées suivies | `python eval.py --tests tests_injection.jsonl --extra-corpus tests/injection --out results/injection` | `results/injection/` |
| 16 nov. | `tests_ambigus.jsonl` | 20 cas ambigus ou hors sujet | critère principal de l'extension, avec les 10 cas ambigus de `tests.jsonl` | `python eval.py --tests tests_ambigus.jsonl --out results/ambigus --trial-types ambiguous --no-judge`, de même avec `--types ambiguous` pour les 10 cas d'origine, puis `python scripts/ambigus.py` | `results/ambigus/` |
| 16 nov. | `tests_absents.jsonl` | 10 cas absents, termes vérifiés hors corpus | contrôle neutre de l'abstention au niveau 3 | `python eval.py --tests tests_absents.jsonl --out results/absents --no-judge` | `results/absents/` |

Règles propres à ces jeux :

- Cas ambigus : 3 essais par cas ; le score d'un cas est la part de ses essais traités comme attendu. On compte aussi les publications non demandées et les outils appelés avant la question de précision.
- Cas absents complémentaires : écrits après la correction du plan du niveau 3 et jamais utilisés pour le régler, parce que cette correction a été faite après lecture des 10 cas absents de `tests.jsonl`.

## Mesure de l'extension (fixée le 16 novembre, avant le code)

Niveau 3 contre niveau 2, bootstrap apparié. Critère principal : Ambigu sur les 30 cas à 3 essais. Non-régression : succès des tâches, pass^3, exactitude, abstention. L'extension « aide » si l'intervalle de la différence sur Ambigu exclut zéro et si pass^3 ne baisse pas de façon fiable. Détail dans `docs/plan.md`, section 6.

## Modèle

Depuis le 16 novembre : `gpt-6-luna`, raisonnement désactivé (`LLM_REASONING_EFFORT=none`), température 0, 1 024 tokens de sortie par appel. Juge de fidélité : `qwen/qwen3.8-27b` sur Groq. Les réponses varient d'un essai à l'autre malgré la température 0 : c'est la raison des 3 essais sur les tâches et sur les cas ambigus.
