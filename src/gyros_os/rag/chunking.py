"""Text chunking strategies for the RAG pipeline.

Splits text into chunks targeting ~512 tokens with 50-token overlap.
Uses semantic separators (paragraphs, then sentences) before falling
back to fixed-size splitting.
"""

import tiktoken

# Target chunk size and overlap in tokens
TARGET_TOKENS = 512
OVERLAP_TOKENS = 50

# Encoding for token counting (cl100k_base is used by text-embedding-3-small)
_encoding = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count tokens using cl100k_base encoding."""
    return len(_encoding.encode(text))


def chunk_text(text: str) -> list[tuple[str, int]]:
    """Split text into chunks with semantic boundaries.

    Strategy:
    1. Split by double newlines (paragraphs).
    2. If a paragraph exceeds TARGET_TOKENS, split by sentences.
    3. If a sentence still exceeds, split by fixed token count.

    Returns:
        List of (chunk_text, token_count) tuples.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    # Merge small paragraphs and split large ones into sentence-level pieces
    pieces: list[str] = []
    for para in paragraphs:
        if count_tokens(para) <= TARGET_TOKENS:
            pieces.append(para)
        else:
            # Split paragraph into sentences
            pieces.extend(_split_into_sentences(para))

    # Now group pieces into chunks respecting TARGET_TOKENS
    chunks: list[tuple[str, int]] = []
    current_pieces: list[str] = []
    current_tokens = 0

    for piece in pieces:
        piece_tokens = count_tokens(piece)

        # If a single piece exceeds target, force-split it
        if piece_tokens > TARGET_TOKENS:
            # Flush current buffer first
            if current_pieces:
                chunk_text_str = "\n\n".join(current_pieces)
                chunks.append((chunk_text_str, count_tokens(chunk_text_str)))
                current_pieces, current_tokens = _apply_overlap(
                    current_pieces, chunks
                )

            for sub_chunk, sub_tokens in _fixed_split(piece):
                chunks.append((sub_chunk, sub_tokens))
            continue

        if current_tokens + piece_tokens > TARGET_TOKENS and current_pieces:
            chunk_text_str = "\n\n".join(current_pieces)
            chunks.append((chunk_text_str, count_tokens(chunk_text_str)))
            current_pieces, current_tokens = _apply_overlap(
                current_pieces, chunks
            )

        current_pieces.append(piece)
        current_tokens += piece_tokens

    # Flush remaining
    if current_pieces:
        chunk_text_str = "\n\n".join(current_pieces)
        chunks.append((chunk_text_str, count_tokens(chunk_text_str)))

    return chunks


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences using simple heuristics."""
    import re

    # Split on sentence-ending punctuation followed by space or end
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _fixed_split(text: str) -> list[tuple[str, int]]:
    """Split text into fixed-size token chunks as a last resort."""
    tokens = _encoding.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + TARGET_TOKENS, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_str = _encoding.decode(chunk_tokens)
        chunks.append((chunk_str, len(chunk_tokens)))
        start = end - OVERLAP_TOKENS if end < len(tokens) else end
    return chunks


def _apply_overlap(
    current_pieces: list[str],
    chunks: list[tuple[str, int]],
) -> tuple[list[str], int]:
    """Keep trailing pieces as overlap for the next chunk.

    Returns new (pieces, token_count) to seed the next chunk buffer.
    """
    # Walk backwards through pieces to gather ~OVERLAP_TOKENS
    overlap_pieces: list[str] = []
    overlap_tokens = 0
    for piece in reversed(current_pieces):
        piece_tok = count_tokens(piece)
        if overlap_tokens + piece_tok > OVERLAP_TOKENS:
            break
        overlap_pieces.insert(0, piece)
        overlap_tokens += piece_tok
    return overlap_pieces, overlap_tokens
