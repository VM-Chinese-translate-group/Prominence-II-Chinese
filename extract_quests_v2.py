from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

try:
    import ftb_snbt_lib
    from ftb_snbt_lib.token import lexer as ftb_lexer
except ImportError as exc:  # pragma: no cover - exercised by the command line only
    raise SystemExit(
        "Missing dependency: ftb-snbt-lib==0.4.0. "
        "Install it with: python -m pip install -r requirements.txt"
    ) from exc


ID_PATTERN = re.compile(r"[0-9A-Fa-f]{16}\Z")
SAFE_FILENAME_PATTERN = re.compile(r"[A-Za-z0-9_.-]+\Z")
SIMPLE_REFERENCE_PATTERN = re.compile(r"\{([^{}]+)\}\Z")

MANAGED_PREFIXES = (
    "ftbquests.chapter.",
    "ftbquests.chapter_group.",
    "ftbquests.reward_table.",
)
MANAGED_EXACT_KEYS = {"ftbquests.title", "ftbquests.lock_message"}
DISPLAY_FIELDS = ("title", "subtitle", "description")


class ExtractionError(Exception):
    """Raised when preflight validation prevents a safe extraction."""


class DuplicateJsonKey(ValueError):
    """Raised when a JSON object contains a duplicate key."""


@dataclass(frozen=True)
class Token:
    type: str
    value: Any
    start: int
    end: int


@dataclass
class Member:
    key: str
    value: "Node"


@dataclass
class Node:
    kind: str
    start: int
    end: int
    value: Any = None
    members: list[Member] = field(default_factory=list)
    items: list["Node"] = field(default_factory=list)

    def get(self, key: str) -> "Node | None":
        if self.kind != "compound":
            return None
        for member in self.members:
            if member.key == key:
                return member.value
        return None


@dataclass
class Document:
    path: Path
    relative_path: str
    kind: str
    stem: str
    text: str
    bom: bool
    root: Node


@dataclass(frozen=True)
class Target:
    node: Node
    key: str
    context: str
    category: str


@dataclass
class LanguageFormat:
    bom: bool = False
    newline: str = "\n"
    indent: int | str | None = 2
    trailing_newline: bool = True


@dataclass
class Report:
    extracted: Counter[str] = field(default_factory=Counter)
    rehydrated: Counter[str] = field(default_factory=Counter)
    skipped_empty: Counter[str] = field(default_factory=Counter)
    skipped_control: Counter[str] = field(default_factory=Counter)
    changed_snbt_files: int = 0
    language_changed: bool = False

    @property
    def extracted_total(self) -> int:
        return sum(self.extracted.values())

    @property
    def rehydrated_total(self) -> int:
        return sum(self.rehydrated.values())


def decode_snbt_string(raw: str) -> str:
    """Decode the two escape forms understood by ftb-snbt-lib."""
    if len(raw) < 2 or raw[0] != '"' or raw[-1] != '"':
        raise ExtractionError(f"Invalid quoted SNBT string: {raw!r}")

    result: list[str] = []
    index = 1
    while index < len(raw) - 1:
        char = raw[index]
        if char == "\\" and index + 1 < len(raw) - 1:
            following = raw[index + 1]
            if following in {'"', "\\"}:
                result.append(following)
            else:
                result.extend(("\\", following))
            index += 2
        else:
            result.append(char)
            index += 1
    return "".join(result)


def encode_snbt_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _scan_quoted_end(source: str, start: int) -> int:
    index = start + 1
    while index < len(source):
        if source[index] == "\\":
            index += 2
        elif source[index] == '"':
            return index + 1
        else:
            index += 1
    raise ExtractionError(f"Unterminated SNBT string at character {start}")


def _scan_scalar_end(source: str, start: int) -> int:
    index = start
    while index < len(source) and source[index] not in " \t\r\n,]}:;":
        index += 1
    return index


