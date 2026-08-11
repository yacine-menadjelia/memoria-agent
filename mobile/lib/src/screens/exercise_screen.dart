import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/providers.dart';
import '../widgets/calc_exercise_view.dart';
import '../widgets/memory_exercise_view.dart';
import '../widgets/session_header.dart';

class ExerciseScreen extends ConsumerWidget {
  const ExerciseScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sessionAsync = ref.watch(sessionControllerProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Exercice'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Terminer la session',
            onPressed: () {
              ref.read(sessionControllerProvider.notifier).reset();
              Navigator.of(context).popUntil((route) => route.isFirst);
            },
          ),
        ],
      ),
      body: SafeArea(
        child: sessionAsync.when(
          data: (session) {
            if (session == null || session.currentExercise == null) {
              return const Center(child: Text('Aucun exercice en cours.'));
            }
            final exercise = session.currentExercise!;
            // Clé basée sur l'historique + la famille : force un nouveau
            // widget (et donc de nouveaux TextEditingController vierges)
            // à chaque exercice, plutôt que de réutiliser l'état du
            // précédent.
            final exerciseKey = ValueKey('${session.history.length}-${exercise.type}');

            return Column(
              children: [
                SessionHeader(session: session),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: exercise.isMemory
                        ? MemoryExerciseView(key: exerciseKey, exercise: exercise)
                        : CalcExerciseView(key: exerciseKey, exercise: exercise),
                  ),
                ),
              ],
            );
          },
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Text('Erreur : $error', textAlign: TextAlign.center),
            ),
          ),
        ),
      ),
    );
  }
}
