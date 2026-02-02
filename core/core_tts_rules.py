"""
core_tts_rules.py

Text -> speech-ready chunks.
No Qt. No file I/O. Pure functions.
"""

from __future__ import annotations

import re
from typing import List

from core.core_drivers import TTS

## ## This is for the see-say rules
_UI_LABEL_RE = re.compile(r"^\s*(You|Doris)\s*:\s*", re.IGNORECASE)
_BRACKET_TAG_RE = re.compile(r"\[[A-Z _-]{3,}\]")  # e.g. [BACKEND ERROR], [TTS ERROR]
_PATH_RE = re.compile(r"(/[^ \n\t]+)+")  # crude unix path matcher
_MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_MD_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)")
_MD_UNDERSCORE_RE = re.compile(r"_(.+?)_")
_LONE_ASTERISK_RE = re.compile(r"(?<!\w)\*(?!\w)")
_NON_LATIN_RE = re.compile(r"[^\x00-\x7F]")  # any non-ASCII character


## ## This is the original set, from initial build.
_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_URL_RE = re.compile(r"https?://\S+")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")
_MULTI_WS_RE = re.compile(r"[ \t]+")
_MULTI_NL_RE = re.compile(r"\n{3,}")
_BULLET_RE = re.compile(r"^\s*([-*•]+)\s+", re.MULTILINE)


##  ##                                      ##  ##  -- -- This is to help the TTS skip non-English characters  -- --  ##  ##
def sanitize_for_tts(text: str) -> str:
    t = text or ""
    # Non-English / non-ASCII guard:
    # Detect non-Latin writing systems (exclude emojis & symbols)
    _NON_LATIN_SCRIPT_RE = re.compile(
        r"[\u0400-\u04FF"  # Cyrillic
        r"\u0600-\u06FF"  # Arabic
        r"\u0750-\u077F"
        r"\u08A0-\u08FF"
        r"\u3040-\u30FF"  # Hiragana / Katakana
        r"\u3400-\u4DBF"  # CJK Extension A
        r"\u4E00-\u9FFF]"  # CJK Unified Ideographs
    )

    ##  ##                              ##  ## Clears Hashtags in vocalization
    _HASHTAG_WORD_RE = re.compile(r"(?<!\w)#([A-Za-z0-9_]+)")

    if TTS.strip_markdown:
        # Convert markdown links to readable label
        t = _MD_LINK_RE.sub(r"\1", t)
        # Strip markdown emphasis so TTS doesn't read '*' literally
        # Handle bold (**text**)
        t = _MD_BOLD_RE.sub(r"\1", t)
        # Handle italic (*text*)
        t = _MD_ITALIC_RE.sub(r"\1", t)
        # Handle underscore (_text_)
        t = _MD_UNDERSCORE_RE.sub(r"\1", t)

    if TTS.strip_code_blocks:
        t = _CODE_FENCE_RE.sub(" ", t)

    if TTS.strip_inline_code:
        t = _INLINE_CODE_RE.sub(r"\1", t)

    if TTS.strip_urls:
        t = _URL_RE.sub(" ", t)

    ##  ##                              ##  ##  -- -- See-Say rules -- --  ##  ##
    # --- See-say rewrite pass (conservative) ---
    # Goal: don't speak UI scaffolding or log tags; speak intent instead.
    t = _UI_LABEL_RE.sub("", t)

    # Replace loud bracket tags with a spoken cue
    t = _BRACKET_TAG_RE.sub(" Notice:", t)

    # Replace raw filesystem paths with a human phrase
    t = _PATH_RE.sub(" a file path", t)

    # Hashtags: keep the word, drop the '#'
    t = _HASHTAG_WORD_RE.sub(r"\1", t)
    # Clean up any leftover standalone '#' -- but ensure we don't merge words if spaces are missing
    t = t.replace("#", " ")

    # Bullets -> "1) ..." style (helps speech cadence)
    if TTS.speak_lists_as_sentences:
        lines = t.splitlines()
        out: List[str] = []
        n = 1
        for line in lines:
            m = _BULLET_RE.match(line)
            if m:
                out.append(f"{n}. {_BULLET_RE.sub('', line).strip()}")
                n += 1
            else:
                out.append(line)
        t = "\n".join(out)

    # Remove stray '*' characters that slip through
    t = _LONE_ASTERISK_RE.sub(" ", t)


    if TTS.normalize_punctuation:
        t = t.replace("…", ".")
        t = re.sub(r"[!?]{3,}", "!", t)
        t = re.sub(r"\.{3,}", ".", t)

    if TTS.collapse_whitespace:
        t = _MULTI_WS_RE.sub(" ", t)
        t = _MULTI_NL_RE.sub("\n\n", t)

    return t.strip()


def chunk_for_tts(text: str) -> List[str]:
    """
    Sentence-ish chunking aimed at low-latency playback.
    Splits on punctuation more aggressively to feed the streamer.
    """
    t = sanitize_for_tts(text)
    if not t:
        return []

    # 1. Split on strong punctuation (. ! ?)
    # 2. Also consider commas or semicolons if chunks get too long (optional optimization)
    # The regex splits AFTER the punctuation, keeping it in the previous chunk if possible,
    # or we handle the split list carefully.
    
    # This regex splits *after* a sentence terminator (., !, ?) followed by whitespace or end of string.
    parts = re.split(r"(?<=[.!?])\s+", t)
    
    chunks: List[str] = []
    buf = ""
    
    # Target chunk size for "live" feel. 
    # Too small = robotic/choppy. Too large = latency.
    # ~50-80 chars is often a good balance for Piper.
    SOFT_LIMIT = 80 

    for p in parts:
        p = p.strip()
        if not p:
            continue

        if not buf:
            buf = p
            continue

        # If adding this part exceeds max, flush existing buffer
        if len(buf) + 1 + len(p) > TTS.max_chars_per_chunk:
            chunks.append(buf)
            buf = p
        
        # If the current buffer is already "long enough" (soft limit) and this is a new sentence, flush it
        elif len(buf) > SOFT_LIMIT:
             chunks.append(buf)
             buf = p
             
        else:
            # Merge
            buf = f"{buf} {p}"

    if buf:
        chunks.append(buf)

    return chunks