def tokenize_snbt(source: str) -> list[Token]:
    """Tokenize FTB SNBT while retaining exact character spans."""
    ftb_lexer.lineno = 1
    ftb_lexer.level = 0
    ftb_lexer.input(source)
    tokens: list[Token] = []
    for raw_token in ftb_lexer:
        start = raw_token.lexpos
        if raw_token.type == "STRING":
            end = _scan_quoted_end(source, start)
            value = decode_snbt_string(source[start:end])
        elif raw_token.type in {
            "LBRACE",
            "RBRACE",
            "LBRACKET",
            "RBRACKET",
            "COLON",
            "SEMICOLON",
            "COMMA",
        }:
            end = start + 1
            value = source[start:end]
        elif raw_token.type == "NAME":
            value = str(raw_token.value)
            end = start + len(value)
        else:
            end = _scan_scalar_end(source, start)
            value = source[start:end]
        tokens.append(Token(raw_token.type, value, start, end))
    return tokens


class PositionParser:
    """Small positional parser for the grammar already accepted by ftb-snbt-lib."""

    def __init__(self, source: str):
        self.source = source
        self.tokens = tokenize_snbt(source)
        self.index = 0

    def current(self) -> Token | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def advance(self) -> Token:
        token = self.current()
        if token is None:
            raise ExtractionError("Unexpected end of SNBT")
        self.index += 1
        return token

    def expect(self, token_type: str) -> Token:
        token = self.advance()
        if token.type != token_type:
            raise ExtractionError(
                f"Expected {token_type} at character {token.start}, got {token.type}"
            )
        return token

    def parse(self) -> Node:
        if not self.tokens:
            raise ExtractionError("SNBT file is empty")
        root = self.parse_value()
        if self.current() is not None:
            token = self.current()
            raise ExtractionError(
                f"Unexpected {token.type} at character {token.start} after root value"
            )
        return root

    def parse_value(self) -> Node:
        token = self.current()
        if token is None:
            raise ExtractionError("Unexpected end of SNBT value")
        if token.type == "LBRACE":
            return self.parse_compound()
        if token.type == "LBRACKET":
            return self.parse_list()
        token = self.advance()
        kind = "string" if token.type == "STRING" else "scalar"
        return Node(kind, token.start, token.end, token.value)

    def parse_compound(self) -> Node:
        opening = self.expect("LBRACE")
        members: list[Member] = []
        while True:
            token = self.current()
            if token is None:
                raise ExtractionError(
                    f"Unterminated compound starting at character {opening.start}"
                )
            if token.type == "RBRACE":
                closing = self.advance()
                return Node("compound", opening.start, closing.end, members=members)
            if token.type == "COMMA":
                self.advance()
                continue
            if token.type not in {"NAME", "STRING"}:
                raise ExtractionError(
                    f"Expected compound key at character {token.start}, got {token.type}"
                )
            key = str(self.advance().value)
            self.expect("COLON")
            members.append(Member(key, self.parse_value()))

    def parse_list(self) -> Node:
        opening = self.expect("LBRACKET")
        items: list[Node] = []
        while True:
            token = self.current()
            if token is None:
                raise ExtractionError(
                    f"Unterminated list starting at character {opening.start}"
                )
            if token.type == "RBRACKET":
                closing = self.advance()
                return Node("list", opening.start, closing.end, items=items)
            if token.type in {"COMMA", "SEMICOLON"}:
                self.advance()
                continue
            items.append(self.parse_value())


def parse_position_tree(source: str) -> Node:
    return PositionParser(source).parse()


def is_managed_key(key: str) -> bool:
    return key in MANAGED_EXACT_KEYS or key.startswith(MANAGED_PREFIXES)


def managed_reference(value: str) -> str | None:
    match = SIMPLE_REFERENCE_PATTERN.fullmatch(value.strip())
    if match and is_managed_key(match.group(1)):
        return match.group(1)
    return None


def target_reference(target: Target, value: str) -> str | None:
    """Return the managed key referenced by a target's field syntax."""
    stripped = value.strip()
    if target.category == "image" and is_managed_key(stripped):
        return stripped
    return managed_reference(value)


