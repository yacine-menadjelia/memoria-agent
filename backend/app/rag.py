import psycopg
import voyageai

DEFAULT_MODEL = "voyage-3.5"

# Contenu pédagogique de départ : quelques repères sur la mémorisation et le
# calcul mental, tagués par famille d'exercice pour filtrer la recherche.
# family=None = repère général, valable pour les deux familles.
SEED_KNOWLEDGE = [
    {
        "family": "memory",
        "content": (
            "Le chunking (regrouper les éléments par blocs de 3 à 4) rend une "
            "séquence bien plus facile à retenir qu'un flux continu d'éléments "
            "isolés."
        ),
    },
    {
        "family": "memory",
        "content": (
            "Associer chaque élément à une image mentale concrète aide à "
            "mémoriser des séquences mixtes chiffres/mots."
        ),
    },
    {
        "family": "memory",
        "content": (
            "Les séquences trop longues d'un coup découragent plus qu'elles "
            "n'entraînent : mieux vaut allonger progressivement d'un ou deux "
            "éléments à la fois."
        ),
    },
    {
        "family": "memory",
        "content": (
            "Mélanger chiffres et mots dans une même séquence sollicite deux "
            "systèmes de mémoire différents (verbal et numérique), ce qui "
            "augmente la difficulté perçue même à longueur égale."
        ),
    },
    {
        "family": "calc",
        "content": (
            "Décomposer un nombre (ex: 47 = 40 + 7) avant de multiplier ou "
            "d'additionner est une stratégie de calcul mental plus fiable que "
            "le calcul posé mental direct."
        ),
    },
    {
        "family": "calc",
        "content": (
            "Les erreurs de calcul mental augmentent fortement dès qu'une "
            "expression combine plus de deux opérations ou introduit des "
            "parenthèses."
        ),
    },
    {
        "family": "calc",
        "content": (
            "Les divisions qui ne tombent pas juste sont nettement plus "
            "difficiles à traiter mentalement : réserver les divisions "
            "exactes tant que la difficulté n'est pas élevée."
        ),
    },
    {
        "family": "calc",
        "content": (
            "La table de multiplication reste le goulot d'étranglement "
            "principal du calcul mental jusqu'à un niveau intermédiaire ; "
            "au-delà, c'est la gestion de plusieurs étapes qui domine."
        ),
    },
    {
        "family": None,
        "content": (
            "Un utilisateur qui enchaîne les erreurs bénéficie davantage "
            "d'une baisse de difficulté immédiate que d'un encouragement à "
            "persévérer sur le même niveau."
        ),
    },
    {
        "family": None,
        "content": (
            "Revenir sur une famille d'exercice récemment ratée consolide "
            "mieux l'apprentissage qu'un évitement systématique de cette "
            "famille."
        ),
    },
]


def _to_vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"


def _embedding_dim(client: voyageai.Client, model: str) -> int:
    result = client.embed(["dimension probe"], model=model, input_type="document")
    return len(result.embeddings[0])


def _seed_knowledge_base(database_url: str, client: voyageai.Client, model: str) -> None:
    texts = [entry["content"] for entry in SEED_KNOWLEDGE]
    result = client.embed(texts, model=model, input_type="document")
    with psycopg.connect(database_url) as conn:
        for entry, embedding in zip(SEED_KNOWLEDGE, result.embeddings):
            conn.execute(
                "INSERT INTO knowledge_base (family, content, embedding) "
                "VALUES (%s, %s, %s::vector)",
                (entry["family"], entry["content"], _to_vector_literal(embedding)),
            )


def init_knowledge_base(database_url: str, client: voyageai.Client, model: str = DEFAULT_MODEL) -> None:
    with psycopg.connect(database_url) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        table_exists = conn.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'knowledge_base'"
        ).fetchone()

    if table_exists is not None:
        return

    # la table n'existe pas encore : on sonde la dimension réelle du modèle
    # d'embedding plutôt que de la coder en dur (elle diffère selon le modèle)
    dim = _embedding_dim(client, model)
    with psycopg.connect(database_url) as conn:
        conn.execute(
            f"""
            CREATE TABLE knowledge_base (
                id SERIAL PRIMARY KEY,
                family TEXT,
                content TEXT NOT NULL,
                embedding vector({dim}) NOT NULL
            )
            """
        )
    _seed_knowledge_base(database_url, client, model)


class KnowledgeBaseStore:
    def __init__(self, database_url: str, client: voyageai.Client, model: str = DEFAULT_MODEL):
        self._database_url = database_url
        self._client = client
        self._model = model

    def search(self, family: str, difficulty: int, k: int = 3) -> list[str]:
        query = f"Conseils pédagogiques pour un exercice de {family} à difficulté {difficulty}/10."
        result = self._client.embed([query], model=self._model, input_type="query")
        embedding_literal = _to_vector_literal(result.embeddings[0])
        with psycopg.connect(self._database_url) as conn:
            rows = conn.execute(
                """
                SELECT content FROM knowledge_base
                WHERE family IS NULL OR family = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (family, embedding_literal, k),
            ).fetchall()
        return [row[0] for row in rows]
