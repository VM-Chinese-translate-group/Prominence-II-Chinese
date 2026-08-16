import hashlib
import json
import os
import re
import sys
import unicodedata


def find_repo_root(start_dir):
    current = os.path.abspath(start_dir)
    while True:
        if os.path.exists(os.path.join(current, '.git')):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent

def load_unicode_mapping(mapping_file):
    """从 mapping.txt 读取字符映射，避免脚本内映射过期。"""
    mapping = {}
    pattern = re.compile(r"^(.+)\s*->\s*\\u([0-9A-Fa-f]{4,6})$")

    with open(mapping_file, 'r', encoding='utf-8') as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            match = pattern.match(line)
            if not match:
                raise ValueError(f"mapping.txt 第 {line_no} 行格式错误: {raw_line.rstrip()}")
            source_char = match.group(1)
            target_char = chr(int(match.group(2), 16))
            mapping[source_char] = target_char

    return mapping


def replace_unicode(text, unicode_mapping):
    if not isinstance(text, str):
        return text
    for old, new in unicode_mapping.items():
        text = text.replace(old, new)
    return text.replace('\u00a7', '\\u00a7')

def write_lang_file(file_path, translations):
    with open(file_path, 'wb') as f:
        # 手动构建JSON字符串,使用bytes写入以保持原始格式
        f.write(b'{\n')
        entries = []
        items = list(translations.items())
        for i, (key, value) in enumerate(items):
            value = value.replace('"', '\\"').replace('\n', '\\n')
            entry = f'    "{key}": "{value}"'
            if i < len(items) - 1:
                entry += ','
            entries.append(entry.encode('utf-8'))
        f.write(b'\n'.join(entries))
        f.write(b'\n}\n')


def load_existing_translations(file_path):
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as e:
        print(f"警告: 读取现有语言文件失败 {file_path}: {e}")
        return {}


def load_json_dict(file_path):
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as e:
        print(f"警告: 读取 JSON 失败 {file_path}: {e}")
        return {}


def load_seed_translations(base_dir):
    """当本地 en_us.json 为空时，从 Source 里的英文词条回填 puffish_skills。"""
    repo_root = find_repo_root(base_dir)
    if not repo_root:
        return {}

    source_lang_path = os.path.join(
        repo_root,
        'Source',
        'resourcepacks',
        'vm_translations',
        'assets',
        'vm_language',
        'lang',
        'en_us.json'
    )

    if not os.path.exists(source_lang_path):
        return {}

    try:
        with open(source_lang_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return {
            key: value
            for key, value in data.items()
            if key.startswith('puffish_skills.') and isinstance(value, str)
        }
    except (json.JSONDecodeError, OSError) as e:
        print(f"警告: 读取 Source 英文词条失败 {source_lang_path}: {e}")
        return {}


def put_translation(all_translations, ordered_keys, key, value, unicode_mapping):
    if not isinstance(key, str) or not key:
        return
    if not isinstance(value, str):
        value = str(value)
    if key not in all_translations:
        ordered_keys.append(key)
    all_translations[key] = replace_unicode(value, unicode_mapping)


def infer_readable_translation(key):
    suffix = key.split("puffish_skills.categories.", 1)[-1]
    suffix = suffix.rsplit(".", 1)[0]
    text = suffix.replace("_", " ").replace("+", " + ").replace("-", " - ").replace("%", " %")
    text = re.sub(r"\s+", " ", text).strip()
    return text.title()


def resolve_translation_value(trans_key, existing_translations, seed_translations):
    """原始提取文件不含翻译键，因此不做旧 key 迁移。只处理当前文件本身的已存在英文值和 seed 值。"""
    if trans_key in existing_translations and isinstance(existing_translations[trans_key], str):
        existing_value = existing_translations[trans_key]
        if not existing_value.startswith("__MISSING__ "):
            return existing_value, "existing"
    if trans_key in seed_translations and isinstance(seed_translations[trans_key], str):
        return seed_translations[trans_key], "seed"
    return infer_readable_translation(trans_key), "generated"

def normalize_text_for_signature(text):
    """标准化文本，保证同内容会得到同一签名，避免 hash() 进程随机化导致重跑结果变动。"""
    if not isinstance(text, str):
        return ""
    normalized = unicodedata.normalize('NFC', text)
    normalized = normalized.replace('\r\n', '\n').replace('\r', '\n')
    return normalized.strip()


def get_content_hash(text):
    """稳定的内容签名，用于区分同一技能中的不同文本。"""
    normalized = normalize_text_for_signature(text)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:12]


