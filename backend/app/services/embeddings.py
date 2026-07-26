from sentence_transformers import SentenceTransformer

# Loaded once at import time and reused — runs locally, so it doesn't touch
# the Gemini free-tier quota at all. 384-dim output matches models.py's Vector(384).
_model = SentenceTransformer("all-MiniLM-L6-v2")


def embed_text(text: str) -> list[float]:
    return _model.encode(text[:2000]).tolist()
