"""标题 → 关键词集合。连续名词合并成短语，同时保留 ≥2 字的单个名词。"""
import re, unicodedata
from janome.tokenizer import Tokenizer
from . import config

_tok = Tokenizer()
_SKIP_SUB = {"数", "接尾", "非自立", "代名詞", "副詞可能", "接続詞的"}
_NUM = re.compile(r"^[\d０-９.,%％]+$")
_HIRA = re.compile(r"^[぀-ゟ]+$")  # 纯平假名碎片（きん/ぐに）不要

def _is_noun(t):
    pos = t.part_of_speech.split(",")
    return pos[0] == "名詞" and pos[1] not in _SKIP_SUB and not _NUM.match(t.surface) and not _HIRA.match(t.surface)

def extract(title: str) -> set[str]:
    title = unicodedata.normalize("NFKC", title)
    out, run = set(), []
    def flush():
        if not run:
            return
        for w in run:
            if len(w) >= config.MIN_LEN and w not in config.STOPWORDS:
                out.add(w)
        if 1 < len(run) <= config.MAX_COMPOUND:
            comp = "".join(run)
            if comp not in config.STOPWORDS:
                out.add(comp)
        run.clear()
    for t in _tok.tokenize(title):
        if _is_noun(t):
            run.append(t.surface)
        else:
            flush()
    flush()
    return out
