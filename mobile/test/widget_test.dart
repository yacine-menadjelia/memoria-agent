import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:memoria_mobile/main.dart';

void main() {
  testWidgets("l'écran de démarrage affiche le titre et un identifiant utilisateur", (
    tester,
  ) async {
    SharedPreferences.setMockInitialValues({});

    await tester.pumpWidget(const ProviderScope(child: MemoriaApp()));
    await tester.pumpAndSettle();

    expect(find.text('Memoria'), findsOneWidget);
    expect(find.text('Commencer une session'), findsOneWidget);
    expect(find.text('Identifiant utilisateur'), findsOneWidget);
  });
}
