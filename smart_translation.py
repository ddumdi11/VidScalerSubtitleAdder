"""
smart_translation.py

High‑quality SRT translation with OpenAI (and optional fallbacks).

Goals
- Merge SRT fragments into full sentences before translating
- Use LLM (OpenAI) for context‑aware EN->DE translation
- Keep original SRT timing by default (reflow text only)
- Provide simple caching and safe formatting for German

Environment
- OPENAI_API_KEY: required for provider='openai'
- OPENAI_MODEL: optional (default: gpt-3.5-turbo)

CLI
  py smart_translation.py input.srt en de --provider openai
"""

from __future__ import annotations

import os
import re
import json
import hashlib
import textwrap
from dataclasses import dataclass
from typing import List, Optional, Tuple


# Optional OpenAI dependencies (support both legacy and modern clients)
try:
    from openai import OpenAI as _OpenAIClient  # type: ignore
    _HAS_OPENAI_V1 = True
except Exception:
    _HAS_OPENAI_V1 = False
try:
    import openai  # type: ignore
    _HAS_OPENAI_LEGACY = True
except Exception:
    _HAS_OPENAI_LEGACY = False


@dataclass
class SRTBlock:
    index: int
    start: str
    end: str
    text: str


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_srt(path: str) -> List[SRTBlock]:
    try:
        raw = open(path, "r", encoding="utf-8").read()
    except UnicodeDecodeError:
        raw = open(path, "r", encoding="latin-1").read()

    entries: List[SRTBlock] = []
    # Accept optional spaces after index line, and robust CR/LF handling is covered by Python's universal newline mode.
    pattern = r"(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3})\s-->\s(\d{2}:\d{2}:\d{2},\d{3})\n([\s\S]*?)(?=\n\n|\Z)"
    for m in re.finditer(pattern, raw):
        idx = int(m.group(1))
        start = m.group(2)
        end = m.group(3)
        text = _normalize_whitespace(m.group(4).replace("\n", " "))
        if text:
            entries.append(SRTBlock(idx, start, end, text))
    return entries


def write_srt(path: str, blocks: List[SRTBlock]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for b in blocks:
            f.write(f"{b.index}\n{b.start} --> {b.end}\n{b.text}\n\n")


def _split_into_sentence_groups(blocks: List[SRTBlock], max_chars: int = 320) -> List[Tuple[int, int, str]]:
    """Group adjacent blocks into sentence‑like chunks.
    Returns list of (start_idx, end_idx, merged_text) with inclusive indices.
    """
    groups: List[Tuple[int, int, str]] = []
    cur_start = 0
    cur_text = []
    for i, b in enumerate(blocks):
        cur_text.append(b.text)
        merged = " ".join(cur_text)
        # End group on sentence punctuation or length threshold
        if re.search(r"[\.!?][\)\]\"]?$", merged) or len(merged) >= max_chars:
            groups.append((cur_start, i, _normalize_whitespace(merged)))
            cur_start = i + 1
            cur_text = []
    if cur_text:
        groups.append((cur_start, len(blocks) - 1, _normalize_whitespace(" ".join(cur_text))))
    return groups


def _german_postprocess(text: str) -> str:
    # Normalize quotes and whitespace typical for German typesetting
    text = text.replace('"', '"')  # keep straight quotes; GUI subtitles/ffmpeg handle them reliably
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r"\s+\.", ".", text)
    text = re.sub(r"\s+(!|\?|:|;)", r"\1", text)
    text = re.sub(r"\s+\)\s*", ") ", text)
    text = re.sub(r"\s+\(", " (", text)
    return text.strip()


def _wrap_two_lines(text: str, width: int = 42) -> str:
    lines = textwrap.wrap(text, width=width)
    if len(lines) <= 2:
        return "\n".join(lines)
    # If more than two lines, compress gently: join last lines
    first = lines[0]
    second = " ".join(lines[1:])
    return f"{first}\n{second}"


