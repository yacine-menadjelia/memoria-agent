import 'package:flutter/material.dart';

import '../models/session_state.dart';

class SessionHeader extends StatelessWidget {
  const SessionHeader({super.key, required this.session});

  final SessionState session;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final recentHistory = session.history.length > 8
        ? session.history.sublist(session.history.length - 8)
        : session.history;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      color: theme.colorScheme.surfaceContainerHighest,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Chip(
                avatar: const Icon(Icons.speed, size: 18),
                label: Text('Difficulté ${session.currentDifficulty}/10'),
              ),
              Chip(
                avatar: Icon(
                  session.exerciseFamily == 'memory' ? Icons.psychology : Icons.calculate,
                  size: 18,
                ),
                label: Text(session.exerciseFamily == 'memory' ? 'Mémoire' : 'Calcul'),
              ),
            ],
          ),
          if (recentHistory.isNotEmpty) ...[
            const SizedBox(height: 12),
            Row(
              children: [
                for (final entry in recentHistory)
                  Padding(
                    padding: const EdgeInsets.only(right: 4),
                    child: Icon(
                      entry.correct ? Icons.check_circle : Icons.cancel,
                      color: entry.correct ? Colors.green : Colors.red,
                      size: 18,
                    ),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
