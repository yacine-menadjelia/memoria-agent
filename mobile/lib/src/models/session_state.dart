import 'exercise.dart';
import 'history_entry.dart';

/// Miroir côté client de `_public_state()` dans le backend
/// (backend/app/main.py). Un seul modèle pour les trois réponses
/// (`/sessions/start`, `/sessions/{id}/answer`, `/sessions/{id}`) puisque
/// les trois endpoints renvoient exactement la même forme.
class SessionState {
  const SessionState({
    required this.sessionId,
    required this.userId,
    required this.currentExercise,
    required this.currentDifficulty,
    required this.exerciseFamily,
    required this.history,
  });

  final String sessionId;
  final String userId;
  final Exercise? currentExercise;
  final int currentDifficulty;
  final String exerciseFamily;
  final List<HistoryEntry> history;

  factory SessionState.fromJson(Map<String, dynamic> json) {
    return SessionState(
      sessionId: json['session_id'] as String,
      userId: json['user_id'] as String,
      currentExercise: json['current_exercise'] == null
          ? null
          : Exercise.fromJson(json['current_exercise'] as Map<String, dynamic>),
      currentDifficulty: json['current_difficulty'] as int,
      exerciseFamily: json['exercise_family'] as String,
      history: (json['history'] as List<dynamic>)
          .map((e) => HistoryEntry.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}
