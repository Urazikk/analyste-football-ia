# Journal des décisions

Chaque choix technique est consigné avec la mesure qui le justifie.

| Date | Décision | Options comparées | Mesure | Résultat |
|---|---|---|---|---|
| 2026-11-05 | Squelette du dépôt, protocole de test fixé | | | |
| 2026-11-05 | Compétitions : Euro 2024, Copa América 2024, CdM 2022 (sélections) | CdM 2022 seule, compétitions futures | aucune compétition à venir dans l'open data ; ~147 matchs donnent un historique par équipe | rapport d'avant-match sur une affiche donnée par l'utilisateur, à partir des derniers matchs disponibles |
| 2026-11-05 | LLM provisoire : Mistral Small (poids ouverts, API) | Llama 70B via Groq, Ollama 7-8B | à mesurer : niveau 2, 10 tâches, succès, pass^3, tokens, latence (`eval.py --levels 2 --types task --model ...`) | |
| 2026-11-08 | Modèle d'embeddings : multilingual-e5-small | multilingual-e5-small, bge-m3 | Recall@5 et MRR sur les 20 cas doc, dense, 600 car. (`results/retrieval.md`) | e5-small : R@5 1,00, MRR 0,89, 10 ms/req ; bge-m3 : R@5 1,00, MRR 0,85, 232 ms/req sur CPU. Aussi bon et 23 fois plus rapide |
| 2026-11-08 | Morceaux : sections, puis 600 caractères max ; ids par document et section, indépendants de la taille | 600, 1200, 2000 caractères | Recall@5 et MRR sur les 20 cas doc (e5-small, dense) | 600 : 1,00 / 0,89 ; 1200 : 0,95 / 0,80 ; 2000 : 0,90 / 0,75 |
| 2026-11-08 | Recherche dense seule (pas d'hybride) | dense, BM25, hybride RRF (k=60) | Recall@5 et MRR sur les 20 cas doc (e5-small, 600 car.) | dense 1,00 / 0,89 ; hybride 1,00 / 0,84 ; BM25 0,90 / 0,72. L'hybride n'aide pas : on garde le plus simple. Limite : 20 cas, un cas vaut 0,05 |
| 2026-11-08 | Pas de seuil d'abstention sur le score (abstention par le modèle) | seuil sur le meilleur cosinus dense | meilleur score des 20 cas doc et des 5 cas absents | e5-small : doc min 0,865, absent max 0,876, recouvrement ; bge-m3 : 0,660 contre 0,636, marge trop faible sur 5 cas. Un seuil ferait perdre des cas doc |
| 2026-11-05 | Corpus : lois du jeu IFAB (FR) téléchargées par script, non commitées (licence), + Wikipédia (CC BY-SA) | Wikipédia seul | | |
| 2026-11-07 | Corpus construit : 25 articles Wikipédia FR (un par loi « Loi N du football » + 8 sur l'arbitrage), 17 lois IFAB 2026/27 + protocole VAR, soit 43 documents et 468 morceaux (290 wiki, 178 IFAB) | | | Le PDF 2026/27 n'a pas de signets : découpage par les pages séparatrices « Loi / N », vérifié sur les 17 lois |
| | Extension niveau 3 | | défaut mesuré au niveau 2 | |
| 2026-11-07 | Jeu de test : 20 cas doc (17 lois IFAB, 1 protocole VAR, 2 Wikipédia) et 5 cas absents | | réponse attendue vérifiée dans la section citée (`tests/test_cases.py`) ; termes des cas absents introuvables dans le corpus | sources au niveau de la section pour Recall@5 et MRR |
