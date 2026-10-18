"""Text chunking on paragraph and sentence boundaries with overlap."""

from __future__ import annotations

import re
from typing import Optional
from luna.ingest.models import ParsedChunk


def chunk_text(
    source_id: str,
    source_name: str,
    raw_text: str,
    max_chunk_chars: int = 1500,
    overlap_chars: int = 200,
    max_total_chunks: int = 400,
) -> list[ParsedChunk]:
    """Split text into chunks of at most max_chunk_chars with overlap_chars."""
    # Normalize newlines
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        return []

    chunks: list[ParsedChunk] = []
    paragraphs = re.split(r"(\n\s*\n)", text)

    current_chunk: list[str] = []
    current_len = 0
    char_start = 0
    current_char = 0
    line_start = 1

    for part in paragraphs:
        part_len = len(part)
        if current_len + part_len <= max_chunk_chars:
            if not current_chunk:
                char_start = current_char
                line_start = text[:char_start].count("\n") + 1
            current_chunk.append(part)
            current_len += part_len
            current_char += part_len
        else:
            # Current chunk is full, emit it
            if current_chunk:
                chunk_str = "".join(current_chunk)
                char_end = char_start + len(chunk_str)
                chunks.append(
                    ParsedChunk(
                        source_id=source_id,
                        source_name=source_name,
                        text=chunk_str,
                        char_start=char_start,
                        char_end=char_end,
                        line_start=line_start,
                    )
                )
                if len(chunks) >= max_total_chunks:
                    return chunks

                # Calculate overlap
                overlap_text = chunk_str[-overlap_chars:] if len(chunk_str) > overlap_chars else ""
                current_chunk = [overlap_text, part]
                current_len = len(overlap_text) + part_len
                char_start = char_end - len(overlap_text)
                current_char = char_start + current_len
                line_start = text[:char_start].count("\n") + 1
            else:
                # A single paragraph is larger than max_chunk_chars; split by sentence or hard slice
                sentences = re.split(r"(?<=[.!?])\s+", part)
                for sent in sentences:
                    if current_len + len(sent) <= max_chunk_chars:
                        if not current_chunk:
                            char_start = current_char
                            line_start = text[:char_start].count("\n") + 1
                        current_chunk.append(sent)
                        current_len += len(sent)
                        current_char += len(sent)
                    else:
                        if current_chunk:
                            chunk_str = " ".join(current_chunk)
                            char_end = char_start + len(chunk_str)
                            chunks.append(
                                ParsedChunk(
                                    source_id=source_id,
                                    source_name=source_name,
                                    text=chunk_str,
                                    char_start=char_start,
                                    char_end=char_end,
                                    line_start=line_start,
                                )
                            )
                            if len(chunks) >= max_total_chunks:
                                return chunks
                        # Hard slice sent if longer than max_chunk_chars
                        s_text = sent
                        while len(s_text) > max_chunk_chars:
                            slice_str = s_text[:max_chunk_chars]
                            chunks.append(
                                ParsedChunk(
                                    source_id=source_id,
                                    source_name=source_name,
                                    text=slice_str,
                                    char_start=current_char,
                                    char_end=current_char + len(slice_str),
                                    line_start=text[:current_char].count("\n") + 1,
                                )
                            )
                            current_char += len(slice_str) - overlap_chars
                            s_text = s_text[max_chunk_chars - overlap_chars:]
                            if len(chunks) >= max_total_chunks:
                                return chunks
                        current_chunk = [s_text]
                        current_len = len(s_text)
                        char_start = current_char
                        current_char += current_len
                        line_start = text[:char_start].count("\n") + 1

    if current_chunk:
        chunk_str = "".join(current_chunk).strip()
        if chunk_str:
            chunks.append(
                ParsedChunk(
                    source_id=source_id,
                    source_name=source_name,
                    text=chunk_str,
                    char_start=char_start,
                    char_end=char_start + len(chunk_str),
                    line_start=line_start,
                )
            )

    return chunks[:max_total_chunks]
