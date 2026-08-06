"""
Alexandria RAG Configuration
Copy to config.py and customize as needed.
"""

# Book directory
BOOKS_DIRECTORY = "/Volumes/PRO-BLADE/Alexandria"

# Embedding model
# Options: all-MiniLM-L6-v2 (default), all-mpnet-base-v2, all-roberta-large-v1
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Chunking parameters
CHUNK_SIZE = 512      # Approximate tokens per chunk
CHUNK_OVERLAP = 50    # Tokens of overlap between chunks
MIN_CHUNK_LENGTH = 50  # Minimum chunk length (words)

# Batch processing
BATCH_SIZE = 128      # Batch size for embedding generation

# Search parameters
DEFAULT_K = 5         # Default number of results to return
SIMILARITY_THRESHOLD = 0.3  # Minimum similarity score (0-1)

# Output
OUTPUT_DIRECTORY = "."
INDEX_NAME = "alexandria"

# Advanced
DEVICE = "auto"  # "auto", "cuda", "cpu", "mps"
SHOW_PROGRESS = True
