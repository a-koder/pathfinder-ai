from pinecone import Pinecone, ServerlessSpec
import config

_DIMENSION = 1536       # text-embedding-3-small output dimension
_NAMESPACE = "default"
_BATCH_SIZE = 100


class PineconeClient:
    """Wraps pinecone.Pinecone() for index init, upsert, and query. Only layer that imports pinecone."""

    def __init__(self):
        self._pc = Pinecone(api_key=config.PINECONE_API_KEY)
        self._index_name = config.PINECONE_INDEX_NAME
        self._index = None

    def initialize_pinecone(self) -> None:
        """Connect to the index, creating it first if it does not exist."""
        self.create_index_if_needed()
        self._index = self._pc.Index(self._index_name)

    def create_index_if_needed(self) -> None:
        """Create the Pinecone serverless index if it is not already present."""
        existing = {idx.name for idx in self._pc.list_indexes()}
        if self._index_name not in existing:
            self._pc.create_index(
                name=self._index_name,
                dimension=_DIMENSION,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )

    def upsert_vectors(self, vectors: list[dict]) -> None:
        """Upsert a list of {id, values, metadata} dicts in batches of 100."""
        if self._index is None:
            self.initialize_pinecone()
        for i in range(0, len(vectors), _BATCH_SIZE):
            batch = vectors[i : i + _BATCH_SIZE]
            self._index.upsert(vectors=batch, namespace=_NAMESPACE)

    def query_vectors(
        self,
        vector: list[float],
        top_k: int = 5,
        filter: dict | None = None,
    ) -> list[dict]:
        """Return top-k matches as [{id, score, metadata}] dicts."""
        if self._index is None:
            self.initialize_pinecone()
        response = self._index.query(
            vector=vector,
            top_k=top_k,
            filter=filter,
            include_metadata=True,
            namespace=_NAMESPACE,
        )
        return [
            {"id": m["id"], "score": m["score"], "metadata": m.get("metadata", {})}
            for m in response["matches"]
        ]

    # Legacy aliases kept for Phase 5+ stubs that call the old signatures
    def query(self, vector: list[float], top_k: int = 5, filter: dict | None = None) -> list[dict]:
        return self.query_vectors(vector, top_k, filter)

    def upsert(self, vectors: list[dict]) -> None:
        self.upsert_vectors(vectors)
