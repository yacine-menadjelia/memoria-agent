import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/session_state.dart';
import '../services/api_client.dart';
import '../services/user_identity_store.dart';

final apiClientProvider = Provider<ApiClient>((ref) => ApiClient());

final userIdentityStoreProvider = Provider<UserIdentityStore>(
  (ref) => UserIdentityStore(),
);

final userIdProvider = FutureProvider<String>((ref) {
  return ref.watch(userIdentityStoreProvider).loadOrCreate();
});

/// Pilote le cycle de vie d'une session côté client : démarrage, envoi
/// de réponse, mesure du temps de réponse. `state == AsyncData(null)`
/// signifie "pas de session en cours" (écran de démarrage).
class SessionController extends AsyncNotifier<SessionState?> {
  DateTime? _interactionStartedAt;

  @override
  Future<SessionState?> build() async => null;

  Future<void> start(String userId) async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      final session = await ref.read(apiClientProvider).startSession(userId);
      _interactionStartedAt = DateTime.now();
      return session;
    });
  }

  Future<void> answer({required bool correct}) async {
    final current = state.value;
    if (current == null) return;

    final responseTime = _elapsedSinceInteractionStart().inMilliseconds / 1000.0;
    state = const AsyncLoading();
    state = await AsyncValue.guard(() async {
      final session = await ref.read(apiClientProvider).submitAnswer(
            current.sessionId,
            correct: correct,
            responseTime: responseTime,
          );
      _interactionStartedAt = DateTime.now();
      return session;
    });
  }

  /// À appeler quand l'utilisateur commence réellement à répondre — pour
  /// `memory`, c'est au passage en phase de rappel (la phase de
  /// mémorisation, à durée choisie par l'utilisateur, ne doit pas gonfler
  /// artificiellement `response_time` et fausser l'adaptation de
  /// difficulté côté backend).
  void markInteractionStart() {
    _interactionStartedAt = DateTime.now();
  }

  Duration _elapsedSinceInteractionStart() {
    final startedAt = _interactionStartedAt;
    if (startedAt == null) return Duration.zero;
    return DateTime.now().difference(startedAt);
  }

  void reset() {
    _interactionStartedAt = null;
    state = const AsyncData(null);
  }
}

final sessionControllerProvider =
    AsyncNotifierProvider<SessionController, SessionState?>(SessionController.new);