def collect_translate_references(base_dir):
    references = set()

    def walk(value):
        if isinstance(value, dict):
            for k, v in value.items():
                if k == 'translate' and isinstance(v, str):
                    references.add(v)
                walk(v)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    for root, _, files in os.walk(base_dir):
        for file in files:
            if file not in {'category.json', 'definitions.json'}:
                continue
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                walk(data)
            except (json.JSONDecodeError, OSError) as e:
                print(f"警告: 扫描 {file_path} 失败: {e}")

    return references


def self_check_translations(base_dir, all_translations, seed_translations, ordered_keys):
    issues = []
    references = collect_translate_references(base_dir)
    known_keys = set(all_translations.keys()) | set(seed_translations.keys())

    missing_keys = sorted(ref for ref in references if ref not in known_keys)
    if missing_keys:
        issues.append(f"缺失翻译键: {', '.join(missing_keys[:10])}{' ...' if len(missing_keys) > 10 else ''}")

    variant_by_base = {}
    for key in ordered_keys:
        if not isinstance(key, str):
            continue
        if key.endswith('.title') or key.endswith('.description'):
            base_key = key
        elif re.search(r'\.(title|description)\.\d+$', key):
            base_key = re.sub(r'\.(title|description)\.\d+$', r'.\1', key)
        else:
            continue

        value = all_translations.get(key)
        if value is None:
            continue
        normalized = normalize_text_for_signature(value)
        variant_by_base.setdefault(base_key, {})
        previous_key = variant_by_base[base_key].get(normalized)
        if previous_key is not None and previous_key != key:
            issues.append(f"同一技能字段中重复文本映射: {base_key} -> {previous_key} / {key} => {value[:60]}")
        variant_by_base[base_key][normalized] = key

    if issues:
        raise RuntimeError("自检失败:\n- " + "\n- ".join(issues))

    print("自检通过: 翻译键引用完整，未发现同技能字段中的重复/冲突文本变体。")


