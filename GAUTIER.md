# Partie de Gautier : données StatsBomb, outils de l'agent, tâches multi-étapes

Rendu final le 30 novembre, 23h59. Ta partie compte pour le niveau 2 (agent), noté avec l'interface et le contrôle des actions (6 points), et pour les tâches de l'évaluation (pass^3).

Répartition (revue le 16 novembre) : deux pistes indépendantes, mise en commun le 28 novembre seulement.
- **Simon** : extension (niveau 3) en entier, tableau final des niveaux 0 à 3, sections du rapport sur l'architecture, le RAG, l'évaluation et l'extension.
- **Gautier** : second annotateur, benchmark de modèles, analyse des 5 échecs, traces de démo, vidéo, sections du rapport sur l'agent, le benchmark, les coûts, les échecs et les limites.
- **À deux, du 28 au 30** : assemblage du rapport, vérification depuis un clone neuf, rendu.

## À faire : ta piste (mise à jour le 16 novembre)

Les sections 1 à 8 plus bas sont faites et restent pour mémoire. Rien de ce qui suit ne dépend du travail de Simon : tout porte sur les niveaux 0 à 2, déjà mesurés.

### État des mesures au 16 novembre

- Le tableau des niveaux utilise maintenant `gpt-6-luna` (clé OpenAI de l'encadrant, raisonnement désactivé), à cause du quota Groq. Niveaux 0 à 2 mesurés sur les 80 cas, pass^3 compris, plus la robustesse et l'injection. Détail dans `docs/decisions.md`, lignes du 16 novembre.
- Niveau 2 avec `gpt-6-luna` : succès des tâches 1,00, pass^3 1,00, exactitude 0,95. Défauts mesurés : cas ambigus 0,60, MRR 0,54. Les chiffres non soutenus sont à 0,00 après correction de la métrique (elle comptait à tort les probabilités écrites en pourcentage) ; avec `gpt-oss-120b`, 3 rapports sur 12 restent signalés (task-02, task-03).
- Les mesures `openai/gpt-oss-120b` restent dans `results/raw_level*.jsonl` (étiquetées par modèle) et servent au benchmark. Au niveau 2, 20 essais de tâches sur 60 sont faits (tâches 1 à 7), le reste est en erreur de quota.
- Tu n'as pas besoin de la clé de l'encadrant : ta clé Groq et Ollama suffisent. Depuis le 16 novembre `.env.example` met `gpt-6-luna` par défaut : pour ton benchmark, garde dans ton `.env` les lignes Groq (`LLM_BASE_URL=https://api.groq.com/openai/v1`, `LLM_MODEL=openai/gpt-oss-120b`, `LLM_REASONING_EFFORT=` vide), ou passe `--model` et `--base-url` à `eval.py`.

### Tes tâches

| # | Tâche | Commande ou fichier | Pour le |
|---|---|---|---|
| G1 | Annotation à l'aveugle des 30 réponses du juge, puis accord entre humains | `python scripts/calibrate_judge.py --annotate --annotateur gautier` puis `--accord` | 18 nov. |
| G2 | Benchmark au niveau 2 sur les tâches : finir `openai/gpt-oss-120b` (40 essais restants, environ 2 jours de quota), puis un modèle Ollama en local | `python eval.py --levels 2 --types task --trials 3 --resume`, puis `--model <modèle> --base-url http://localhost:11434/v1`, puis `python scripts/bench_models.py` | 22 nov. |
| G3 | Analyse de 5 échecs avec leur trace, à partir des résultats déjà dans le dépôt : chiffres non soutenus de gpt-oss-120b (task-02, task-03), cas ambigus ratés au niveau 2, affiche inversée par gpt-oss-120b (task-01, task-03), échec de task-04, abstentions manquées | `docs/echecs.md` | 24 nov. |
| G4 | Traces de démo (une par scène de la vidéo) | `traces/`, ajoutées avec `git add -f` | 25 nov. |
| G5 | Vidéo de 3 à 5 minutes : cas réussi, abstention, tâche multi-étapes avec sa trace, action validée. Les quatre scènes se tournent sur les niveaux 0 à 2 | | 27 nov. |
| G6 | Rapport : agent et outils, benchmark de modèles, coûts, les 5 échecs, limites | `docs/rapport/gautier.md` | 27 nov. |
| G7 | Consigner G1 et G2 dans `docs/decisions.md` (lignes ajoutées en fin de fichier) | | 22 nov. |

### Règles pour travailler sans se gêner

- Partir de `main` après la fusion de la PR 21. Une branche par sujet, puis une pull request.
- Tes fichiers : `results/raw_level0.jsonl` à `raw_level2.jsonl` (pour le benchmark), `results/bench-llm.md`, `docs/echecs.md`, `docs/rapport/gautier.md`, `docs/annotations_fidelite.jsonl`, `traces/`.
- Fichiers de Simon, à ne pas modifier : `src/level3.py`, `eval.py`, `results/table.md`, `results/raw_level3.jsonl`, `docs/rapport/simon.md`.
- Figés pour les deux : `src/tools.py`, `src/agent.py`, `tests.jsonl`. Y toucher oblige à tout remesurer.
- `docs/decisions.md` : ajouter des lignes à la fin, sans modifier les existantes.

### Mise en commun

| Date | Quoi |
|---|---|
| 28 nov. | Assemblage du rapport (4 pages maximum), relecture croisée |
| 29 nov. | Vérification depuis un clone neuf : installation, `pytest`, `python eval.py --table-only`, interface |
| 30 nov. | Rendu, la journée sert de marge |

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

Voir « À faire : ta piste » en haut du fichier.
