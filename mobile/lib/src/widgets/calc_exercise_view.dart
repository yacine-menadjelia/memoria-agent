import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/exercise.dart';
import '../providers/providers.dart';

class CalcExerciseView extends ConsumerStatefulWidget {
  const CalcExerciseView({super.key, required this.exercise});

  final Exercise exercise;

  @override
  ConsumerState<CalcExerciseView> createState() => _CalcExerciseViewState();
}

class _CalcExerciseViewState extends ConsumerState<CalcExerciseView> {
  final _controller = TextEditingController();
  String? _feedback;
  bool _submitted = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _submit() {
    if (_submitted) return;
    final entered = num.tryParse(_controller.text.trim());
    final expected = widget.exercise.answer;
    final correct = entered != null && expected != null && entered == expected;

    setState(() {
      _submitted = true;
      _feedback = correct ? 'Correct !' : 'Raté — la réponse était $expected';
    });
    ref.read(sessionControllerProvider.notifier).answer(correct: correct);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Text(
          widget.exercise.calcExpression,
          style: theme.textTheme.displaySmall,
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 32),
        SizedBox(
          width: 200,
          child: TextField(
            controller: _controller,
            enabled: !_submitted,
            autofocus: true,
            keyboardType: const TextInputType.numberWithOptions(signed: true),
            textAlign: TextAlign.center,
            style: theme.textTheme.headlineSmall,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              hintText: 'Réponse',
            ),
            onSubmitted: (_) => _submit(),
          ),
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
    );
  }
}
