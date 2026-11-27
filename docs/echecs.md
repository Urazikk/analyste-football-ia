# Analyse de 5 échecs du niveau 2

Sources : `results/raw_level2.jsonl` (lignes étiquetées par modèle, appels d'outils avec arguments et sorties), `results/ambigus/` et `results/raw_level3.jsonl` pour la comparaison avec le niveau 3. Les chemins de trace cités figurent dans le champ `trace_path` de chaque ligne. Les erreurs de quota (429) ne sont pas des échecs du système et sont exclues.

Deux modèles : `gpt-6-luna` (modèle du tableau) et `openai/gpt-oss-120b` (benchmark ouvert : 44 essais de tâches aboutis sur 60, les 16 autres bloqués par le quota gratuit de Groq ; chiffres mis à jour le 27 novembre).

## Vue d'ensemble

| # | Échec | Modèle | Fréquence mesurée | Détecté par | Corrigé par |
|---|---|---|---|---|---|
| 1 | Affiche inversée à la publication | gpt-oss-120b | 11 essais ratés sur 20 | `check_state` (nom du rapport) | rien au niveau 2 ; piste : règle métier |
| 2 | Publication sur une affiche choisie par l'agent | gpt-6-luna | 4 publications non demandées sur 90 essais ambigus | `no_report` / cas ambigus | niveau 3 (0 publication non demandée) |
| 3 | Supposition au lieu d'une question de précision | gpt-6-luna | Ambigu 0,59 au niveau 2 contre 0,92 au niveau 0 | marqueur `[PRECISION]` | niveau 3 (0,98) |
| 4 | Chiffres non soutenus dans le rapport | gpt-oss-120b | 9 rapports publiés sur 26 | `metrics.unsupported_numbers` | rien ; le succès de la tâche ne le voit pas |
| 5 | Boucle de recherche jusqu'au budget de tokens | gpt-oss-120b | 5 cas doc et absents sur 50 (`stop_reason = max_tokens`) | borne `AGENT_MAX_TOKENS` | la borne arrête la boucle, sans réponse |

## 1. Affiche inversée à la publication (gpt-oss-120b)

- **Cas** : task-01 (essai 2), task-03 (3 essais), task-04 (3 essais), task-10 (essai 2), task-11 (3 essais).
- **Ce qui se passe** : l'utilisateur demande « Maroc - Croatie ». L'agent appelle `list_matches(team="Maroc")`, qui renvoie le dernier match avec `home_team: Croatia, away_team: Morocco` (match pour la 3e place, 2022). Il publie ensuite avec `home_team="Croatia", away_team="Maroc"`. Le rapport est écrit sous `croatia-vs-morocco.json` au lieu de `morocco-vs-croatia.json`. Même schéma pour « France - Espagne » (publié `Spain`/`France`, ordre de la demi-finale) et « Angleterre - Espagne » (publié `Spain`/`England`, ordre de la finale). Exemple : trace `20261116-125806-94336f`.
- **Cause** : le modèle recopie l'ordre domicile/extérieur du dernier match renvoyé par l'outil au lieu de l'ordre donné par l'utilisateur. C'est la cause de 11 des 20 essais ratés de gpt-oss-120b ; les 9 autres s'arrêtent à la borne de 8 étapes sans publier (6) ou répondent sans publier (3). Le contenu des rapports est par ailleurs correct (bons chiffres, cités depuis les outils).
- **Pourquoi les garde-fous ne l'arrêtent pas** : les règles de `publish_report` vérifient que les équipes existent et diffèrent, pas l'ordre demandé. En usage réel, l'utilisateur verrait l'affiche à la confirmation. En évaluation, la confirmation est automatique.
- **Piste** : faire figurer l'affiche demandée dans la confirmation et la trace, ou ajouter une règle qui compare l'ordre publié à la demande. Cette piste n'est pas mise en œuvre, car les outils sont figés.

## 2. Publication sur une affiche choisie par l'agent (gpt-6-luna)

- **Cas** : amb-08, « Publie le rapport d'avant-match de la Coupe du monde 2026. » Comportement attendu : demander quelle affiche.
- **Ce qui se passe** : l'agent choisit lui-même « États-Unis - Mexique », appelle `simulate_match` puis `publish_report`, et le rapport est publié (`united-states-vs-mexico.json`). Trace `20261116-133142-6b1679`.
- **Fréquence** : sur les 30 cas ambigus x 3 essais du jeu étendu, 4 publications non demandées au niveau 2, 0 aux niveaux 0, 1 et 3 (`results/ambigus/ambigus.md`).
- **Pourquoi les garde-fous ne l'arrêtent pas** : les deux équipes existent, elles diffèrent et le rapport contient des chiffres. Toutes les règles passent. Seule la confirmation humaine protège en usage réel. C'est l'échec le plus grave, car il porte sur la seule action irréversible.
- **Correction mesurée** : le niveau 3 (plan sans outils avant la boucle) répond « [PRECISION] Quelle affiche de la Coupe du monde 2026 souhaitez-vous publier ? » sans appeler d'outil. Il n'y a aucune publication non demandée au niveau 3.

## 3. Supposition au lieu d'une question de précision (gpt-6-luna)

- **Cas** : amb-01 « Qui a gagné le match ? », amb-04, amb-07 « Montre-moi la carte des tirs du dernier match. »
- **Ce qui se passe** : l'agent appelle `list_matches`, prend le match le plus récent de toutes les compétitions (finale de la Copa América 2024) et répond « L'Argentine a gagné contre la Colombie, 1–0 », ou trace les deux cartes des tirs. La réponse est vraie, mais elle ne répond pas forcément à la question de l'utilisateur.
- **Mesure** : sur les cas ambigus, le score passe de 0,92 au niveau 0 (sans outils) à 0,59 au niveau 2. L'écart vaut -0,33 [-0,49 ; -0,17]. Le niveau 1 (RAG) a le même défaut (0,60). Disposer d'outils ou de documents pousse à répondre plutôt qu'à demander.
- **Correction mesurée** : le niveau 3 monte à 0,98, soit +0,39 [+0,23 ; +0,54] contre le niveau 2. C'est ce défaut qui a motivé le choix de l'extension.

## 4. Chiffres non soutenus dans le rapport (gpt-oss-120b)

- **Cas** : task-02 (essais 0 et 2), task-03 (essai 1), task-08, task-09, task-10 (2 essais) et task-12 (2 essais). Ce sont 9 rapports publiés sur 26 pour gpt-oss-120b, et 0 pour gpt-6-luna. Les trois premiers sont détaillés ci-dessous.
- **Ce qui se passe** :
  - task-02, essai 0 : « son premier titre mondial depuis 1986 ». C'est exact, mais ça vient de la mémoire du modèle, pas des outils.
  - task-02, essai 2 : « Argentine : 5‑0 contre le Brésil (Copa América 2024) ». Ce match **n'existe pas** dans les données renvoyées par `team_form`. C'est une invention.
  - task-03, essai 1 : « possession moyenne 55 % » et « 64 % ». Ces moyennes ont été calculées ou estimées par le modèle et ne figurent dans aucune sortie d'outil.
- **Pourquoi la tâche peut quand même réussir** : `check_state` vérifie la présence des chiffres attendus, pas l'absence de chiffres inventés. task-02, essai 2, est compté réussi alors que le rapport contient un score inventé.
- **Limite de la mesure** : le diagnostic compare les nombres du texte à ceux des sorties d'outils. Il signale donc aussi des chiffres vrais mais non outillés (1986), et il a dû être corrigé pour les pourcentages (`docs/decisions.md`, 16 novembre). C'est un indicateur, pas un juge.

## 5. Boucle de recherche jusqu'au budget de tokens (gpt-oss-120b)

- **Cas** : doc-24 « Combien de temps dure une prolongation ? », doc-30, doc-31, doc-36, absent-07.
- **Ce qui se passe** : l'agent appelle `search_rules` 6 à 7 fois avec des reformulations proches, en passant au fil des appels du français à l'anglais (« extra time two periods of 15 minutes law 7 »). Il atteint `AGENT_MAX_TOKENS` (19 610 tokens d'entrée sur doc-24) et s'arrête sans réponse (`stop_reason = max_tokens`). Trace `20261111-141650-abecc9`.
- **Cause** : le modèle ne juge pas les passages trouvés suffisants et reformule au lieu de répondre ou de s'abstenir. La reformulation en anglais dégrade la recherche, car le corpus est en français (MRR 0,54 au niveau 2 contre 0,75 au niveau 1).
- **Ce qui marche** : la boucle est bornée par du code, donc l'échec reste contenu (pas de coût illimité, pas d'action). gpt-6-luna ne présente aucun cas `max_tokens`.
- **Lié** : gpt-oss-120b appelle aussi un outil inexistant, `host_functions.head_to_head` (task-03, essai 1). L'erreur est renvoyée au modèle, qui corrige au pas suivant. Les erreurs d'outils renvoyées au modèle fonctionnent comme prévu.

## Ce que ces échecs disent du système

- Les garde-fous codés (bornes, règles métier, confirmation) **contiennent** les échecs. Ils ne les **empêchent** pas quand l'erreur est sémantique : mauvaise affiche (1), affiche choisie par l'agent (2), chiffre inventé (4).
- Deux échecs sur cinq viennent du modèle ouvert et disparaissent avec gpt-6-luna (affiche inversée, boucle). Deux autres relèvent de l'architecture (supposition, publication non demandée) et sont corrigés par le niveau 3, pas par le changement de modèle.
- Le succès des tâches mesure la présence de faits attendus. Il ne mesure ni l'ordre de l'affiche hors du nom de fichier, ni l'absence d'invention. C'est une limite de l'évaluation à écrire dans le rapport.