def is_full_control_or_reference(value: str) -> bool:
    stripped = value.strip()
    return bool(stripped.startswith("{") and stripped.endswith("}") and "{" not in stripped[1:-1])


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKey(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json_component(value: str, context: str) -> tuple[Any, bool] | None:
    stripped = value.strip()
    if not stripped.startswith(("[", "{")):
        return None
    try:
        parsed = json.loads(stripped, object_pairs_hook=_json_object_without_duplicates)
    except DuplicateJsonKey as exc:
        raise ExtractionError(f"{context}: {exc}") from exc
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, (dict, list)):
        return None
    spaced = bool(re.search(r"[, :]\s+", stripped))
    return parsed, spaced


def dump_json_component(component: Any, spaced: bool) -> str:
    separators = (", ", ": ") if spaced else (",", ":")
    return json.dumps(component, ensure_ascii=False, separators=separators)


def apply_replacements(source: str, replacements: Iterable[tuple[int, int, str]]) -> str:
    ordered = sorted(replacements, key=lambda item: item[0], reverse=True)
    previous_start = len(source) + 1
    result = source
    for start, end, replacement in ordered:
        if not (0 <= start <= end <= len(source)):
            raise ExtractionError(f"Invalid replacement span: {start}:{end}")
        if end > previous_start:
            raise ExtractionError(f"Overlapping replacement span: {start}:{end}")
        result = result[:start] + replacement + result[end:]
        previous_start = start
    return result


def _read_utf8(path: Path) -> tuple[str, bool]:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        return raw.decode("utf-8-sig" if bom else "utf-8"), bom
    except UnicodeDecodeError as exc:
        raise ExtractionError(f"{path}: file is not valid UTF-8: {exc}") from exc


def _encode_utf8(text: str, bom: bool) -> bytes:
    raw = text.encode("utf-8")
    return (b"\xef\xbb\xbf" + raw) if bom else raw


def _document_kind(path: Path, quests_dir: Path) -> tuple[str, str]:
    relative = path.relative_to(quests_dir)
    if relative.as_posix() == "data.snbt":
        return "data", path.stem
    if relative.as_posix() == "chapter_groups.snbt":
        return "chapter_groups", path.stem
    if relative.parts and relative.parts[0] == "chapters":
        return "chapter", path.stem
    if relative.parts and relative.parts[0] == "reward_tables":
        return "reward_table", path.stem
    return "other", path.stem


def load_documents(ftbquests_root: Path) -> list[Document]:
    quests_dir = ftbquests_root / "quests"
    required = (quests_dir / "data.snbt", quests_dir / "chapter_groups.snbt")
    missing = [str(path) for path in required if not path.is_file()]
    chapters_dir = quests_dir / "chapters"
    if not chapters_dir.is_dir():
        missing.append(str(chapters_dir))
    if missing:
        raise ExtractionError("Missing required FTB Quests paths:\n- " + "\n- ".join(missing))

    paths = [*required]
    paths.extend(sorted(chapters_dir.glob("*.snbt"), key=lambda path: path.name.lower()))
    reward_tables_dir = quests_dir / "reward_tables"
    if reward_tables_dir.is_dir():
        paths.extend(sorted(reward_tables_dir.glob("*.snbt"), key=lambda path: path.name.lower()))

    documents: list[Document] = []
    errors: list[str] = []
    seen_names: set[tuple[str, str]] = set()
    for path in paths:
        kind, stem = _document_kind(path, quests_dir)
        if kind in {"chapter", "reward_table"}:
            if not SAFE_FILENAME_PATTERN.fullmatch(stem):
                errors.append(f"{path}: unsafe filename for translation key: {stem!r}")
            name_key = (kind, stem)
            if name_key in seen_names:
                errors.append(f"{path}: duplicate {kind} filename: {stem}")
            seen_names.add(name_key)
        try:
            text, bom = _read_utf8(path)
            ftb_snbt_lib.loads(text)
            root = parse_position_tree(text)
            if root.kind != "compound":
                raise ExtractionError("root SNBT value must be a compound")
            documents.append(
                Document(
                    path=path,
                    relative_path=path.relative_to(ftbquests_root).as_posix(),
                    kind=kind,
                    stem=stem,
                    text=text,
                    bom=bom,
                    root=root,
                )
            )
        except Exception as exc:
            errors.append(f"{path}: {exc}")
    if errors:
        raise ExtractionError("SNBT preflight failed:\n- " + "\n- ".join(errors))
    return documents


