# Étape 1 — squelette du StateGraph

Objectif de cette étape : comprendre `add_node` / `add_conditional_edges` avant
d'ajouter LLM, RAG, DB ou Docker. Pas de dépendance externe autre que
`langgraph`.

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Lancer

```bash
python test_run.py
```

## Ce que tu dois observer

- Le choix de la difficulté et de la famille d'exercice (`decide_next_action`)
  est fait par un appel LLM (Claude Opus 5, sortie structurée via
  `output_config.format`, thinking désactivé + effort `low` — c'est une
  décision simple, pas la peine de payer du raisonnement étendu à chaque tour).
  `route_by_family` route ensuite vers `generate_memory` ou `generate_calc`
  selon ce que le LLM a choisi — il n'alterne plus mécaniquement : le modèle
  peut décider de rester sur la même famille si l'historique montre qu'elle
  pose problème.
- `generate_memory` et `generate_calc` génèrent aussi l'exercice via LLM
  plutôt qu'une formule fixe (`range(1, difficulty+3)` / `a+b`) : le contenu
  et sa complexité varient avec la difficulté (ex. `14 * 6` à difficulté 4,
  `(48 * 7 - 156) / 12` à difficulté 7). Pour `calc`, le serveur ne fait
  jamais confiance au résultat renvoyé par le modèle : seule l'expression
  (`content`) vient du LLM, la réponse (`answer`) est recalculée côté serveur
  par un évaluateur arithmétique restreint (`app/llm.py::_evaluate_expression`,
  AST limité à `+ - * / ()`, jamais un `eval()` général sur du texte LLM).
- `retrieve_context` (entre `decide_next_action` et le routage vers
  `generate_memory`/`generate_calc`) alimente la génération avec deux sources,
  volontairement séparées selon leur nature :
  - **historique structuré** (`app/db.py::ExerciseHistoryStore`, simple SQL sur
    la table `exercise_history`) : derniers exercices de l'utilisateur sur
    cette famille (pour ne pas reproposer le même contenu) et statistiques
    d'erreurs par difficulté (points faibles). Pas d'embeddings ici — ces
    données sont déjà structurées, une requête directe suffit.
  - **recherche vectorielle** (`app/rag.py`, Voyage AI + pgvector, table
    `knowledge_base`) : uniquement pour retrouver des repères pédagogiques
    (chunking, décomposition en calcul mental, etc.) pertinents pour la
    famille/difficulté en cours. C'est la seule partie qui a vraiment besoin
    de similarité sémantique.
  - Si Voyage AI est indisponible (ex. rate limit sur un compte sans moyen de
    paiement), `retrieve_context` continue sans les repères pédagogiques
    plutôt que de faire échouer le tour — voir le `try/except` dans
    `make_retrieve_context`. L'historique structuré, lui, reste une dépendance
    dure (pas de fallback : une erreur Postgres doit remonter).
- Chaque tour affiche `[format_response] exercice prêt -> ...` : c'est le dernier
  noeud du graphe qui s'exécute, la preuve que le routage conditionnel a bien
  fonctionné.
- Nécessite `ANTHROPIC_API_KEY` et `VOYAGE_API_KEY` dans `backend/.env` (voir
  `.env.example`).

## Point à noter (pas un bug, un sujet de discussion en entretien)

Au tour 1 d'une session, `history` est vide donc `error_rate` et
`avg_response_time` valent 0.0 par défaut dans `analyze_performance` — ce qui
fait *monter* la difficulté d'un cran, comme si l'utilisateur avait bien
performé. C'est le "cold start problem" : sans historique, l'agent n'a aucune
base pour décider.

`load_user_profile` (premier noeud du graphe) atténue ça au niveau
inter-session : `current_difficulty` repart de la dernière difficulté connue
de l'utilisateur (table Postgres `user_profiles`, clé `user_id` — distinct du
`session_id`, qui lui reste éphémère et sert de `thread_id` LangGraph) plutôt
que d'une constante à 3. Le bump du tour 1 lui-même reste inchangé : un
utilisateur qui reprend à 7 se retrouve à 8, exactement comme un nouvel
utilisateur part de 3 puis 4. Ce que ça corrige, c'est la perte de progression
entre deux sessions, pas le biais du tour 1 — celui-là dépend maintenant de
`retrieve_context` (voir ci-dessus), qui a de l'historique réel dès le
deuxième tour d'une session donnée mais rien au tout premier tour.

## Ce qui ne bouge pas quand on ajoutera la suite

Le graphe a 7 noeuds : `load_user_profile`, `analyze_performance`,
`decide_next_action`, `retrieve_context`, `generate_memory`, `generate_calc`,
`format_response`. Tous les noeuds qui prenaient des décisions ou généraient
du contenu sont passés de règles/stubs fixes à des appels LLM (`app/llm.py`)
et à de la récupération de contexte (`app/db.py`, `app/rag.py`). Ce qui reste
pour aller plus loin : un noeud `validate_output` (vérifier que l'exercice
généré est cohérent avant de le renvoyer) — mais la forme générale du graphe
ne change pas. C'est le principe même de LangGraph : faire évoluer ce qui se
passe *dans* un noeud sans casser le câblage autour.
