# Analyste de football : un système génératif qui se mesure

Projet du cours Generative AI (ECE, Dr. Issam Falih), parcours Texte. Rendu le 30 novembre 2026.

Un assistant qui répond aux questions sur le football et prépare des rapports d'avant-match, construit en 4 niveaux comparés sur le même protocole de test :

| Niveau | Fichier | Contenu |
|---|---|---|
| 0 · LLM seul | `src/llm.py` | prompt soigné, sans documents ni outils |
| 1 · RAG | `src/rag.py` | lois du jeu, recherche dense ou hybride, citations, abstention |
| 2 · Agent | `src/agent.py`, `src/tools.py` | boucle écrite à la main, outils StatsBomb, confirmation avant publication |
| 3 · Agent avec plan | `src/level3.py` | planification : un plan sans outils décide (précision, refus ou exécution) avant la boucle de l'agent |

## Installation

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # clé OpenAI (gpt-6-luna) dans LLM_API_KEY, clé Groq gratuite (juge) dans JUDGE_API_KEY
```

Sans GPU, installer d'abord torch en version processeur évite plusieurs Go de bibliothèques CUDA :
`pip install torch --index-url https://download.pytorch.org/whl/cpu`, puis `pip install -r requirements.txt`.
Versions exactes de l'environnement testé : `requirements-lock.txt`.

## Corpus

```bash
python scripts/build_corpus.py                      # articles Wikipédia (FR)
python scripts/build_corpus.py --no-wiki --ifab-download                  # + lois du jeu IFAB 2026/27 (PDF FR)
python scripts/build_corpus.py --inspect <Lois_du_jeu_FR.pdf>              # diagnostic si le découpage échoue
python -m src.rag --list                            # identifiants des morceaux, pour tests.jsonl
```

Les articles Wikipédia (CC BY-SA 4.0) sont versionnés dans `data/corpus/wiki/` avec leur numéro de révision, pour que l'évaluation soit reproductible. Les lois de l'IFAB ne sont pas redistribuées : `--ifab-download` télécharge le PDF français 2026/27 dans `data/cache/` (non versionné) puis le découpe (une loi par fichier, plus le protocole VAR). `--ifab-pdf` accepte un PDF local. `data/corpus/manifest.json` liste les documents et leur empreinte sha256.

## Données de match

```bash
python scripts/fetch_statsbomb.py     # matchs et événements StatsBomb des 5 compétitions (2 min, environ 870 Mo, data/cache/)
python scripts/eval_prediction.py     # résultats internationaux pour le pronostic (téléchargés une fois), puis évaluation
```

Sans ces deux caches, l'agent ne peut pas répondre sur les matchs et les tests qui en dépendent sont sautés.

Le jeu de résultats internationaux (martj42/international_results) est mis à jour en continu : `results/prediction/` a été produit avec les matchs connus au 6 octobre 2026 (1 803 matchs évalués). Relancé plus tard, il inclut les matchs joués depuis, et les scores bougent légèrement (Brier 0,494 au lieu de 0,497 le 27 novembre).

## Livrables

- Rapport : `docs/rapport/rapport.pdf` (4 pages), régénéré par `python scripts/build_report.py`.
- Vidéo de démonstration : `docs/video/demo.mp4` (3 min 08), scénario dans `docs/video.md`.
- Résultats : `results/table.md` (niveaux 0 à 3), `results/comparaison.md`, résultats bruts `results/raw_level{0..3}.jsonl`, benchmark `results/bench-llm.md`.
- Analyse de cinq échecs : `docs/echecs.md`. Choix et mesures : `docs/decisions.md`. Protocole : `docs/protocole.md`.

## Utilisation

```bash
python eval.py              # sans LLM_API_KEY : refait results/table.md depuis les résultats bruts, sans appel ;
                            # avec la clé : relance les mesures des niveaux 0 à 3, puis refait le tableau
python eval.py --table-only # refait le tableau sans appel, même avec une clé
python eval.py --resume     # ne relance que les cas manquants ou en erreur
streamlit run src/app.py    # interface
pytest                      # tests unitaires (sans API)
python scripts/compare_levels.py   # comparaison appariée des niveaux (sans appel)
python scripts/build_report.py     # rapport PDF (docs/rapport/), tableaux recalculés depuis results/ ; pandoc et Chrome requis
python scripts/robustesse.py --retrieval   # robustesse de la recherche aux reformulations (sans appel)
python eval.py --tests tests_injection.jsonl --extra-corpus tests/injection --out results/injection   # injection de consignes
```

## Organisation

```
eval.py           évaluation de tous les niveaux sur tests.jsonl
tests.jsonl       jeu de test (80 cas)
scripts/          construction du corpus
src/              code des niveaux, outils, métriques, traces, interface
tests/            tests pytest
docs/             sujet, protocole de test, journal des décisions mesurées
data/corpus/      documents du RAG
results/          résultats bruts par niveau et tableau
traces/           une trace JSONL par exécution ; mesures archivées dans mesures-<date>.jsonl.gz (scripts/archive_traces.py)
```

Répartition du travail : `GAUTIER.md`. Protocole de test : `docs/protocole.md`. Choix techniques et mesures : `docs/decisions.md`.
