import 'dart:convert';
import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kIsWeb;
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

  /// L'émulateur Android tourne dans sa propre VM réseau : `localhost` y
  /// désigne l'émulateur lui-même, pas la machine hôte qui fait tourner le
  /// `docker compose` du backend. `10.0.2.2` est l'alias spécial que
  /// l'émulateur fournit pour atteindre le localhost de l'hôte. Le web et
  /// le desktop partagent directement le réseau de l'hôte, donc
  /// `localhost` y fonctionne normalement.
  static String _defaultBaseUrl() {
    if (kIsWeb) return 'http://localhost:8000';
    if (Platform.isAndroid) return 'http://10.0.2.2:8000';
    return 'http://localhost:8000';
  }

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
