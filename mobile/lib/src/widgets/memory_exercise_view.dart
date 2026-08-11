import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/exercise.dart';
import '../providers/providers.dart';

enum _MemoryPhase { memorize, recall }

/// Exercice de mémorisation en deux temps : on affiche la séquence, puis
/// on la cache et on demande à l'utilisateur de la reproduire dans
/// l'ordre. Le backend ne connaît pas de notion de "bonne réponse" pour
/// `memory` (contrairement à `calc`) — c'est le client qui administre le
/// test et l'auto-corrige avant de renvoyer `correct` au serveur.
class MemoryExerciseView extends ConsumerStatefulWidget {
  const MemoryExerciseView({super.key, required this.exercise});

  final Exercise exercise;

  @override
  ConsumerState<MemoryExerciseView> createState() => _MemoryExerciseViewState();
}

class _MemoryExerciseViewState extends ConsumerState<MemoryExerciseView> {
  late final List<String> _items = widget.exercise.memoryItems;
  late final List<TextEditingController> _controllers = List.generate(
    _items.length,
    (_) => TextEditingController(),
  );
  _MemoryPhase _phase = _MemoryPhase.memorize;
  String? _feedback;
  bool _submitted = false;

  @override
  void dispose() {
    for (final controller in _controllers) {
      controller.dispose();
    }
    super.dispose();
  }

  void _startRecall() {
    ref.read(sessionControllerProvider.notifier).markInteractionStart();
    setState(() => _phase = _MemoryPhase.recall);
  }

  void _submit() {
    if (_submitted) return;
    final entered = _controllers.map((c) => c.text.trim()).toList();
    final correct = entered.length == _items.length &&
        List.generate(
          _items.length,
          (i) => entered[i].toLowerCase() == _items[i].toLowerCase(),
        ).every((match) => match);

    setState(() {
      _submitted = true;
      _feedback = correct ? 'Correct !' : "Raté — c'était : ${_items.join(', ')}";
    });
    ref.read(sessionControllerProvider.notifier).answer(correct: correct);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    if (_phase == _MemoryPhase.memorize) {
      return Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text('Mémorise cette séquence :', style: theme.textTheme.titleMedium),
          const SizedBox(height: 16),
          Wrap(
            alignment: WrapAlignment.center,
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final item in _items)
                Chip(label: Text(item, style: const TextStyle(fontSize: 18))),
            ],
          ),
          const SizedBox(height: 32),
          FilledButton.icon(
            onPressed: _startRecall,
            icon: const Icon(Icons.visibility_off),
            label: const Text("C'est mémorisé, cacher la séquence"),
          ),
        ],
      );
    }

    return SingleChildScrollView(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text("Reproduis la séquence, dans l'ordre :", style: theme.textTheme.titleMedium),
          const SizedBox(height: 16),
          Wrap(
            alignment: WrapAlignment.center,
            spacing: 8,
            runSpacing: 8,
            children: [
              for (var i = 0; i < _items.length; i++)
                SizedBox(
                  width: 64,
                  child: TextField(
                    controller: _controllers[i],
                    enabled: !_submitted,
                    autofocus: i == 0,
                    textAlign: TextAlign.center,
                    decoration: InputDecoration(
                      border: const OutlineInputBorder(),
                      counterText: '',
                      labelText: '${i + 1}',
                    ),
                    maxLength: 12,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 24),
          FilledButton(
            onPressed: _submitted ? null : _submit,
            child: const Text('Valider'),
          ),
          if (_feedback != null) ...[
            const SizedBox(height: 16),
            Text(_feedback!, style: theme.textTheme.titleMedium),
          ],
        ],
      ),
    );
  }
}
