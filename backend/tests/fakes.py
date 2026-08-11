import json


class FakeTextBlock:
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class FakeMessageResponse:
    def __init__(self, payload):
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        self.content = [FakeTextBlock(text)]


class FakeMessages:
    def __init__(self, payload):
        self._payload = payload
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeMessageResponse(self._payload)


class FakeAnthropicClient:
    """Double du client Anthropic : renvoie toujours le même payload JSON,
    sans appel réseau. Les tests inspectent .messages.calls pour vérifier ce
    qui a été envoyé au modèle (system prompt, schema, etc.)."""

    def __init__(self, payload):
        self.messages = FakeMessages(payload)


class FakeProfileStore:
    def __init__(self, profile: dict | None):
        self._profile = profile
        self.calls: list[str] = []

    def get(self, user_id: str):
        self.calls.append(user_id)
        return self._profile


class FakeExerciseHistoryStore:
    def __init__(self, recent_contents=None, error_stats=None):
        self._recent_contents = recent_contents or []
        self._error_stats = error_stats or {}
        self.recent_contents_calls: list[tuple] = []
        self.error_stats_calls: list[tuple] = []

    def recent_contents(self, user_id, family, limit=5):
        self.recent_contents_calls.append((user_id, family, limit))
        return self._recent_contents

    def error_stats(self, user_id, family, window=20):
        self.error_stats_calls.append((user_id, family, window))
        return self._error_stats


class FakeKnowledgeBase:
    def __init__(self, tips=None, raises: Exception | None = None):
        self._tips = tips or []
        self._raises = raises
        self.calls: list[tuple] = []

    def search(self, family, difficulty, k=3):
        self.calls.append((family, difficulty, k))
        if self._raises is not None:
            raise self._raises
        return self._tips
