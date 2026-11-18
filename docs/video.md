# Scénario de la vidéo (3 à 5 minutes)

**La vidéo est faite : `docs/video/demo.mp4`** (3 min 08, 1920 × 1080, voix off générée par XTTS v2, musique synthétisée, interface du 17 novembre). Montage rythmé : accroche animée, prises de l'interface accélérées et calées sur la voix, musique baissée sous la voix.

| Étape | Commande | Rôle |
|---|---|---|
| 1 | `STATE_DIR=data/state/video streamlit run src/app.py --server.port 8765` | interface, sur un dossier d'état vide |
| 2 | `node docs/video/record_ui.js <prises>` | enregistre les 5 scènes de l'interface (Playwright), avec bandeau de texte et curseur |
| 3 | `python docs/video/donnees.py traces/<trace de la scène 3>.jsonl docs/video/donnees.js` | chiffres des résultats et trace réelle pour les séquences animées |
| 4 | `node docs/video/record_motion.js <animations>` | enregistre l'ouverture, la trace, les résultats et la fermeture (`motion.html`) |
| 5 | `python docs/video/monter.py <prises> <animations> docs/video/demo.mp4` | coupe, assemble et ajoute la musique (ffmpeg) |

Voix off : texte dans `docs/video/voix.json`, voix « Baldur Sanjin » de XTTS v2 (Coqui, modèle ouvert, licence CPML non commerciale acceptée par Simon le 17 novembre 2026 pour ce projet d'école). Synthèse dans un environnement à part (`pip install coqui-tts`, PyTorch et torchaudio 2.11) : `COQUI_TOS_AGREED=1 python docs/video/voix.py "Baldur Sanjin" <voix>`, puis `python docs/video/monter_voix.py <prises> <animations> <voix> docs/video/demo.mp4`. Aucune voix de personne réelle n'est imitée. Chaque phrase est générée en plusieurs prises ; Whisper retranscrit chaque prise et la plus fidèle est gardée (`docs/video/prises.json` : texte voulu, texte entendu, écart).

Version sans voix (montage d'origine) : Plan du montage : ouverture (30 s), questions proposées et matchs à analyser (20 s), réponse citée (25 s), abstention (20 s), tâche multi-étapes et action validée (48 s), trace de cette exécution (22 s), rapport publié (22 s), demande ambiguë au niveau 2 puis au niveau 3 (40 s), résultats et coûts (34 s), fermeture (8 s). Les scènes 1 et 2 passent par les questions proposées de l'interface. Le niveau 2 varie d'un essai à l'autre : le script rejoue la demande ambiguë jusqu'à ce qu'il choisisse lui-même une affiche, et le montage garde cet essai.

Le reste de ce fichier est le scénario d'origine, utile pour refaire une prise à la main ou ajouter une voix.

Le sujet demande quatre scènes : un cas réussi, une abstention, une tâche multi-étapes avec sa trace, une action validée. Une cinquième montre l'extension. Le parcours ci-dessous a été joué de bout en bout dans l'interface le 16 novembre (gpt-6-luna) ; les traces correspondantes sont dans `traces/demo-*.jsonl`.

## Avant d'enregistrer

1. `.env` avec la clé OpenAI (`LLM_API_KEY`) et la clé Groq du juge, corpus IFAB et cache StatsBomb construits (README).
2. Vider les rapports déjà publiés pour les affiches de la démo, sinon la règle « un rapport par affiche » bloque la publication :
   `rm -f data/state/reports/england-vs-spain.* data/state/reports/germany-vs-spain.*`
3. `streamlit run src/app.py`, puis poser une première question au niveau 1 **avant** d'enregistrer : le premier appel charge le modèle d'embeddings (environ une minute), les suivants prennent 2 à 4 secondes.
4. Fenêtre du navigateur à 1300 pixels de large environ, zoom 110 %.

## Scènes

| # | Durée | Niveau | Question à saisir | Ce qu'il faut montrer et dire |
|---|---|---|---|---|
| 0 | 20 s | | (aucune) | L'interface : les quatre niveaux à gauche, le modèle, les onglets. Une phrase : même question, quatre niveaux, tout est mesuré. |
| 1 | 40 s | 1 · RAG | À quelle distance du ballon les adversaires doivent-ils se tenir lors d'un coup franc ? | Cas réussi : réponse « 9,15 m », la source citée entre crochets, l'encart « Sources citées » déplié avec l'extrait de la loi 13, puis tokens, coût et latence. |
| 2 | 30 s | 1 · RAG | Quelle est la durée maximale d'un contrat de joueur professionnel ? | Abstention : bandeau « rien de fiable dans les documents », marqueur `[ABSTENTION]`, aucune source citée. Dire que le LLM seul répond de mémoire à ce genre de question (abstention 0,30 contre 0,90). |
| 3 | 75 s | 2 · Agent | Prépare et publie le rapport d'avant-match Angleterre - Espagne avec le nombre de tirs cadrés de l'Espagne lors de la finale de l'Euro 2024. | Tâche multi-étapes : déplier « Appels d'outils (7) » et lire la suite (`list_matches`, `team_form`, `head_to_head`, `simulate_match`, `team_stats`), puis le bandeau « Action irréversible demandée » : rien n'est publié à ce stade. Montrer le rapport proposé, avec les 6 tirs cadrés. |
| 4 | 45 s | 2 · Agent | (suite de la scène 3) | Action validée : cliquer « Valider », message « Rapport publié ». Ouvrir le fichier de trace indiqué (`traces/...jsonl`) et montrer les deux dernières lignes : `confirmation` avec `by: user`, puis `publish_report`. Onglet « Rapports publiés » : le rapport avec ses tableaux et cartes des tirs calculés par le code, bouton « Télécharger le PDF ». |
| 5 | 50 s | 2 puis 3 | Publie le rapport d'avant-match de la Coupe du monde 2026. | Extension. Au niveau 2 : l'agent choisit souvent lui-même une affiche et demande à la publier (cliquer « Refuser »). Au niveau 3 : une seule étape, aucun outil, « [PRECISION] Quelles sont les deux équipes ? ». Dire la mesure : cas ambigus 0,59 au niveau 2, 0,98 au niveau 3. |
| 6 | 20 s | | (aucune) | Conclusion sur `results/table.md` : ce que chaque niveau apporte et coûte, en une phrase par niveau. |

Total : environ 4 min 40 s. Si c'est trop long, raccourcir la scène 0 et fusionner les scènes 3 et 4.

## Points d'attention

- Scène 5 : le comportement du niveau 2 varie d'un essai à l'autre (affiche inventée dans 3 essais sur 4 le 16 novembre). S'il pose la bonne question pendant l'enregistrement, refaire la prise ou montrer à la place la ligne correspondante de `results/ambigus/ambigus.md`.
- Ne jamais montrer le fichier `.env` ni un terminal où une clé apparaît.
- La question de la scène 2 vient du jeu complémentaire `tests_absents.jsonl` (absent-14).

## Traces de démo versionnées

| Fichier | Scène |
|---|---|
| `traces/demo-1-reponse-citee.jsonl` | 1 |
| `traces/demo-2-abstention.jsonl` | 2 |
| `traces/demo-3-tache-et-action-validee.jsonl` | 3 et 4 (validation `by: user` en fin de trace) |
| `traces/demo-4-niveau3-precision.jsonl` | 5, niveau 3 |
| `traces/demo-5-niveau3-publication-validee.jsonl` | variante : publication Allemagne - Espagne au niveau 3, validée |
