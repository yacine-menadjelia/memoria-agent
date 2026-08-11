import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/session_state.dart';
import 'api_exception.dart';

/// Client HTTP pour les trois endpoints exposés par le backend
/// (backend/app/main.py) : démarrer une session, répondre à l'exercice
/// courant, relire l'état d'une session.
class ApiClient {
  ApiClient({http.Client? client, String? baseUrl})
      : _client = client ?? http.Client(),
        baseUrl = baseUrl ?? _defaultBaseUrl();

  final http.Client _client;
  final String baseUrl;

  /// Toujours `localhost` : sur Android (émulateur ou appareil physique en
  /// USB), on route vers le backend de l'hôte via `adb reverse tcp:8000
  /// tcp:8000` plutôt que de bricoler des cas par plateforme (`10.0.2.2`
  /// pour l'émulateur uniquement, IP LAN pour un appareil physique...).
  /// Un seul mécanisme réseau à documenter, qui marche pour les deux —
  /// voir mobile/README.md.
  static String _defaultBaseUrl() => 'http://localhost:8000';

  Future<SessionState> startSession(String userId) async {
    final response = await _client.post(
      Uri.parse('$baseUrl/sessions/start'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({'user_id': userId}),
    );
    return _decode(response);
  }

  Future<SessionState> submitAnswer(
    String sessionId, {
    required bool correct,
    required double responseTime,
  }) async {
    final response = await _client.post(
      Uri.parse('$baseUrl/sessions/$sessionId/answer'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({'correct': correct, 'response_time': responseTime}),
    );
    return _decode(response);
  }

  Future<SessionState> getSession(String sessionId) async {
    final response = await _client.get(Uri.parse('$baseUrl/sessions/$sessionId'));
    return _decode(response);
  }

  SessionState _decode(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return SessionState.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
    }

    String detail = response.body;
    try {
      final parsed = jsonDecode(response.body);
      if (parsed is Map && parsed['detail'] != null) {
        detail = parsed['detail'].toString();
      }
    } catch (_) {
      // corps non-JSON (erreur réseau bas niveau, proxy, etc.) : on garde
      // le corps brut comme message
    }
    throw ApiException(detail, statusCode: response.statusCode);
  }
}
