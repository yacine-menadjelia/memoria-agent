/// Un exercice tel que renvoyé par l'API (`current_exercise`).
///
/// `content` change de forme selon `type` : une chaîne pour `calc`
/// ("14 * 6"), une liste de chaînes pour `memory` (["7", "chat", "9"]).
/// On garde `dynamic` côté modèle et on expose des accesseurs typés
/// ([calcExpression], [memoryItems]) plutôt que deux classes séparées,
/// pour rester au plus près du contrat JSON réel du backend.
class Exercise {
  const Exercise({
    required this.type,
    required this.content,
    required this.difficulty,
    this.answer,
  });

  final String type;
  final dynamic content;
  final int difficulty;

  /// Uniquement présent pour `calc`. Le backend calcule cette valeur
  /// côté serveur (jamais confiance dans un calcul fait par le LLM) ;
  /// le client s'en sert pour l'auto-correction.
  final num? answer;

  bool get isMemory => type == 'memory';

  String get calcExpression => content as String;

  List<String> get memoryItems => (content as List).cast<String>();

  factory Exercise.fromJson(Map<String, dynamic> json) {
    return Exercise(
      type: json['type'] as String,
      content: json['content'],
      difficulty: json['difficulty'] as int,
      answer: json['answer'] as num?,
    );
  }
}
