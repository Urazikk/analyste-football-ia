# Analyste de football : un système génératif qui se mesure

Projet de la mineure IA générative (ECE, Dr. Issam Falih), parcours Texte. Rendu le 30 novembre 2026.

Un assistant qui répond aux questions sur le football et prépare des rapports d'avant-match, construit en 4 niveaux comparés sur le même protocole de test :

| Niveau | Fichier | Contenu |
|---|---|---|
| 0 · LLM seul | `src/llm.py` | prompt soigné, sans documents ni outils |
| 1 · RAG | `src/rag.py` | lois du jeu, recherche dense ou hybride, citations, abstention |
| 2 · Agent | `src/agent.py`, `src/tools.py` | boucle écrite à la main, outils StatsBomb, confirmation avant publication |
| 3 · Extension | à venir | une technique choisie d'après un défaut mesuré au niveau 2 |

## Installation

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # puis remplir la clé et le modèle
```

## Corpus

```bash
python scripts/build_corpus.py                      # articles Wikipédia (FR)
python scripts/build_corpus.py --no-wiki --ifab-pdf <Lois_du_jeu_FR.pdf>   # + lois du jeu IFAB
python scripts/build_corpus.py --inspect <Lois_du_jeu_FR.pdf>              # diagnostic si le découpage échoue
python -m src.rag --list                            # identifiants des morceaux, pour tests.jsonl
```

Les articles Wikipédia (CC BY-SA 4.0) sont versionnés dans `data/corpus/wiki/` avec leur numéro de révision, pour que l'évaluation soit reproductible. Les lois de l'IFAB ne sont pas redistribuées : télécharger le PDF français sur theifab.com, puis lancer le script. `data/corpus/manifest.json` liste les documents et leur empreinte sha256.

## Utilisation

```bash
python eval.py              # reproduit le tableau de résultats (results/table.md)
streamlit run src/app.py    # interface
pytest                      # tests unitaires (sans API)
```

## Organisation

```
eval.py           évaluation de tous les niveaux sur tests.jsonl
tests.jsonl       jeu de test (40 cas)
scripts/          construction du corpus
src/              code des niveaux, outils, métriques, traces, interface
tests/            tests pytest
docs/             sujet, protocole de test, journal des décisions mesurées
data/corpus/      documents du RAG
results/          résultats bruts par niveau et tableau
traces/           une trace JSONL par exécution
```

Répartition du travail : `GAUTIER.md`. Protocole de test : `docs/protocole.md`. Choix techniques et mesures : `docs/decisions.md`.
