import json
import re
from collections import defaultdict, OrderedDict
from pathlib import Path


CONFIG_DIR = Path(__file__).resolve().parent
REPO_DIR = CONFIG_DIR.parent.parent
LANG_FILE = REPO_DIR / "Source" / "vaultpatcher" / "i18n" / "en_us.json"
RULE_FILE = CONFIG_DIR / "vaultpatcher_asm" / "Prominent-GLOBAL-MC1.20.1-4.0.0.json"
MAPPING_FILE = CONFIG_DIR / "mapping.txt"


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=OrderedDict)


def dump_json(path, value, indent):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=indent) + "\n").encode("utf-8"))


def parse_mapping():
    mapping = {}
    for line in MAPPING_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or " -> " not in line:
            continue
        source, target = line.split(" -> ", 1)
        match = re.fullmatch(r"\\u([0-9A-Fa-f]{4})", target)
        if not match:
            raise ValueError(f"Invalid mapping target: {line}")
        mapping[source] = chr(int(match.group(1), 16))
    return mapping


def map_private_use(text, mapping):
    return "".join(mapping.get(char, char) for char in text)


def module_prefix(owner):
    owner = owner.replace("/", ".")
    known = (
        ("elocindev.prominent_talents.", "prominenttalents"),
        ("elocindev.prominentbase.", "prominentbase"),
        ("elocindev.prominent.settings.", "prominentsettings"),
        ("elocindev.prominent.", "prominent"),
    )
    for package, prefix in known:
        if owner.startswith(package):
            return prefix
    parts = owner.split(".")
    return re.sub(r"[^a-z0-9]+", "", (parts[1] if len(parts) > 1 else parts[0]).lower())


def class_slug(owner):
    simple = owner.replace("/", ".").split(".")[-1]
    return re.sub(r"[^a-z0-9]+", "", simple.lower())


def initial_counters(translations):
    counters = defaultdict(int)
    pattern = re.compile(r"^vp\\.([a-z0-9]+)\\.([a-z0-9]+)\\.(\\d+)$")
    for key in translations:
        match = pattern.match(key)
        if match:
            counters[(match.group(1), match.group(2))] = max(
                counters[(match.group(1), match.group(2))], int(match.group(3))
            )
    return counters


def main():
    translations = load_json(LANG_FILE)
    data = load_json(RULE_FILE)
    mapping = parse_mapping()
    new_translations = OrderedDict()
    used_keys = set(translations)
    counters = initial_counters(translations)

    for item in data:
        target = item.get("target_class")
        if not target or "pairs" not in item:
            continue
        prefix = module_prefix(target.get("name", ""))
        slug = class_slug(target.get("name", ""))
        for pair in item["pairs"]:
            value = pair.get("value", "")
            if not value:
                continue
            if value.startswith("vp."):
                # Existing keys are retained. If an old rule references a
                # missing key, recover the English source from its exact pair
                # key instead of leaving a broken i18n closure.
                if value not in translations and value not in new_translations:
                    new_translations[value] = map_private_use(pair.get("key", ""), mapping)
                continue

            # This script is fed a Duper-style rule whose raw value is the
            # original hardcoded string. Internal lookup keys are intentionally
            # not filtered here: the caller controls the candidate rule, while
            # the module/class prefix remains deterministic for every owner.
            counters[(prefix, slug)] += 1
            key = f"vp.{prefix}.{slug}.{counters[(prefix, slug)]}"
            while key in used_keys or key in new_translations:
                counters[(prefix, slug)] += 1
                key = f"vp.{prefix}.{slug}.{counters[(prefix, slug)]}"
            pair["value"] = key
            new_translations[key] = map_private_use(value, mapping)

    translations.update(new_translations)
    dump_json(LANG_FILE, translations, indent=4)
    dump_json(RULE_FILE, data, indent=2)
    print(f"Processed {len(new_translations)} Vault Patcher i18n entries")


if __name__ == "__main__":
    main()