def reparse_document(document: Document, text: str) -> Document:
    try:
        ftb_snbt_lib.loads(text)
        root = parse_position_tree(text)
    except Exception as exc:
        raise ExtractionError(f"{document.path}: generated invalid SNBT: {exc}") from exc
    return Document(
        document.path,
        document.relative_path,
        document.kind,
        document.stem,
        text,
        document.bom,
        root,
    )


def _require_compound(node: Node, context: str) -> Node:
    if node.kind != "compound":
        raise ExtractionError(f"{context}: expected compound, got {node.kind}")
    return node


def _optional_list(compound: Node, key: str, context: str) -> list[Node]:
    node = compound.get(key)
    if node is None:
        return []
    if node.kind != "list":
        raise ExtractionError(f"{context}.{key}: expected list, got {node.kind}")
    return node.items


def _field_targets(
    compound: Node,
    field_name: str,
    key_base: str,
    context: str,
    category: str,
) -> list[Target]:
    node = compound.get(field_name)
    if node is None:
        return []
    if node.kind == "string":
        return [Target(node, f"{key_base}.{field_name}", f"{context}.{field_name}", category)]
    if node.kind == "list":
        targets: list[Target] = []
        for index, item in enumerate(node.items):
            if item.kind != "string":
                raise ExtractionError(
                    f"{context}.{field_name}[{index}]: expected string, got {item.kind}"
                )
            targets.append(
                Target(
                    item,
                    f"{key_base}.{field_name}{index}",
                    f"{context}.{field_name}[{index}]",
                    category,
                )
            )
        return targets
    raise ExtractionError(f"{context}.{field_name}: expected string or list, got {node.kind}")


def _display_targets(
    compound: Node, key_base: str, context: str, category: str
) -> list[Target]:
    targets: list[Target] = []
    for field_name in DISPLAY_FIELDS:
        targets.extend(_field_targets(compound, field_name, key_base, context, category))
    return targets


def _has_visible_candidate(targets: Iterable[Target]) -> bool:
    return any(str(target.node.value).strip() for target in targets)


class IdRegistry:
    def __init__(self) -> None:
        self.seen: dict[str, dict[str, str]] = {}

    def require(self, compound: Node, kind: str, context: str) -> str:
        node = compound.get("id")
        if node is None or node.kind != "string":
            raise ExtractionError(f"{context}: missing string id")
        entity_id = str(node.value)
        if not ID_PATTERN.fullmatch(entity_id):
            raise ExtractionError(
                f"{context}: invalid id {entity_id!r}; expected exactly 16 hexadecimal characters"
            )
        normalized = entity_id.upper()
        previous = self.seen.setdefault(kind, {}).get(normalized)
        if previous is not None:
            raise ExtractionError(
                f"{context}: duplicate {kind} id {entity_id}; first seen at {previous}"
            )
        self.seen[kind][normalized] = context
        return entity_id


