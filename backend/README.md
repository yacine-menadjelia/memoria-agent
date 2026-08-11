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
- `validate_output` tourne après `generate_memory`/`generate_calc`, avant
  `format_response`, et referme une boucle dans le graphe : si l'exercice
  généré est invalide (division qui ne tombe pas juste pour `calc`, séquence
  avec doublons/élément vide/trop courte pour `memory`), le routage repart
  vers le noeud de génération correspondant (`route_after_validation`) au
  lieu d'avancer. `generation_attempts` (remis à zéro à chaque tour dans
  `retrieve_context`) borne la boucle : au-delà de
  `MAX_GENERATION_RETRIES` (2) tentatives, `fallback_exercise` prend le
  relais avec un exercice déterministe (`range(1, difficulty+3)` / `a+b`,
  comme au tout premier stub) — l'utilisateur ne doit jamais recevoir une
  erreur 500 parce que le LLM a raté la génération plusieurs fois de suite.
- Chaque tour affiche `[format_response] exercice prêt -> ...` : c'est le dernier
  noeud du graphe qui s'exécute, la preuve que le routage conditionnel a bien
  fonctionné.
- Nécessite `ANTHROPIC_API_KEY` et `VOYAGE_API_KEY` dans `backend/.env` (voir
  `.env.example`).

## Scénarios manuels

`scripts/manual_scenarios.py` pilote l'API en HTTP (donc `docker compose up`
doit tourner) sur quelques cas concrets : progression (réponses justes et
rapides), régression (erreurs et lenteur, jusqu'à la borne de difficulté 1),
retour d'un utilisateur connu (vérifie que `load_user_profile` reprend bien
à la bonne difficulté d'une session à l'autre), non-répétition des exercices
`calc` sur une série de tours, et les erreurs API attendues (404 sur une
session inconnue).

```bash
pip install requests
python scripts/manual_scenarios.py
# ou contre une autre URL : MEMORIA_BASE_URL=http://localhost:8000 python scripts/manual_scenarios.py
```

`scripts/scenario_fallback.py` force spécifiquement la boucle de régénération
et le fallback déterministe de `validate_output` — impossible à obtenir de
façon fiable en pilotant l'API en HTTP puisqu'on ne contrôle pas le vrai LLM.
Volontairement boîte blanche : il monkeypatch
`app.llm.calc_exercise_is_valid`/`memory_exercise_is_valid` pour simuler un
LLM qui échoue la validation, puis invoque le graphe directement (`app.llm`
et `app.agent.graph` doivent donc être importables — exécuter dans le
conteneur backend, pas depuis l'hôte) :

```bash
docker compose cp scripts/scenario_fallback.py backend:/app/scripts/scenario_fallback.py
docker compose exec backend python /app/scripts/scenario_fallback.py
docker compose exec backend rm -rf /app/scripts  # nettoyage — scripts/ n'est pas dans l'image
```

Deux scénarios : (1) le LLM rate la validation en boucle → au bout de
`MAX_GENERATION_RETRIES` (2) régénérations, `fallback_exercise` prend le
relais avec un exercice déterministe ; (2) le LLM rate une fois puis se
rattrape au tour suivant → pas de fallback, la boucle de retry suffit.

## Tests automatisés (pytest)

Contrairement aux scénarios ci-dessus, `tests/` ne dépend ni de Docker, ni
d'une clé API, ni de Postgres : chaque appel externe est mocké ou remplacé
par un double de test (`tests/fakes.py` — `FakeAnthropicClient`,
`FakeProfileStore`, `FakeExerciseHistoryStore`, `FakeKnowledgeBase`), et les
noeuds du graphe sont appelés directement comme des fonctions Python. Rapide
et déterministe, adapté à la CI.

- `tests/test_llm.py` : l'évaluateur arithmétique restreint (`_evaluate_expression`
  — y compris qu'il rejette un appel de fonction du type
  `__import__('os').system(...)`, preuve que ce n'est pas un `eval()`
  général), `_clamp_difficulty`, `_normalize_answer`, les fonctions de
  validité, et `decide_next_action`/`generate_calc_exercise`/
  `generate_memory_exercise` avec un client Anthropic mocké (le contrat —
  schema envoyé, parsing de la réponse, calcul serveur de la réponse calc —
  est vérifié sans jamais appeler la vraie API).
- `tests/test_graph_nodes.py` : chaque noeud isolément (`analyze_performance`,
  `load_user_profile` avec/sans profil, `retrieve_context` y compris sa
  résilience à une panne de `knowledge_base`, `validate_output`,
  `fallback_exercise`, les fonctions de routage), plus deux tests qui
  construisent le graphe complet (`build_graph()`) avec `app.llm` monkeypatché
  pour rejouer en hermétique les deux scénarios de
  `scripts/scenario_fallback.py`.

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -v
```

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

Le graphe a 9 noeuds : `load_user_profile`, `analyze_performance`,
`decide_next_action`, `retrieve_context`, `generate_memory`, `generate_calc`,
`validate_output`, `fallback_exercise`, `format_response`. `validate_output`
introduit la première boucle du graphe (retour vers `generate_memory`/
`generate_calc` si invalide) — c'était jusque-là un pipeline strictement
linéaire. Tous les noeuds qui prenaient des décisions ou généraient du
contenu sont passés de règles/stubs fixes à des appels LLM (`app/llm.py`) et
à de la récupération de contexte (`app/db.py`, `app/rag.py`), avec un filet
de sécurité déterministe en bout de chaîne. La forme générale ne change pas
pour autant : c'est le principe même de LangGraph, faire évoluer ce qui se
passe *dans* un noeud (et, ici, le câblage d'une boucle bornée) sans casser
le reste.
