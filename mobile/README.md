# memoria_mobile

App Flutter (Android) qui consomme l'API du backend (`../backend`) :
`POST /sessions/start`, `POST /sessions/{id}/answer`, `GET /sessions/{id}`.
Deux familles d'exercices générées par le backend (memory / calc), la
difficulté s'adapte automatiquement selon les réponses.

## Architecture

```
lib/
  main.dart                        ProviderScope + MaterialApp
  src/
    models/                        SessionState, Exercise, HistoryEntry
                                    (fromJson manuels, miroir du contrat
                                    JSON du backend — voir backend/app/main.py)
    services/
      api_client.dart              Les 3 appels HTTP
      user_identity_store.dart     user_id persistant (shared_preferences)
    providers/
      providers.dart                SessionController (AsyncNotifier Riverpod)
    screens/
      start_screen.dart            Identifiant + démarrage de session
      exercise_screen.dart         Boucle de jeu
    widgets/
      calc_exercise_view.dart      Saisie + auto-correction (answer serveur)
      memory_exercise_view.dart    Mémorisation puis rappel, auto-corrigé
      session_header.dart          Difficulté / famille / historique récent
```

**Gestion d'état : Riverpod** (`flutter_riverpod`, sans code génération).
Choisi plutôt que Provider (moins de cérémonie mais moins strict côté
compile-safety) ou Bloc (plus de boilerplate pour ce périmètre) : Riverpod
donne un typage fort pour la DI (`Provider<ApiClient>`) et un support
`AsyncValue`/`AsyncNotifier` qui colle naturellement au flux de l'app
(chaque interaction — démarrer, répondre — est un appel réseau avec un
état loading/data/error explicite). Pas de génération de code
(`riverpod_generator`/`freezed`) pour garder le build simple et fiable —
un choix pragmatique pour ce périmètre, pas un désaveu de ces outils.

**`user_id` persistant.** Le backend distingue `user_id` (persistant,
alimente `load_user_profile` côté serveur pour la reprise de difficulté
entre sessions) de `session_id` (éphémère, un par partie) — voir
`backend/README.md`. L'app génère un UUID au premier lancement et le
persiste via `shared_preferences`, pour bénéficier de cette continuité
sans écran de compte.

**`response_time` mesuré côté client.** Pour `calc`, c'est le temps entre
l'affichage de l'exercice et la validation. Pour `memory`, le chronomètre
ne démarre qu'au passage en phase de rappel (`markInteractionStart()`) —
le temps de mémorisation, à durée choisie par l'utilisateur, ne doit pas
gonfler artificiellement la mesure et fausser l'adaptation de difficulté
côté backend.

**Auto-correction côté client.** Le backend ne valide pas les réponses
(`/answer` prend juste `correct: bool`) : pour `calc`, l'app compare la
saisie à `exercise.answer` (calculé côté serveur, jamais par le LLM —
voir `backend/README.md`) ; pour `memory`, elle compare la séquence
ressaisie à celle affichée pendant la phase de mémorisation.

## Lancer

Backend requis (`docker compose up` depuis la racine du repo). L'app
cible toujours `http://localhost:8000` (voir `ApiClient`) ; sur Android
(émulateur ou appareil physique en USB), il faut rediriger ce port vers
le backend de l'hôte :

```bash
adb reverse tcp:8000 tcp:8000
```

Un seul mécanisme réseau à retenir pour les deux cas, plutôt que des cas
spéciaux par plateforme (`10.0.2.2` pour l'émulateur, IP LAN pour un
appareil physique...). Pour un appareil physique : activer le débogage
USB dans les options développeur, puis accepter la popup d'autorisation
sur le téléphone au premier branchement (si `adb devices` affiche
`unauthorized` sans popup visible, `adb kill-server && adb start-server`
force un nouveau handshake qui la déclenche).

```bash
flutter pub get
flutter run          # sur un émulateur ou un appareil connecté
flutter test         # tests widget
flutter analyze
```
