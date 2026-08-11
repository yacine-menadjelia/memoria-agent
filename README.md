# memoria-agent

Agent d'entraînement cognitif (mémoire + calcul mental) dont la difficulté
s'adapte à l'utilisateur. Backend FastAPI/LangGraph avec RAG, app mobile
Flutter (Android). Projet portfolio, construit pour illustrer une chaîne
complète : agent LLM avec boucles de contrôle, RAG hybride, guardrails
déterministes, et un client mobile de bout en bout.

```
backend/   FastAPI + LangGraph + Postgres/pgvector — voir backend/README.md
mobile/    App Flutter (Android) — voir mobile/README.md
infra/
docker-compose.yml
```

## Lancer le projet

```bash
docker compose up          # backend + Postgres/pgvector
cd mobile && flutter run   # app mobile (nécessite adb reverse tcp:8000 tcp:8000)
```

Détails, variables d'environnement et tests dans `backend/README.md` et
`mobile/README.md`.

## Architecture du backend

Le cœur est un graphe LangGraph à 9 nœuds :

```
load_user_profile → analyze_performance → decide_next_action → retrieve_context
  → generate_memory / generate_calc → validate_output → format_response
                                            ↑___________________|
                                    (retry borné, ou fallback_exercise)
```

- **`load_user_profile`** atténue le cold-start : un utilisateur connu
  reprend à sa dernière difficulté (table `user_profiles`) au lieu de
  repartir à 3.
- **`decide_next_action`** choisit la difficulté et la famille d'exercice
  via un appel LLM (Claude Haiku 4.5, sortie structurée) à partir de
  l'historique récent.
- **`generate_memory` / `generate_calc`** génèrent le contenu de
  l'exercice via LLM. Pour `calc`, le serveur ne fait jamais confiance au
  résultat renvoyé par le modèle : l'expression est réévaluée côté serveur
  par un évaluateur arithmétique restreint (AST limité à `+ - * / ()`,
  jamais un `eval()` général).
- **RAG hybride** (`retrieve_context`), deux sources volontairement
  séparées :
  - SQL structuré (`app/db.py`) pour l'historique récent et les stats
    d'erreurs — pas d'embeddings, ces données sont déjà structurées.
  - Recherche vectorielle réelle (Voyage AI + pgvector, `app/rag.py`)
    uniquement pour les repères pédagogiques. Résiliente : si Voyage AI
    est indisponible, le tour continue sans les repères plutôt que
    d'échouer.
- **`validate_output`** ferme une boucle bornée (`MAX_GENERATION_RETRIES`)
  : un exercice invalide déclenche une régénération ; au-delà de la borne,
  `fallback_exercise` fournit un exercice déterministe — l'utilisateur ne
  doit jamais recevoir une erreur 500 parce que le LLM a raté plusieurs
  fois de suite.

Tests : suite pytest (nœuds isolés + graphe complet) avec doubles de test
plutôt que des mocks, aucune dépendance à Docker/Postgres/clé API. Détails
dans `backend/README.md`.

## App mobile

Flutter, Riverpod (`AsyncNotifier`, sans génération de code) pour l'état,
`shared_preferences` pour un `user_id` persistant côté client. Consomme les
trois endpoints du backend (`/sessions/start`, `/sessions/{id}/answer`,
`/sessions/{id}`), auto-correction côté client (le backend ne valide pas
les réponses). Validée sur émulateur (AVD, API 35) et sur un appareil
Android physique via `adb reverse tcp:8000 tcp:8000`. Détails et choix
d'architecture dans `mobile/README.md`.

## Optimisation de latence

L'app était initialement lente (~10,4s par tour). Diagnostic par mesures
directes (curl, timing instrumenté) plutôt que par supposition :

- Le goulot n'était pas Voyage AI (retries réseau) mais les deux appels
  LLM séquentiels du tour (décision + génération), sur Claude Opus 5
  (~5-6s par appel).
- Bascule vers **Claude Haiku 4.5** (~2s par appel) : ces appels sont des
  tâches simples (classification de difficulté, génération d'une
  expression/séquence courte), pas du raisonnement à payer à chaque tour.
- Suppression d'un champ `reasoning` inutilisé dans le schema de sortie —
  personne ne le lisait, et le faire rédiger coûtait des tokens de
  génération pour rien.
- Cache en mémoire des embeddings de requête par `(family, difficulty)`
  dans `KnowledgeBaseStore` — seulement 20 combinaisons possibles, pas la
  peine de rappeler Voyage AI à chaque tour pour la même combinaison.

Résultat mesuré : **~10,4s → ~2,4-2,6s** par tour (~4x plus rapide).