class OpenAITranslator:
    def __init__(self, model: Optional[str] = None, temperature: float = 0.2):
        if not (_HAS_OPENAI_V1 or _HAS_OPENAI_LEGACY):
            raise RuntimeError("openai package not available. Install openai>=1.0 or 0.28+")
        def _strip_quotes(v: str) -> str:
            v = v.strip()
            if len(v) >= 2 and ((v[0] == v[-1]) and v[0] in ('"', "'")):
                return v[1:-1].strip()
            return v

        env_key = _strip_quotes(os.environ.get("OPENAI_API_KEY", ""))

        def _load_env_key() -> str:
            found = ""
            candidates = ("OPENAI_API_KEY", "OPENAI_KEY", "OPENAI_TOKEN")
            for probe in (".env", os.path.join(os.path.dirname(__file__), "..", ".env")):
                p = os.path.abspath(probe)
                if not os.path.exists(p):
                    continue
                try:
                    try:
                        lines = open(p, "r", encoding="utf-8").read().splitlines()
                    except UnicodeDecodeError:
                        lines = open(p, "r", encoding="latin-1").read().splitlines()
                    for line in lines:
                        s = line.strip()
                        if not s or s.startswith("#"):
                            continue
                        # support optional `export ` prefix
                        if s.lower().startswith("export "):
                            s = s[7:].lstrip()
                        if "=" in s:
                            k, v = s.split("=", 1)
                            k = k.strip(); v = _strip_quotes(v)
                            if k in candidates and v:
                                found = v
                                break
                    if found:
                        break
                except Exception:
                    pass
            return found

        # Always prefer .env if present; otherwise fall back to current process env
        file_key = _load_env_key()
        api_key = file_key or env_key

        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set. Add it to .env or environment.")
        # Project-scoped keys require the modern OpenAI client (>=1.x)
        if api_key.startswith("sk-proj") and not _HAS_OPENAI_V1:
            raise RuntimeError("Project key detected (sk-proj...). Please install openai>=1.0.0.")
        # Prefer modern client when available or when using project keys
        self._use_v1 = _HAS_OPENAI_V1 or api_key.startswith("sk-proj")
        if self._use_v1 and not _HAS_OPENAI_V1:
            raise RuntimeError("Project-scoped key detected. Please install openai>=1.0 to use project keys.")

        if not self._use_v1:
            # Legacy client configuration
            openai.api_key = api_key  # type: ignore

        mdl_env = _strip_quotes(os.environ.get("OPENAI_MODEL", ""))
        self.model = model or (mdl_env if mdl_env else "gpt-3.5-turbo")
        self.temperature = temperature

    def translate_one(self, text: str, source_lang: str, target_lang: str) -> str:
        system = (
            "You are a professional translator. Translate the user's text "
            f"from {source_lang} to {target_lang} in natural, fluent, concise style. "
            "Preserve names, numbers and units. Do not add commentary. Output only the translation."
        )
        if self._use_v1:
            client = _OpenAIClient()  # api key from env
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": text},
                ],
                temperature=self.temperature,
            )
            out = resp.choices[0].message.content or ""
        else:
            resp = openai.ChatCompletion.create(  # type: ignore
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": text},
                ],
                temperature=self.temperature,
            )
            out = resp.choices[0].message["content"].strip()
        return _german_postprocess(out or "")

    def translate_many(self, texts: List[str], source_lang: str, target_lang: str) -> List[str]:
        return [self.translate_one(t, source_lang, target_lang) for t in texts]


class JsonCache:
    def __init__(self, path: str):
        self.path = path
        self._data = {}  # type: ignore
        if os.path.exists(path):
            try:
                self._data = json.load(open(path, "r", encoding="utf-8"))
            except Exception:
                self._data = {}

    def get(self, key: str) -> Optional[str]:
        return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        self._data[key] = value
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)


def _cache_key(provider: str, model: str, src: str, tgt: str, text: str) -> str:
    h = hashlib.sha256()
    h.update((provider + "\0" + model + "\0" + src + "\0" + tgt + "\0" + text).encode("utf-8"))
    return h.hexdigest()