def discover_targets(documents: Iterable[Document]) -> list[tuple[Document, list[Target]]]:
    registry = IdRegistry()
    discovered: list[tuple[Document, list[Target]]] = []

    for document in documents:
        root = _require_compound(document.root, document.relative_path)
        targets: list[Target] = []

        if document.kind == "data":
            for field_name in ("title", "lock_message"):
                targets.extend(
                    _field_targets(
                        root,
                        field_name,
                        "ftbquests",
                        document.relative_path,
                        "data",
                    )
                )

        elif document.kind == "chapter_groups":
            groups = _optional_list(root, "chapter_groups", document.relative_path)
            for index, raw_group in enumerate(groups):
                context = f"{document.relative_path}.chapter_groups[{index}]"
                group = _require_compound(raw_group, context)
                group_id = registry.require(group, "chapter_group", context)
                targets.extend(
                    _field_targets(
                        group,
                        "title",
                        f"ftbquests.chapter_group.{group_id}",
                        context,
                        "chapter_group",
                    )
                )

        elif document.kind == "chapter":
            chapter_base = f"ftbquests.chapter.{document.stem}"
            targets.extend(
                _field_targets(
                    root, "title", chapter_base, document.relative_path, "chapter"
                )
            )
            targets.extend(
                _field_targets(
                    root, "subtitle", chapter_base, document.relative_path, "chapter"
                )
            )

            for image_index, raw_image in enumerate(
                _optional_list(root, "images", document.relative_path)
            ):
                context = f"{document.relative_path}.images[{image_index}]"
                image = _require_compound(raw_image, context)
                targets.extend(
                    _field_targets(
                        image,
                        "hover",
                        f"{chapter_base}.image{image_index}",
                        context,
                        "image",
                    )
                )

            for quest_index, raw_quest in enumerate(
                _optional_list(root, "quests", document.relative_path)
            ):
                quest_context = f"{document.relative_path}.quests[{quest_index}]"
                quest = _require_compound(raw_quest, quest_context)
                quest_id = registry.require(quest, "quest", quest_context)
                quest_base = f"{chapter_base}.quest.{quest_id}"
                targets.extend(_display_targets(quest, quest_base, quest_context, "quest"))

                for task_index, raw_task in enumerate(
                    _optional_list(quest, "tasks", quest_context)
                ):
                    task_context = f"{quest_context}.tasks[{task_index}]"
                    task = _require_compound(raw_task, task_context)
                    task_id = registry.require(task, "task", task_context)
                    targets.extend(
                        _display_targets(
                            task,
                            f"{quest_base}.task.{task_id}",
                            task_context,
                            "task",
                        )
                    )

                for reward_index, raw_reward in enumerate(
                    _optional_list(quest, "rewards", quest_context)
                ):
                    reward_context = f"{quest_context}.rewards[{reward_index}]"
                    reward = _require_compound(raw_reward, reward_context)
                    reward_id = registry.require(reward, "reward", reward_context)
                    targets.extend(
                        _display_targets(
                            reward,
                            f"{quest_base}.reward.{reward_id}",
                            reward_context,
                            "reward",
                        )
                    )

        elif document.kind == "reward_table":
            table_base = f"ftbquests.reward_table.{document.stem}"
            targets.extend(
                _field_targets(
                    root,
                    "title",
                    table_base,
                    document.relative_path,
                    "reward_table",
                )
            )
            for reward_index, raw_reward in enumerate(
                _optional_list(root, "rewards", document.relative_path)
            ):
                context = f"{document.relative_path}.rewards[{reward_index}]"
                reward = _require_compound(raw_reward, context)
                candidate_targets = _display_targets(
                    reward, table_base, context, "reward_table_reward"
                )
                if _has_visible_candidate(candidate_targets):
                    reward_id = registry.require(reward, "reward", context)
                    targets.extend(
                        _display_targets(
                            reward,
                            f"{table_base}.reward.{reward_id}",
                            context,
                            "reward_table_reward",
                        )
                    )

        discovered.append((document, targets))

    return discovered


