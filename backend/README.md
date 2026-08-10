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

- Le graphe alterne `memory` / `calc` d'un tour à l'autre (logique `route_by_family`,
  volontairement simpliste pour l'instant).
- La difficulté monte quand `error_rate` est bas et `avg_response_time` est bas,
  descend quand `error_rate > 0.4`.
- Chaque tour affiche `[format_response] exercice prêt -> ...` : c'est le dernier
  noeud du graphe qui s'exécute, la preuve que le routage conditionnel a bien
  fonctionné.

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
entre deux sessions, pas le biais du tour 1 — celui-là est laissé pour la
suite (RAG sur l'historique réel plutôt qu'un simple compteur agrégé).

## Ce qui ne bouge pas quand on ajoutera la suite

Le graphe a 6 noeuds : `load_user_profile`, `analyze_performance`,
`decide_next_action`, `generate_memory`, `generate_calc`, `format_response`.
Les phases suivantes remplacent le *contenu* de `decide_next_action`,
`generate_memory` et `generate_calc` (règles → LLM, stub → RAG) et ajoutent
des noeuds (`retrieve_context`, `validate_output`) — mais la forme générale du
graphe ne change pas. C'est le principe même de LangGraph : faire évoluer ce
qui se passe *dans* un noeud sans casser le câblage autour.
