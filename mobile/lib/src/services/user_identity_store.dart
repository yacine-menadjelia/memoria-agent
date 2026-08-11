import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

/// Persiste un identifiant utilisateur stable entre les lancements de
/// l'app. Le backend distingue explicitement `user_id` (persistant,
/// alimente `load_user_profile`) de `session_id` (éphémère, un par
/// partie) — voir backend/README.md. Réutiliser le même `user_id`
/// d'un lancement à l'autre permet à l'app de bénéficier de la reprise
/// de difficulté ("cold start problem" mitigé côté backend).
class UserIdentityStore {
  static const _prefsKey = 'memoria_user_id';

  Future<String> loadOrCreate() async {
    final prefs = await SharedPreferences.getInstance();
    final existing = prefs.getString(_prefsKey);
    if (existing != null) return existing;
    return _generateAndPersist(prefs);
  }

  Future<String> reset() async {
    final prefs = await SharedPreferences.getInstance();
    return _generateAndPersist(prefs);
  }

  Future<String> _generateAndPersist(SharedPreferences prefs) async {
    final generated = const Uuid().v4();
    await prefs.setString(_prefsKey, generated);
    return generated;
  }
}