def _replace_ordered_key(
    mapping: dict[str, Any], old_key: str, new_key: str, new_value: Any
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in mapping.items():
        if key == old_key:
            result[new_key] = new_value
        else:
            result[key] = value
    return result


def _rehydrate_component(
    value: Any,
    language: dict[str, Any],
    missing: list[str],
    context: str,
) -> tuple[Any, int]:
    if isinstance(value, str):
        reference = managed_reference(value)
        if reference is None:
            return value, 0
        if reference not in language:
            missing.append(f"{context}: {reference}")
            return value, 0
        translated = language[reference]
        if not isinstance(translated, str):
            missing.append(f"{context}: {reference} is not a string in the language file")
            return value, 0
        return translated, 1

    if isinstance(value, list):
        result: list[Any] = []
        count = 0
        for index, item in enumerate(value):
            transformed, item_count = _rehydrate_component(
                item, language, missing, f"{context}[{index}]"
            )
            result.append(transformed)
            count += item_count
        return result, count

    if not isinstance(value, dict):
        return value, 0

    result = dict(value)
    count = 0
    translate = result.get("translate")
    if isinstance(translate, str) and is_managed_key(translate):
        if "text" in result:
            missing.append(f"{context}: component contains both text and translate")
        elif translate not in language:
            missing.append(f"{context}: {translate}")
        elif not isinstance(language[translate], str):
            missing.append(f"{context}: {translate} is not a string in the language file")
        else:
            result = _replace_ordered_key(result, "translate", "text", language[translate])
            count += 1

    for key in ("extra", "with", "separator"):
        if key in result:
            result[key], item_count = _rehydrate_component(
                result[key], language, missing, f"{context}.{key}"
            )
            count += item_count

    hover = result.get("hoverEvent")
    if isinstance(hover, dict) and hover.get("action") == "show_text":
        hover = dict(hover)
        for key in ("contents", "value"):
            if key in hover:
                hover[key], item_count = _rehydrate_component(
                    hover[key], language, missing, f"{context}.hoverEvent.{key}"
                )
                count += item_count
        result["hoverEvent"] = hover

    return result, count


def rehydrate_documents(
    documents: list[Document], language: dict[str, Any], report: Report
) -> list[Document]:
    missing: list[str] = []
    transformed_documents: list[Document] = []

    for document, targets in discover_targets(documents):
        replacements: list[tuple[int, int, str]] = []
        for target in targets:
            value = str(target.node.value)
            reference = target_reference(target, value)
            if reference is not None:
                if reference not in language:
                    missing.append(f"{target.context}: {reference}")
                    continue
                translated = language[reference]
                if not isinstance(translated, str):
                    missing.append(
                        f"{target.context}: {reference} is not a string in the language file"
                    )
                    continue
                replacements.append(
                    (target.node.start, target.node.end, encode_snbt_string(translated))
                )
                report.rehydrated[target.category] += 1
                continue

            parsed_component = parse_json_component(value, target.context)
            if parsed_component is None:
                continue
            component, spaced = parsed_component
            transformed, count = _rehydrate_component(
                component, language, missing, target.context
            )
            if count:
                replacements.append(
                    (
                        target.node.start,
                        target.node.end,
                        encode_snbt_string(dump_json_component(transformed, spaced)),
                    )
                )
                report.rehydrated[target.category] += count

        new_text = apply_replacements(document.text, replacements)
        transformed_documents.append(reparse_document(document, new_text))

    if missing:
        unique_missing = list(dict.fromkeys(missing))
        raise ExtractionError(
            "Language rehydration preflight failed:\n- " + "\n- ".join(unique_missing)
        )
    return transformed_documents


def _add_translation(
    translations: dict[str, str], key: str, value: str, context: str
) -> None:
    if key in translations:
        raise ExtractionError(
            f"{context}: generated duplicate translation key {key}; "
            f"existing value={translations[key]!r}, new value={value!r}"
        )
    translations[key] = value


def _extractable_literal(value: str) -> tuple[bool, str]:
    if not value.strip():
        return False, "empty"
    if is_full_control_or_reference(value):
        return False, "control"
    return True, ""


def _extract_component(
    value: Any,
    key_base: str,
    translations: dict[str, str],
    context: str,
    counter: list[int],
    report: Report,
    category: str,
) -> tuple[Any, int]:
    if isinstance(value, str):
        allowed, reason = _extractable_literal(value)
        if not allowed:
            if reason == "empty":
                report.skipped_empty[category] += 1
            else:
                report.skipped_control[category] += 1
            return value, 0
        key = f"{key_base}.text{counter[0]}"
        counter[0] += 1
        _add_translation(translations, key, value, context)
        report.extracted[category] += 1
        return {"translate": key}, 1

    if isinstance(value, list):
        result: list[Any] = []
        count = 0
        for index, item in enumerate(value):
            transformed, item_count = _extract_component(
                item,
                key_base,
                translations,
                f"{context}[{index}]",
                counter,
                report,
                category,
            )
            result.append(transformed)
            count += item_count
        return result, count

    if not isinstance(value, dict):
        return value, 0

    result = dict(value)
    count = 0
    text_value = result.get("text")
    if isinstance(text_value, str):
        allowed, reason = _extractable_literal(text_value)
        if allowed:
            if "translate" in result:
                raise ExtractionError(f"{context}: component contains both text and translate")
            key = f"{key_base}.text{counter[0]}"
            counter[0] += 1
            _add_translation(translations, key, text_value, f"{context}.text")
            result = _replace_ordered_key(result, "text", "translate", key)
            report.extracted[category] += 1
            count += 1
        elif reason == "empty":
            report.skipped_empty[category] += 1
        else:
            report.skipped_control[category] += 1

    for key in ("extra", "with", "separator"):
        if key in result:
            result[key], item_count = _extract_component(
                result[key],
                key_base,
                translations,
                f"{context}.{key}",
                counter,
                report,
                category,
            )
            count += item_count

    hover = result.get("hoverEvent")
    if isinstance(hover, dict) and hover.get("action") == "show_text":
        hover = dict(hover)
        for key in ("contents", "value"):
            if key in hover:
                hover[key], item_count = _extract_component(
                    hover[key],
                    key_base,
                    translations,
                    f"{context}.hoverEvent.{key}",
                    counter,
                    report,
                    category,
                )
                count += item_count
        result["hoverEvent"] = hover

    return result, count


def extract_documents(
    documents: list[Document], report: Report
) -> tuple[list[Document], dict[str, str]]:
    translations: dict[str, str] = {}
    transformed_documents: list[Document] = []

    for document, targets in discover_targets(documents):
        replacements: list[tuple[int, int, str]] = []
        for target in targets:
            value = str(target.node.value)
            parsed_component = parse_json_component(value, target.context)
            if parsed_component is not None:
                component, spaced = parsed_component
                transformed, count = _extract_component(
                    component,
                    target.key,
                    translations,
                    target.context,
                    [0],
                    report,
                    target.category,
                )
                if count:
                    replacements.append(
                        (
                            target.node.start,
                            target.node.end,
                            encode_snbt_string(dump_json_component(transformed, spaced)),
                        )
                    )
                continue

            allowed, reason = _extractable_literal(value)
            if not allowed:
                if reason == "empty":
                    report.skipped_empty[target.category] += 1
                else:
                    report.skipped_control[target.category] += 1
                continue
            _add_translation(translations, target.key, value, target.context)
            reference = target.key if target.category == "image" else f"{{{target.key}}}"
            replacements.append(
                (
                    target.node.start,
                    target.node.end,
                    encode_snbt_string(reference),
                )
            )
            report.extracted[target.category] += 1

        new_text = apply_replacements(document.text, replacements)
        transformed_documents.append(reparse_document(document, new_text))

    return transformed_documents, translations


def _detect_indent(text: str) -> int | str | None:
    if "\n" not in text and "\r" not in text:
        return None
    candidates: list[str] = []
    for line in text.splitlines()[1:]:
        match = re.match(r"([ \t]+)\"", line)
        if match:
            candidates.append(match.group(1))
    if not candidates:
        return 2
    shortest = min(candidates, key=len)
    if set(shortest) == {"\t"}:
        return "\t"
    if set(shortest) == {" "}:
        return len(shortest)
    return 2


def load_language(path: Path) -> tuple[dict[str, Any], LanguageFormat]:
    if not path.exists():
        return {}, LanguageFormat()
    if not path.is_file():
        raise ExtractionError(f"Language path is not a file: {path}")
    text, bom = _read_utf8(path)
    try:
        data = json.loads(text, object_pairs_hook=_json_object_without_duplicates)
    except (json.JSONDecodeError, DuplicateJsonKey) as exc:
        raise ExtractionError(f"{path}: invalid language JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ExtractionError(f"{path}: language JSON root must be an object")
    newline = "\r\n" if "\r\n" in text else "\n"
    return data, LanguageFormat(
        bom=bom,
        newline=newline,
        indent=_detect_indent(text),
        trailing_newline=text.endswith(("\n", "\r")),
    )


def build_language(
    existing: dict[str, Any], translations: dict[str, str]
) -> dict[str, Any]:
    result = {key: value for key, value in existing.items() if not is_managed_key(key)}
    result.update(translations)
    return result


def dump_language(data: dict[str, Any], language_format: LanguageFormat) -> str:
    if language_format.indent is None:
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    else:
        text = json.dumps(data, ensure_ascii=False, indent=language_format.indent)
    if language_format.newline != "\n":
        text = text.replace("\n", language_format.newline)
    if language_format.trailing_newline:
        text += language_format.newline
    return text


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def run_extraction(
    ftbquests_root: Path | str,
    language_path: Path | str,
    *,
    dry_run: bool = False,
) -> Report:
    root = Path(ftbquests_root).resolve()
    language_file = Path(language_path).resolve()
    documents = load_documents(root)
    language, language_format = load_language(language_file)

    report = Report()
    rehydrated_documents = rehydrate_documents(documents, language, report)
    extracted_documents, translations = extract_documents(rehydrated_documents, report)
    new_language = build_language(language, translations)
    language_text = dump_language(new_language, language_format)

    original_by_path = {document.path: document for document in documents}
    changed_documents = [
        document
        for document in extracted_documents
        if document.text != original_by_path[document.path].text
    ]
    report.changed_snbt_files = len(changed_documents)

    old_language_bytes = language_file.read_bytes() if language_file.exists() else None
    new_language_bytes = _encode_utf8(language_text, language_format.bom)
    report.language_changed = old_language_bytes != new_language_bytes

    if not dry_run:
        for document in changed_documents:
            _atomic_write(document.path, _encode_utf8(document.text, document.bom))
        if report.language_changed:
            _atomic_write(language_file, new_language_bytes)

    return report


def _format_counter(counter: Counter[str]) -> str:
    if not counter:
        return "0"
    details = ", ".join(f"{key}={counter[key]}" for key in sorted(counter))
    return f"{sum(counter.values())} ({details})"


def print_report(report: Report, dry_run: bool) -> None:
    mode = "DRY RUN" if dry_run else "UPDATED"
    print(f"[{mode}] Extracted: {_format_counter(report.extracted)}")
    print(f"[{mode}] Rehydrated: {_format_counter(report.rehydrated)}")
    print(f"[{mode}] Skipped empty: {_format_counter(report.skipped_empty)}")
    print(f"[{mode}] Skipped control/reference: {_format_counter(report.skipped_control)}")
    print(f"[{mode}] SNBT files changed: {report.changed_snbt_files}")
    print(f"[{mode}] Language file changed: {'yes' if report.language_changed else 'no'}")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract visible FTB Quests text into stable translation keys."
    )
    parser.add_argument(
        "ftbquests_root",
        type=Path,
        help="FTB Quests root directory containing quests/data.snbt",
    )
    parser.add_argument("language_json", type=Path, help="Language JSON to update")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run all parsing and validation without writing files",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    try:
        report = run_extraction(
            args.ftbquests_root, args.language_json, dry_run=args.dry_run
        )
    except ExtractionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print_report(report, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
