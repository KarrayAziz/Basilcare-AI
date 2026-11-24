import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit

PUBLIC_SOURCE_URLS = {
    "https://plants.ces.ncsu.edu/plants/ocimum-basilicum/",
    "https://extension.usu.edu/yardandgarden/research/basil-in-the-garden",
}

DEFAULT_CORPUS = Path(__file__).resolve().parents[1] / "corpus" / "knowledge.json"
STOP = set("a an and are as at be been basil by can could do does for from grow growing has have how i in is it its me my of on or our please plant plants should that the their them this to was we what when which why will with would you your".split())
ALIASES = {"sunlight": "light", "lighting": "light", "sun": "light", "pruning": "prune",
           "pinching": "pinch", "harvesting": "harvest", "germinate": "germination",
           "germinating": "germination", "sprout": "germination", "diseases": "disease",
           "pests": "pest", "seeds": "seed", "temperatures": "temperature"}


def tokens(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    return [ALIASES.get(word, word) for word in re.findall(r"[a-z0-9]+", text) if word not in STOP]


class Knowledge:
    def __init__(self, path=DEFAULT_CORPUS, public_only=False):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("version"), str) or not data["version"]:
            raise ValueError("corpus needs a version")
        if (not isinstance(data.get("sources"), list) or not isinstance(data.get("passages"), list)
                or not isinstance(data.get("notes_license"), str)):
            raise ValueError("corpus needs source/passage lists and a notes licence")
        if any(not isinstance(item, dict) for item in data["sources"] + data["passages"]):
            raise ValueError("sources and passages must be objects")
        self.public_only = public_only
        if public_only:
            # Filter before indexing/fingerprinting: project notes cannot reach the cloud provider.
            data = {**data, "sources": [s for s in data["sources"] if s.get("url") in PUBLIC_SOURCE_URLS]}
            allowed = {s.get("id") for s in data["sources"] if isinstance(s.get("id"), str)}
            data["passages"] = [p for p in data["passages"]
                                if p.get("scope") == "garden" and p.get("source_id") in allowed]
        self.version = data["version"] + ("-public-garden" if public_only else "")
        self.fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        self.sources, self.passages = {}, {}
        for source in data["sources"]:
            if (not isinstance(source, dict) or not isinstance(source.get("id"), str)
                    or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", source["id"])
                    or source["id"] in self.sources or not isinstance(source.get("title"), str)
                    or not isinstance(source.get("url"), str)
                    or urlsplit(source["url"]).scheme != "https" or not urlsplit(source["url"]).hostname):
                raise ValueError("invalid or duplicate source")
            self.sources[source["id"]] = source
        for passage in data["passages"]:
            if (not isinstance(passage, dict) or not isinstance(passage.get("id"), str)
                    or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", passage["id"])
                    or passage["id"] in self.passages
                    or not isinstance(passage.get("source_id"), str) or passage["source_id"] not in self.sources
                    or not isinstance(passage.get("text"), str) or not passage["text"].strip()
                    or not isinstance(passage.get("title"), str)
                    or not isinstance(passage.get("keywords"), list)
                    or any(not isinstance(word, str) for word in passage["keywords"])
                    or not isinstance(passage.get("scope"), str)
                    or passage["scope"] not in {"garden", "project", "hydroponic"}):
                raise ValueError("invalid or duplicate passage")
            self.passages[passage["id"]] = passage
        if not self.passages:
            raise ValueError("corpus is empty")
        self.index = {key: tokens(p["title"] + " " + " ".join(p["keywords"]) + " " + p["text"])
                      for key, p in self.passages.items()}

    def retrieve(self, question, limit=4):
        query = set(tokens(question))
        if not query:
            return []
        # Garden soil/seed advice must not become a hydroponic pH/EC/temperature target.
        hydroponic = bool(re.search(r"\b(ph|ec|hydroponic\w*|reservoir)\b|nutrient solution|water temperature",
                                    question, re.IGNORECASE))
        size = len(self.index)
        average = sum(map(len, self.index.values())) / size
        ranked = []
        for key, words in self.index.items():
            passage = self.passages[key]
            if hydroponic and passage["scope"] != "hydroponic":
                continue
            score = 0.0
            for word in query:
                count = words.count(word)
                if count:
                    frequency = sum(word in document for document in self.index.values())
                    inverse = math.log(1 + (size - frequency + 0.5) / (frequency + 0.5))
                    score += inverse * count * 2.5 / (count + 1.5 * (0.25 + 0.75 * len(words) / average))
            if score > 0:
                ranked.append((score, key))
        ranked.sort(key=lambda pair: (-pair[0], pair[1]))
        return [self.passages[key] for _, key in ranked[:limit]]
