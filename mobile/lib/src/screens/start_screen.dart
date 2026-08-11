import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/providers.dart';
import 'exercise_screen.dart';

class StartScreen extends ConsumerWidget {
  const StartScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final userIdAsync = ref.watch(userIdProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Memoria')),
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: userIdAsync.when(
            data: (userId) => _StartContent(userId: userId),
            loading: () => const CircularProgressIndicator(),
            error: (error, _) => Text('Erreur : $error'),
          ),
        ),
      ),
    );
  }
}

class _StartContent extends ConsumerWidget {
  const _StartContent({required this.userId});

  final String userId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sessionAsync = ref.watch(sessionControllerProvider);
    final isLoading = sessionAsync.isLoading;

    ref.listen(sessionControllerProvider, (previous, next) {
      final session = next.value;
      if (session != null) {
        Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => const ExerciseScreen()),
        );
      }
    });

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.psychology_alt, size: 72, color: Theme.of(context).colorScheme.primary),
        const SizedBox(height: 16),
        Text(
          "Entraîne ta mémoire et ton calcul mental.\nLa difficulté s'adapte à toi.",
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodyLarge,
        ),
        const SizedBox(height: 24),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              children: [
                const Text('Identifiant utilisateur', style: TextStyle(fontWeight: FontWeight.bold)),
                const SizedBox(height: 4),
                SelectableText(
                  userId,
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 24),
        FilledButton.icon(
          onPressed: isLoading ? null : () => ref.read(sessionControllerProvider.notifier).start(userId),
          icon: isLoading
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.play_arrow),
          label: const Text('Commencer une session'),
        ),
        const SizedBox(height: 8),
        TextButton(
          onPressed: isLoading
              ? null
              : () async {
                  await ref.read(userIdentityStoreProvider).reset();
                  ref.invalidate(userIdProvider);
                },
          child: const Text('Nouvel utilisateur'),
        ),
        if (sessionAsync.hasError)
          Padding(
            padding: const EdgeInsets.only(top: 16),
            child: Text(
              'Erreur : ${sessionAsync.error}',
              style: TextStyle(color: Theme.of(context).colorScheme.error),
              textAlign: TextAlign.center,
            ),
          ),
      ],
    );
  }
}
