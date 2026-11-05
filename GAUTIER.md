# Partie de Gautier : données StatsBomb, outils de l'agent, tâches multi-étapes

Rendu final le 30 novembre, 23h59. Ta partie compte pour le niveau 2 (agent), noté avec l'interface et le contrôle des actions (6 points), et pour les tâches de l'évaluation (pass^3).

Répartition :
- **Simon** : corpus, RAG (niveau 1), 20 cas « doc » et 5 cas « absent », choix des embeddings.
- **Gautier** : tout ce qui suit.
- **À deux** : extension (niveau 3), analyse des 5 échecs, rapport, vidéo.

## 0. Installation (une fois)

```bash
git clone https://github.com/Urazikk/analyste-football-ia.git
cd analyste-football-ia
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # mettre la clé Mistral
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

## Contexte déjà décidé

- Compétitions dans `src/config.py` (`COMPETITIONS`) : Euro 2024 `(55, 282)`, Copa América 2024 `(223, 282)`, CdM 2022 `(43, 106)`. Des sélections nationales.
- Aucune compétition future n'est dans les données ouvertes. Le rapport d'avant-match porte donc sur une **affiche donnée par l'utilisateur** (« France - Espagne ») et s'appuie sur les **derniers matchs disponibles** des deux équipes.
- `publish_report(home_team, away_team, title, content)` est déjà écrit. Il crée `STATE_DIR/reports/<domicile>-vs-<exterieur>.json` (ex. `france-vs-spain.json`). C'est le seul outil irréversible : la boucle demande une confirmation avant de l'exécuter.
- StatsBomb nomme les équipes en anglais (`Spain`, `Germany`). L'utilisateur écrit en français : il faut normaliser.

## 1. Couche de données StatsBomb (`src/data.py`, à créer)

- Charger matchs et événements via `statsbombpy` (`sb.matches`, `sb.events`), sans clé.
- Mettre en cache sur disque dans `data/cache/` (déjà ignoré par git) : un fichier par match. Deuxième appel sans réseau.
- `resolve_team(name) -> str` : nom français ou anglais vers le nom StatsBomb (« Espagne » vers `Spain`). Erreur claire si l'équipe n'existe pas, avec des suggestions.
- Script `scripts/fetch_statsbomb.py` qui remplit le cache pour les 3 compétitions.

Fini quand : le cache se remplit, `resolve_team` est testé, rien n'est téléchargé deux fois.

## 2. Les 4 outils de lecture et de calcul (`src/tools.py`)

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

## 3. Règles métier de `publish_report` (`check_publish_report`)

Déjà fait : rapport unique par affiche, contenu de 200 caractères minimum. À ajouter, vérifié par du code :
- les deux équipes existent dans les données et sont différentes ;
- le rapport cite au moins un chiffre ;
- (bonus) chaque chiffre cité apparaît dans un résultat d'outil de l'exécution en cours : c'est une vraie mesure de fidélité.

Fini quand : un test pytest par règle.

## 4. Interface (`src/app.py`)

- Afficher l'image quand `plot_shots` a été appelé.
- Vérifier le parcours de validation : bouton Valider, rapport publié, trace visible. Il servira pour la vidéo.

## 5. Jeu de test : 10 tâches et 5 cas ambigus (`tests.jsonl`)

Format dans `docs/protocole.md`, exemples `task-01`, `amb-01`, `amb-02` déjà présents.
- **10 tâches multi-étapes**, l'état final vérifié par `metrics.check_state`. Varier : rapport simple, rapport avec un chiffre précis (`must_contain`), équipe écrite en français, équipe inexistante (attendu : `no_report`), demande d'analyse **sans** demande de publication (attendu : `no_report`).
- **5 cas ambigus ou hors sujet** : `clarify` (« le dernier match », sans équipe) ou `refuse` (hors football).
- Vérifier les réponses attendues à la main dans les données, avant de lancer le modèle.

## 6. Mesures

```bash
python eval.py --levels 2 --types task           # succès et pass^3 sur 3 essais
python eval.py --levels 2 --types task --model <autre> --base-url <autre url>
```

- Benchmark LLM au niveau 2 : Mistral Small, Llama 70B via Groq, un modèle Ollama. Succès, pass^3, tokens, latence dans `docs/decisions.md`.
- Noter les échecs observés (outil mal appelé, boucle qui tourne, chiffre inventé) : ils servent à choisir l'extension du niveau 3.

## Calendrier

| Quand | Quoi |
|---|---|
| semaine 1 (jusqu'au 8 nov.) | installation, couche de données et cache, 10 tâches et 5 cas ambigus écrits |
| semaine 2 (9 au 15 nov.) | 4 outils et leurs tests, règles métier |
| semaine 3 (16 au 22 nov.) | interface, pass^3, benchmark LLM, liste des échecs |
| semaine 4 (23 au 30 nov.) | extension, rapport, vidéo (avec Simon) |
