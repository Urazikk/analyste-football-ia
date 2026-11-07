# Journal des décisions

Chaque choix technique est consigné avec la mesure qui le justifie.

| Date | Décision | Options comparées | Mesure | Résultat |
|---|---|---|---|---|
| 2026-11-05 | Squelette du dépôt, protocole de test fixé | | | |
| 2026-11-05 | Compétitions : Euro 2024, Copa América 2024, CdM 2022 (sélections) | CdM 2022 seule, compétitions futures | aucune compétition à venir dans l'open data ; ~147 matchs donnent un historique par équipe | rapport d'avant-match sur une affiche donnée par l'utilisateur, à partir des derniers matchs disponibles |
| 2026-11-05 | LLM provisoire : Mistral Small (poids ouverts, API) | Llama 70B via Groq, Ollama 7-8B | à mesurer : niveau 2, 10 tâches, succès, pass^3, tokens, latence (`eval.py --levels 2 --types task --model ...`) | |
| | Modèle d'embeddings | multilingual-e5-small, bge-m3 | Recall@5 et MRR sur les 20 cas doc | |
| 2026-11-05 | Morceaux : sections, puis 1200 caractères max (provisoire) ; ids par document et section, indépendants de la taille | 600, 1200, 2000 caractères | Recall@5 et MRR sur les 20 cas doc | |
| | Dense seul ou hybride dense + BM25 | dense, hybride | Recall@5 et MRR sur les 20 cas doc | |
| | Seuil d'abstention | | | |
| 2026-11-05 | Corpus : lois du jeu IFAB (FR) téléchargées par script, non commitées (licence), + Wikipédia (CC BY-SA) | Wikipédia seul | | |
| 2026-11-07 | Corpus construit : 25 articles Wikipédia FR (un par loi « Loi N du football » + 8 sur l'arbitrage), 17 lois IFAB 2026/27 + protocole VAR, soit 43 documents et 468 morceaux (290 wiki, 178 IFAB) | | | Le PDF 2026/27 n'a pas de signets : découpage par les pages séparatrices « Loi / N », vérifié sur les 17 lois |
| | Extension niveau 3 | | défaut mesuré au niveau 2 | |