def _distribute_translation_over_blocks(blocks: List[SRTBlock], translated_full: str) -> List[SRTBlock]:
    # Keep original timing; proportionally allocate translated text chars into each original block
    src_total = sum(len(b.text) for b in blocks) or 1
    translated_full = _normalize_whitespace(translated_full)
    words = translated_full.split()

    # Prepare target lengths per block (approximate)
    tgt_total = len(translated_full)
    targets = [max(1, round(tgt_total * len(b.text) / src_total)) for b in blocks]
    # Adjust rounding to exact total
    diff = tgt_total - sum(targets)
    i = 0
    while diff != 0 and blocks:
        step = 1 if diff > 0 else -1
        targets[i % len(targets)] += step
        diff -= step
        i += 1

    # Fill blocks word by word according to targets
    out_blocks: List[SRTBlock] = []
    cur = []
    cur_len = 0
    widx = 0
    for bi, b in enumerate(blocks):
        cur_target = targets[bi]
        cur.clear()
        cur_len = 0
        while widx < len(words) and (cur_len + len(words[widx]) + (1 if cur else 0)) <= cur_target:
            w = words[widx]
            cur.append(w)
            cur_len += len(w) + (1 if cur_len > 0 else 0)
            widx += 1
        text = " ".join(cur).strip()
        out_blocks.append(SRTBlock(b.index, b.start, b.end, _wrap_two_lines(text)))

    # If any words remain, append them to the last block
    if widx < len(words) and out_blocks:
        last = out_blocks[-1]
        extra = (last.text + " " + " ".join(words[widx:])).strip()
        out_blocks[-1] = SRTBlock(last.index, last.start, last.end, _wrap_two_lines(extra))
    return out_blocks


def translate_srt(
    input_path: str,
    source_lang: str = "en",
    target_lang: str = "de",
    provider: str = "openai",
    model: Optional[str] = None,
    keep_timing: bool = True,
    cache_path: Optional[str] = None,
) -> str:
    blocks = parse_srt(input_path)
    if not blocks:
        raise ValueError("No valid SRT entries found.")

    groups = _split_into_sentence_groups(blocks)
    texts = [g[2] for g in groups]

    cache = JsonCache(cache_path or os.path.join(os.path.dirname(input_path) or ".", "smart_translation_cache.json"))

    def translate_text(t: str) -> str:
        prov = provider.lower()
        if prov == "openai":
            mdl = model or os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")
            key = _cache_key(prov, mdl, source_lang, target_lang, t)
            cached = cache.get(key)
            if cached:
                return cached
            translator = OpenAITranslator(model=mdl)
            out = translator.translate_one(t, source_lang, target_lang)
            cache.set(key, out)
            return out
        else:
            raise RuntimeError(f"Unsupported provider: {provider}")

    translated_groups = [translate_text(t) for t in texts]
    translated_full = _normalize_whitespace(" ".join(translated_groups))

    if keep_timing:
        out_blocks = _distribute_translation_over_blocks(blocks, translated_full)
    else:
        # Reflow groups back into the corresponding block ranges (first line of each block)
        out_blocks = blocks[:]
        for (start_i, end_i, _), t in zip(groups, translated_groups):
            for bi in range(start_i, end_i + 1):
                out_blocks[bi] = SRTBlock(out_blocks[bi].index, out_blocks[bi].start, out_blocks[bi].end, _wrap_two_lines(t))

    name, ext = os.path.splitext(input_path)
    out_path = f"{name}_translated_openai{ext}"
    write_srt(out_path, out_blocks)
    return out_path


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Translate SRT using OpenAI with sentence grouping and timing preservation.")
    p.add_argument("input", help="Path to input .srt")
    p.add_argument("source", help="Source language code, e.g., en")
    p.add_argument("target", help="Target language code, e.g., de")
    p.add_argument("--provider", default="openai", choices=["openai"], help="Translation provider")
    p.add_argument("--model", default=None, help="OpenAI model (default from OPENAI_MODEL or gpt-3.5-turbo)")
    p.add_argument("--no-keep-timing", action="store_true", help="Do not preserve original timing (reflow by groups)")
    args = p.parse_args()

    out = translate_srt(
        args.input,
        source_lang=args.source,
        target_lang=args.target,
        provider=args.provider,
        model=args.model,
        keep_timing=not args.no_keep_timing,
    )
    print(out)