def process_json_files(base_dir):
    """处理JSON文件"""
    mapping_path = os.path.abspath(os.path.join(base_dir, '..', '..', 'mapping.txt'))
    try:
        unicode_mapping = load_unicode_mapping(mapping_path)
        print(f"已加载映射: {mapping_path} ({len(unicode_mapping)} 条)")
    except FileNotFoundError:
        print(f"警告: 未找到映射文件 {mapping_path}，将跳过字符映射")
        unicode_mapping = {}
    except ValueError as e:
        print(f"警告: 映射文件格式异常: {e}，将跳过字符映射")
        unicode_mapping = {}

    lang_path = os.path.join(base_dir, "en_us.json")
    existing_translations = load_existing_translations(lang_path)
    seed_translations = load_seed_translations(base_dir)
    if seed_translations:
        print(f"已加载 Source 词条: {len(seed_translations)} 条")

    # 用于保存最终翻译文本（严格按引用键收集，避免多余键）
    all_translations = {}
    ordered_keys = []
    # 用于追踪同一技能中同一字段内不同文本（hash值）的变体
    content_variants = {}
    generated_keys = []

    # 获取当前脚本的文件名，避免误删
    current_script = os.path.basename(__file__)

    for root, dirs, files in os.walk(base_dir):
        # 1. 清理多余文件
        for file in files:
            if file not in ['definitions.json', 'category.json', 'en_us.json', current_script]:
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)
                    print(f"已删除多余文件: {file_path}")
                except OSError as e:
                    print(f"删除失败: {file_path}, {e}")

        category_name = os.path.basename(root)

        # 2. 处理 category.json
        category_file = os.path.join(root, "category.json")
        if os.path.exists(category_file):
            try:
                with open(category_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                modified = False
                if "title" in data and isinstance(data["title"], str):
                    title_text = data["title"]
                    processed_text = replace_unicode(title_text, unicode_mapping)
                    trans_key = f"puffish_skills.category.{category_name}.title"
                    put_translation(all_translations, ordered_keys, trans_key, processed_text, unicode_mapping)
                    data["title"] = {"translate": trans_key}
                    modified = True
                elif "title" in data and isinstance(data["title"], dict):
                    trans_key = data["title"].get("translate")
                    if isinstance(trans_key, str):
                        value, source = resolve_translation_value(trans_key, existing_translations, seed_translations)
                        put_translation(all_translations, ordered_keys, trans_key, value, unicode_mapping)
                        if source == "generated":
                            generated_keys.append(trans_key)
                            print(f"警告: 自动生成词条 {trans_key}")
                
                if modified:
                    with open(category_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                    print(f"已处理 category.json: {category_file}")
            except Exception as e:
                print(f"处理 category.json 出错: {category_file}, {e}")

        # 3. 处理 definitions.json
        definitions_file = os.path.join(root, "definitions.json")
        if os.path.exists(definitions_file):
            try:
                with open(definitions_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                modified = False
                for skill_name, skill_data in data.items():
                    # 处理 title
                    if "title" in skill_data and isinstance(skill_data["title"], str):
                        original_text = skill_data["title"]
                        base_key = f"puffish_skills.categories.{skill_name}.title"
                        content_hash = get_content_hash(original_text)
                        
                        if base_key not in content_variants:
                            content_variants[base_key] = {}
                        variant_dict = content_variants[base_key]

                        if content_hash in variant_dict:
                            trans_key = variant_dict[content_hash]
                        else:
                            variant_num = len(variant_dict)
                            trans_key = base_key if variant_num == 0 else f"{base_key}.{variant_num}"
                            variant_dict[content_hash] = trans_key
                        
                        processed_text = replace_unicode(original_text, unicode_mapping)
                        put_translation(all_translations, ordered_keys, trans_key, processed_text, unicode_mapping)
                        skill_data["title"] = {"translate": trans_key}
                        modified = True
                    elif "title" in skill_data and isinstance(skill_data["title"], dict):
                        trans_key = skill_data["title"].get("translate")
                        if isinstance(trans_key, str):
                            value, source = resolve_translation_value(trans_key, existing_translations, seed_translations)
                            put_translation(all_translations, ordered_keys, trans_key, value, unicode_mapping)
                            if source == "generated":
                                generated_keys.append(trans_key)
                                print(f"警告: 自动生成词条 {trans_key}")

                    # 处理 description
                    if "description" in skill_data and isinstance(skill_data["description"], str):
                        original_text = skill_data["description"]
                        base_key = f"puffish_skills.categories.{skill_name}.description"
                        content_hash = get_content_hash(original_text)
                        
                        if base_key not in content_variants:
                            content_variants[base_key] = {}
                        variant_dict = content_variants[base_key]

                        if content_hash in variant_dict:
                            trans_key = variant_dict[content_hash]
                        else:
                            variant_num = len(variant_dict)
                            trans_key = base_key if variant_num == 0 else f"{base_key}.{variant_num}"
                            variant_dict[content_hash] = trans_key
                        
                        processed_text = replace_unicode(original_text, unicode_mapping)
                        put_translation(all_translations, ordered_keys, trans_key, processed_text, unicode_mapping)
                        skill_data["description"] = {"translate": trans_key}
                        modified = True
                    elif "description" in skill_data and isinstance(skill_data["description"], dict):
                        trans_key = skill_data["description"].get("translate")
                        if isinstance(trans_key, str):
                            value, source = resolve_translation_value(trans_key, existing_translations, seed_translations)
                            put_translation(all_translations, ordered_keys, trans_key, value, unicode_mapping)
                            if source == "generated":
                                generated_keys.append(trans_key)
                                print(f"警告: 自动生成词条 {trans_key}")
                
                if modified:
                    with open(definitions_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                    print(f"已处理 definitions.json: {definitions_file}")
            except Exception as e:
                print(f"处理 definitions.json 出错: {definitions_file}, {e}")

    # 生成语言文件
    ordered_translations = {key: all_translations[key] for key in ordered_keys}
    write_lang_file(lang_path, ordered_translations)
    report_path = os.path.join(base_dir, "missing_translation_report.txt")
    with open(report_path, 'w', encoding='utf-8') as f:
        for key in sorted(set(generated_keys)):
            f.write(key + "\n")

    self_check_translations(base_dir, ordered_translations, seed_translations, ordered_keys)
    print(f"已生成语言文件: {lang_path}")
    print(f"自动生成词条数量: {len(set(generated_keys))}")

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    process_json_files(base_dir)

if __name__ == "__main__":
    main()
