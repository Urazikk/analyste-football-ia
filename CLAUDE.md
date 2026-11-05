# Projet IA générative 2026 : Analyste de football

## Contexte
- Mineure IA générative (ECE), encadrant Dr. Issam Falih.
- Binôme. Date limite : 30 novembre 2026, 23h59.
- Parcours Texte, thème officiel "Analyste de football" (aucune proposition à envoyer).
- Principe du sujet : on ne juge pas le nombre de techniques, mais la capacité à montrer, mesures à l'appui, ce que chaque niveau apporte, ce qu'il coûte et où il échoue. Ne passer au niveau suivant que si une mesure montre qu'il aide.

## Thème
- Corpus RAG : lois du jeu (IFAB, vérifier la licence), Wikipédia en secours.
- Données : StatsBomb open data via `statsbombpy` (sans clé). Périmètre restreint à une ou deux compétitions (à fixer).
- Outils de l'agent : requêtes sur les événements de match, statistiques, graphiques.
- Action à valider par l'utilisateur : publier le rapport d'avant-match.

## Les 4 niveaux (tous restent disponibles dans l'interface et dans eval.py)
0. LLM seul : prompt soigné, sans documents ni outils. Référence à battre.
1. RAG : découpage, embeddings, recherche dense ou hybride dense + BM25, réponse qui cite ses sources, abstention si rien n'est trouvé.
2. Agent outillé : au moins 3 outils décrits par schéma JSON dont un qui agit, boucle bornée (étapes, tokens), erreurs d'outils renvoyées au modèle, outils classés par effet, confirmation obligatoire avant toute action irréversible, règles métier vérifiées par du code.
3. Extension : une seule technique, mesurée contre le niveau 2 (RAG avancé, multi-agents, LoRA, mémoire long terme, serveur MCP ou planification). À choisir d'après un défaut observé au niveau 2.

## Contraintes impératives
- Au moins un composant écrit sans framework : la boucle de l'agent (pas de LangGraph pour celle-ci).
- Pas de GPU requis : API ou petits modèles ouverts (ouvert conseillé).
- Aucune clé d'API dans le dépôt. Fournir `.env.example`, mettre `.env` dans `.gitignore`.
- Une seule commande `python eval.py` reproduit le tableau de résultats.
- Même protocole de test pour tous les niveaux, défini dès le début.
- Aucune donnée personnelle réelle.
- Interface Streamlit ou Gradio : réponse, sources citées, choix du niveau 0 à 3, coûts affichés.
- Trace de chaque exécution en JSONL (étapes, outils, arguments, tokens, durée) dans `traces/`.

## Évaluation
Jeu de test : `tests.jsonl`, 40 cas minimum.
- 20 réponses présentes dans les documents (réponse correcte, source citée)
- 5 réponses absentes des documents (abstention attendue)
- 10 tâches en plusieurs étapes (état final vérifié par du code)
- 5 demandes ambiguës ou hors sujet (question de précision ou refus)

Métriques par niveau : Recall@5 et MRR (recherche), exactitude (règles ou juge LLM calibré sur 20 cas annotés), fidélité aux sources, taux d'abstention, succès des tâches sur l'état final, pass^3 sur 10 tâches (les 3 essais doivent réussir), tokens par requête, latence.

Pièges à éviter : évaluer sur trois exemples choisis à la main, juger sur la forme plutôt que sur une mesure, exécuter une action sans confirmation, oublier les coûts, publier une clé d'API.

## Livrables
1. Dépôt avec README, requirements.txt, .env.example.
2. tests.jsonl, résultats bruts par niveau et traces.
3. Rapport PDF de 4 pages maximum : cas d'usage, schéma d'architecture, choix justifiés par des mesures, tableau des niveaux 0 à 3, analyse de 5 échecs, limites et coût.
4. Vidéo de 3 à 5 minutes : un cas réussi, une abstention, une tâche multi-étapes avec sa trace, une action validée.

Barème (sur 20) : système fonctionnel niveaux 0 à 2 et interface, y compris le contrôle des actions (6), évaluation (7), extension et sa mesure (4), rapport, vidéo, qualité du code (3).

## Structure du dépôt
```
README.md, requirements.txt, .env.example, .gitignore
eval.py            # python eval.py : tous les niveaux, results/table.md
tests.jsonl        # jeu de test (5 exemples, 40 cas à écrire)
docs/
  sujet.pdf
  protocole.md     # protocole de test figé
  decisions.md     # journal des choix et de leurs mesures
src/
  config.py        # .env, chemins, marqueurs [ABSTENTION] [PRECISION] [REFUS]
  result.py        # Result : sortie commune à tous les niveaux
  tracing.py       # trace JSONL par exécution dans traces/
  llm.py           # client compatible OpenAI + niveau 0
  rag.py           # niveau 1 (à faire)
  agent.py         # niveau 2, boucle écrite à la main (faite et testée)
  tools.py         # outils + schémas JSON + effet + règles métier (lecture à faire)
  metrics.py       # Recall@k, MRR, mots clés, état final, pass^k
  app.py           # interface Streamlit avec validation des actions
tests/             # pytest avec faux LLM, sans API
data/corpus/       # documents du RAG
results/           # raw_level{n}.jsonl, table.md
traces/
```

## Conventions du code
- Chaque niveau expose `answer(question) -> Result` ; eval.py et l'interface ne lisent que `Result`.
- Le modèle signale abstention, précision et refus par des marqueurs fixes, détectés par du code.
- Outils classés par effet : `read`, `compute`, `irreversible`. Un outil irréversible passe par `check` (règles métier) puis confirmation ; sans callback, l'agent renvoie `pending_action` et l'interface fait valider.
- En évaluation, chaque essai écrit dans un `STATE_DIR` temporaire ; l'état final est vérifié par `metrics.check_state`.

## Avancement
- [x] Semaine 1 : squelette, protocole, boucle de l'agent testée, niveau 0 codé
- [ ] Semaine 1 : décisions techniques, corpus, 40 cas de test, premières mesures du niveau 0
- [ ] Semaine 2 : RAG
- [ ] Semaine 3 : outils StatsBomb, pass^3
- [ ] Semaine 4 : extension, rapport, vidéo

## Planning
- Semaine 1 (2 au 8 nov.) : thème, corpus, jeu de test, niveau 0, protocole de test.
- Semaine 2 (9 au 15 nov.) : RAG, sources citées, abstention.
- Semaine 3 (16 au 22 nov.) : agent, confirmation des actions, traces, pass^3.
- Semaine 4 (23 au 30 nov.) : extension, analyse des échecs, rapport, vidéo.

## Décisions à fixer (à compléter)
- Compétition(s) StatsBomb retenue(s) : 
- Modèle LLM (API ou modèle ouvert via Ollama) : 
- Modèle d'embeddings : 
- Extension niveau 3 : 
- Répartition du travail entre les deux membres : 

## Conventions de travail
- Python 3.11 ou plus, environnement virtuel `.venv`.
- Réponses et commentaires courts, code simple et lisible, type hints, tests avec pytest.
- Tout choix technique doit être justifié par une mesure consignée.
- Fixer les graines aléatoires pour la reproductibilité.
