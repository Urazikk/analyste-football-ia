# Partie de Gautier : données StatsBomb, outils de l'agent, tâches multi-étapes

Rendu final le 30 novembre, 23h59. Ta partie compte pour le niveau 2 (agent), noté avec l'interface et le contrôle des actions (6 points), et pour les tâches de l'évaluation (pass^3).

Répartition :
- **Simon** : corpus, RAG (niveau 1), 20 cas « doc » et 5 cas « absent », choix des embeddings.
- **Gautier** : données StatsBomb, outils, règles métier, tâches et cas ambigus, benchmark de modèles (détail ci-dessous).
- **À deux** : extension (niveau 3), analyse des 5 échecs, rapport, vidéo.

## À faire : liste complète (mise à jour le 10 novembre)

Tout ce qui te reste jusqu'au rendu, dans l'ordre. Les sections 1 à 8 plus bas sont faites (PR #3 à #8, #11 à #16) et restent pour mémoire.

### A. Mesures (avec ta clé Groq, chaque jour, `--resume`)

Les outils du niveau 2 sont figés depuis la PR #16 : ne plus en ajouter ni en modifier, sinon tout le niveau 2 est à remesurer. Simon mesure les cas doc, absents, robustesse et injection ; toi les tâches et les cas ambigus.

| # | Tâche | Commande | Pour le |
|---|---|---|---|
| A1 | Cas ambigus, niveaux 0, 1 et 2 (10 cas, peu coûteux) | `python eval.py --levels 0 1 2 --types ambiguous --resume` | 13 nov. |
| A2 | Tâches, niveaux 0 et 1 (sans outils : échec attendu, mais le tableau doit être complet) | `python eval.py --levels 0 1 --types task --resume` | 14 nov. |
| A3 | Tâches au niveau 2 avec pass^3 (20 tâches x 3 essais, le plus cher : plusieurs jours) | `python eval.py --levels 2 --types task --resume` | 20 nov. |
| A4 | Benchmark de modèles sur les tâches au niveau 2 : qwen3.8-27b (Groq), un modèle Ollama en local | `python eval.py --levels 2 --types task --model <modèle> --resume` puis `python scripts/bench_models.py` | 21 nov. |
| A5 | Consigner dans `docs/decisions.md` : succès, pass^3, chiffres non soutenus, coût des tâches, résultat du benchmark | | 21 nov. |

Avant chaque lancement complet : `--limit 3` pour vérifier. Pousser les résultats bruts (`results/raw_level*.jsonl`) au fil de l'eau, ils s'ajoutent à ceux de Simon sans les écraser.

### B. Évaluation

| # | Tâche | Commande | Pour le |
|---|---|---|---|
| B1 | Annotation à l'aveugle des 30 réponses du juge (ordre mélangé, identifiants masqués, tes réponses dans un champ séparé) | `python scripts/calibrate_judge.py --annotate --annotateur gautier` | 15 nov. |
| B2 | Accord entre vous deux, sans LLM | `python scripts/calibrate_judge.py --accord` | 15 nov. |
| B3 | Liste des échecs du niveau 2 sur les tâches, avec l'identifiant de la trace (`traces/`) : outil mal appelé, boucle qui tourne, chiffre inventé, publication non demandée... | dans `docs/decisions.md` ou `docs/echecs.md` | 21 nov. |

### C. Décisions communes

| Date | Quoi |
|---|---|
| 18 nov. | Option C du pronostic (LLM seul contre agent avec simulation) : oui ou non, selon l'avancement |
| 22 nov. | Choix de l'extension (une seule technique), d'après les défauts mesurés au niveau 2 : les tiens (B3) et ceux de Simon (agent qui cherche en anglais, recherche sensible aux reformulations, coût 3,5 fois celui du RAG) |

### D. Semaine du 23 novembre (à deux)

| # | Tâche | Pour le |
|---|---|---|
| D1 | Extension : code, tests, mesure contre le niveau 2 (répartition fixée le 22) | 27 nov. |
| D2 | Rapport : tes parties dans `docs/rapport/rapport.md` (agent et tâches, pass^3, benchmark de modèles, coût des tâches, deux des cinq échecs) ; `python scripts/build_report.py` régénère le PDF | 28 nov. |
| D3 | Vidéo : les scènes « tâche multi-étapes avec sa trace » et « action validée » (publication d'un rapport depuis l'interface, puis PDF) | 28 nov. |
| D4 | Vérification depuis un clone neuf : installation, `pytest`, `python eval.py --table-only`, interface | 29 nov. |

## 0. Installation (une fois)

```bash
git clone https://github.com/Urazikk/analyste-football-ia.git
cd analyste-football-ia
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # mettre ta clé Groq gratuite (console.groq.com) dans LLM_API_KEY
python scripts/build_corpus.py --no-wiki --ifab-download   # lois IFAB en local (non versionnées)
git config user.name "Ton Nom"
git config user.email "ton@email"
pytest                        # tout doit passer
```

Lis avant de coder : `CLAUDE.md` (règles du projet), `docs/protocole.md` (protocole de test), `src/agent.py` (la boucle est déjà faite et testée).

## Règles de travail

- Une branche par sujet (`git checkout -b outils-statsbomb`), puis une pull request relue par Simon. Jamais de push direct sur `main`.
- Commits petits et clairs, à ton nom.
- Aucune clé d'API dans le code. Elle va dans `.env` uniquement.
- Type hints, code simple, un test pytest par règle métier. Les tests ne doivent pas appeler le LLM : utiliser le faux LLM de `tests/test_agent.py`.
- Chaque choix chiffré (nombre de matchs analysés, bornes de l'agent, modèle) va dans `docs/decisions.md` avec sa mesure.

## Budget : gratuit uniquement

- LLM : `openai/gpt-oss-120b` via Groq, offre gratuite. Limites : 8 000 tokens par minute et 200 000 tokens par jour, par compte. Utilise ta propre clé : ton quota s'ajoute à celui de Simon.
- Un cas du niveau 2 coûte environ 4 000 tokens ; une tâche avec pass^3 en coûtera bien plus. Compter plusieurs jours pour l'évaluation complète.
- `python eval.py ... --resume` ne relance que les cas manquants ou en erreur : lancer, laisser le quota s'épuiser, reprendre le lendemain. `--limit 3` pour tester avant de tout lancer.
- `pytest` n'appelle jamais l'API (faux LLM) : développer et tester sans consommer de quota.
- Benchmark de modèles : `qwen/qwen3.8-27b` sur Groq (quota séparé par modèle) et un modèle Ollama en local (gratuit, sans quota).

## Contexte déjà décidé

- Compétitions StatsBomb (`config.COMPETITIONS`) : Euro 2020 et 2024, Copa América 2024, Coupe du monde 2018 et 2022 (262 matchs, cache de 872 Mo : `python scripts/fetch_statsbomb.py`).
- Pronostic : 49 940 matchs internationaux en cache (`data/cache/intl/`, `python scripts/eval_prediction.py` les télécharge).
- LLM : `openai/gpt-oss-120b` via Groq ; juge de fidélité : `qwen/qwen3.8-27b`.
- `publish_report` est la seule action irréversible : règles métier vérifiées par du code, puis confirmation. Le rapport porte sur une affiche donnée par l'utilisateur, avec les sections chiffrées calculées par le code (forme, confrontations, dernier match, pronostic).
- Jeu de test : 80 cas (40 doc, 10 absents, 20 tâches, 10 ambigus), plus 40 reformulations (`tests_robustesse.jsonl`) et 10 cas d'injection (`tests_injection.jsonl`).

## 1. Couche de données StatsBomb (`src/data.py`) : fait

- Charger matchs et événements via `statsbombpy` (`sb.matches`, `sb.events`), sans clé.
- Mettre en cache sur disque dans `data/cache/` (déjà ignoré par git) : un fichier par match. Deuxième appel sans réseau.
- `resolve_team(name) -> str` : nom français ou anglais vers le nom StatsBomb (« Espagne » vers `Spain`). Erreur claire si l'équipe n'existe pas, avec des suggestions.
- Script `scripts/fetch_statsbomb.py` qui remplit le cache pour les 3 compétitions.

Fini quand : le cache se remplit, `resolve_team` est testé, rien n'est téléchargé deux fois.

## 2. Les 4 outils de lecture et de calcul (`src/tools.py`) : fait

Les schémas JSON sont déjà dans `REGISTRY`. Tu peux les ajuster, en gardant un effet par outil (`read`, `compute`, `irreversible`).

| Outil | Effet | Ce qu'il renvoie |
|---|---|---|
| `list_matches(team)` | read | derniers matchs de l'équipe : id, date, compétition, adversaire, score. Trié du plus récent au plus ancien. |
| `match_events(match_id, event_type, team)` | read | événements filtrés, **résumés** (pas le DataFrame brut : la sortie est coupée à 8000 caractères). |
| `team_stats(match_id, team)` | compute | tirs, tirs cadrés, xG, buts, passes réussies (%), possession estimée. |
| `plot_shots(match_id, team)` | compute | carte des tirs en PNG dans `data/state/plots/`, renvoie le chemin. |

Points d'attention :
- Une erreur (équipe inconnue, match absent) doit être une exception avec un message utile. La boucle la renvoie au modèle, qui peut se corriger.
- Sorties courtes et en JSON simple : moins de tokens, meilleure fiabilité.

Fini quand : chaque outil a un test sur un match réel (depuis le cache), et `python -c "from src.tools import REGISTRY; ..."` marche.

## 3. Règles métier de `publish_report` (`check_publish_report`) : fait

Déjà fait : rapport unique par affiche, contenu de 200 caractères minimum. À ajouter, vérifié par du code :
- les deux équipes existent dans les données et sont différentes ;
- le rapport cite au moins un chiffre ;
- (bonus) chaque chiffre cité apparaît dans un résultat d'outil de l'exécution en cours : c'est une vraie mesure de fidélité.

Fini quand : un test pytest par règle.

## 4. Interface (`src/app.py`) : fait

- Afficher l'image quand `plot_shots` a été appelé.
- Vérifier le parcours de validation : bouton Valider, rapport publié, trace visible. Il servira pour la vidéo.

## 5. Jeu de test : 10 tâches et 5 cas ambigus (`tests.jsonl`) : fait

Format dans `docs/protocole.md`, exemples `task-01`, `amb-01`, `amb-02` déjà présents.
Les 20 cas `doc` et 5 cas `absent` de Simon sont écrits : ajouter tes lignes à la suite, sans toucher aux leurs. `pytest` vérifie que les identifiants restent uniques.
- **10 tâches multi-étapes**, l'état final vérifié par `metrics.check_state`. Varier : rapport simple, rapport avec un chiffre précis (`must_contain`), équipe écrite en français, équipe inexistante (attendu : `no_report`), demande d'analyse **sans** demande de publication (attendu : `no_report`).
- **5 cas ambigus ou hors sujet** : `clarify` (« le dernier match », sans équipe) ou `refuse` (hors football).
- Vérifier les réponses attendues à la main dans les données, avant de lancer le modèle.

## 6. Mesures : voir « À faire », partie A

```bash
python scripts/fetch_statsbomb.py                                  # cache des données (une fois)
python eval.py --levels 2 --types task --trials 3 --limit 3        # essai : 3 tâches, environ 40 000 tokens
python eval.py --levels 2 --types task --trials 3 --resume         # 10 tâches x 3 essais, à relancer le lendemain si 429
```

- Les résultats s'ajoutent à `results/raw_level2.jsonl`, étiquetés par modèle : relancer sur les tâches n'efface plus les cas doc du niveau 2 ni les autres modèles.
- Colonne « Chiffres non soutenus » : part des rapports publiés qui citent un chiffre absent des sorties d'outils du run (diagnostic, ne change pas le succès).
- Benchmark au niveau 2, puis tableau comparatif dans `results/bench-llm.md` :

```bash
python eval.py --levels 2 --types task --model qwen/qwen3.8-27b --resume
ollama pull qwen3:8b   # ou un autre petit modèle qui gère les appels d'outils
python eval.py --levels 2 --types task --model qwen3:8b --base-url http://localhost:11434/v1 --resume
python scripts/bench_models.py
```

- Consigner succès, pass^3, chiffres non soutenus, tokens et latence dans `docs/decisions.md`.
- Noter les échecs observés (outil mal appelé, boucle qui tourne, chiffre inventé) : ils servent à choisir l'extension du niveau 3.

## 7. Plan ambitieux (9 novembre) : fait, sauf mesures, annotation et benchmark (voir « À faire »)

Les sections 1 à 5 sont faites (PR #3 à #8). Détail et raisons dans `docs/plan.md`, section 3.

| Tâche | Fini quand | Pour le |
|---|---|---|
| A2 : 10 tâches et 5 cas ambigus de plus dans `tests.jsonl` (task-11 à task-20, amb-06 à amb-10), chiffres vérifiés par `tests/test_tasks_ground_truth.py` | 80 cas, pytest vert | 15 nov. |
| C1 : outils `team_form` (5 derniers matchs : résultats, buts, xG) et `head_to_head` | un test par outil, valeurs vérifiées à la main | 15 nov. |
| Mesures des tâches au niveau 2 avec pass^3, avec ta clé Groq et `--resume` | `results/raw_level2.jsonl` complet sur les tâches | 22 nov. |
| A4 (partie outils) : sorties d'outils piégées par une consigne injectée ; cas de type `injection` (mot témoin `CANARI-7Q`, voir `tests_injection.jsonl` et `tests/test_injection.py`) | taux d'obéissance mesuré ; aucune publication sans confirmation | 22 nov. |
| A5 : annoter à l'aveugle les 30 réponses du juge (`python scripts/calibrate_judge.py --annotate`, sans regarder les annotations de Simon ni le juge) | accord entre humains calculé | 22 nov. |
| C2 : rapport d'avant-match structuré (forme, confrontations, cartes de tirs) ; Simon fait l'export PDF et l'interface | rapport complet publié depuis l'interface | 22 nov. |
| C4 : Euro 2020 et CdM 2018 dans `config.COMPETITIONS` pour l'historique des confrontations | cache rempli, tests des tâches toujours verts | 22 nov. |
| Benchmark de modèles (gpt-oss-120b, qwen3.8-27b, un modèle Ollama) | `results/bench-llm.md` | 22 nov. |

## 8. Pronostic (option B) : fait (PR #16)

Simon a fait le modèle (`src/predict.py` : `predict.simulate(home, away, neutral)`), son évaluation sur le passé (`results/prediction/backtest.md`) et l'animation (`src/animation.py`, onglet « Pronostic »). À toi, pour le 18 novembre :
- outil `simulate_match(home_team, away_team, neutral)` dans `src/tools.py`, effet `compute`, sortie courte (probabilités, scores probables, Elo, note) ;
- correspondance des noms : français et StatsBomb vers ceux du jeu international (mêmes noms anglais dans la plupart des cas ; vérifier « Korea Republic » et les autres écarts), erreur claire sinon ;
- section « Pronostic » dans le rapport structuré (`report.build_sections` et `to_markdown`), donc aussi dans le PDF ;
- un test par point, sans réseau (le CSV est en cache dans `data/cache/intl/`, `python scripts/eval_prediction.py` le télécharge).

## Calendrier

| Quand | Quoi |
|---|---|
| 11 au 15 nov. | A1, A2, B1, B2 ; début de A3 |
| 16 au 21 nov. | A3, A4, A5, B3 ; 18 nov. : option C du pronostic |
| 22 nov. | choix de l'extension, avec Simon |
| 23 au 29 nov. | D1 à D4, avec Simon |
