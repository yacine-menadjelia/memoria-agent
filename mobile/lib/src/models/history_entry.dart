class HistoryEntry {
  const HistoryEntry({
    required this.family,
    required this.correct,
    required this.responseTime,
  });

  final String family;
  final bool correct;
  final double responseTime;

  factory HistoryEntry.fromJson(Map<String, dynamic> json) {
    return HistoryEntry(
      family: json['family'] as String,
      correct: json['correct'] as bool,
      responseTime: (json['response_time'] as num).toDouble(),
    );
  }
}
