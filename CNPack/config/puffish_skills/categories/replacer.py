import json
import os
import re
import sys


ALIAS_TRANSLATION_KEYS = {
    "puffish_skills.categories.fate_fire_archmage.title": "puffish_skills.categories.hothead.title",
    "puffish_skills.categories.fate_fire_archmage.description": "puffish_skills.categories.hothead.description",
    "puffish_skills.categories.fate_high_priest.title": "puffish_skills.categories.donoharm.title",
    "puffish_skills.categories.fate_high_priest.description": "puffish_skills.categories.donoharm.description",
    "puffish_skills.categories.fate_arcane_archmage.title": "puffish_skills.categories.eldritch.title",
    "puffish_skills.categories.fate_arcane_archmage.description": "puffish_skills.categories.eldritch.description",
    "puffish_skills.categories.fate_warriors_devotion.title": "puffish_skills.categories.larry.title",
    "puffish_skills.categories.fate_warriors_devotion.description": "puffish_skills.categories.larry.description",
    "puffish_skills.categories.fate_decaying_devotion.title": "puffish_skills.categories.decayingdevotion.title",
    "puffish_skills.categories.fate_decaying_devotion.description": "puffish_skills.categories.decayingdevotion.description",
    "puffish_skills.categories.fate_sindorei_heritage.title": "puffish_skills.categories.grace.title",
    "puffish_skills.categories.fate_sindorei_heritage.description": "puffish_skills.categories.grace.description",
    "puffish_skills.categories.fate_skellaks_blessing.title": "puffish_skills.categories.stalwart.title",
    "puffish_skills.categories.fate_skellaks_blessing.description": "puffish_skills.categories.stalwart.description",
    "puffish_skills.categories.fate_frost_archmage.title": "puffish_skills.categories.iceking.title",
    "puffish_skills.categories.fate_frost_archmage.description": "puffish_skills.categories.iceking.description",
    "puffish_skills.categories.fate_shadow_techniques.title": "puffish_skills.categories.warriorTwinstrike.title",
    "puffish_skills.categories.fate_knowledge_of_runes_stars.title": "puffish_skills.categories.Elementalist.title",
    "puffish_skills.categories.fate_knowledge_of_runes_stars.description": "puffish_skills.categories.Elementalist.description",
    "puffish_skills.categories.fate_a_bards_tale.title": "puffish_skills.categories.bardPassive.title",
    "puffish_skills.categories.ascendancyDissonance.title": "puffish_skills.categories.bardActive.title",
    "puffish_skills.categories.ascendancyDissonance.description": "puffish_skills.categories.bardActive.description",
    "puffish_skills.categories.passive_skellaks_call.title": "puffish_skills.categories.warriorSwordfall.title",
    "puffish_skills.categories.passive_skellaks_call.description": "puffish_skills.categories.warriorSwordfall.description",
    "puffish_skills.categories.passive_focus_zone.title": "puffish_skills.categories.wayfarerQuickfire.title",
    "puffish_skills.categories.passive_focus_zone.description": "puffish_skills.categories.wayfarerQuickfire.description",
    "puffish_skills.categories.passive_empower.title": "puffish_skills.categories.initiateEmpower.title",
    "puffish_skills.categories.passive_empower.description": "puffish_skills.categories.initiateEmpower.description",
    "puffish_skills.categories.passive_critical_thinking.title": "puffish_skills.categories.initiateGambit.title",
    "puffish_skills.categories.passive_critical_thinking.description": "puffish_skills.categories.initiateGambit.description",
    "puffish_skills.categories.passive_omnivampirism.title": "puffish_skills.categories.omnivamp.title",
    "puffish_skills.categories.passive_omnivampirism.description": "puffish_skills.categories.omnivamp.description",
    "puffish_skills.categories.health+2.5%.title": "puffish_skills.categories.health+10%.title",
    "puffish_skills.categories.roll_distance+8%_roll_cooldown-5%.title": "puffish_skills.categories.ranged_damage+3%.title",
    "puffish_skills.categories.roll_distance+8%_roll_cooldown-5%.description": "puffish_skills.categories.ranged_damage+3%.description",
    "puffish_skills.categories.roll_distance+4%_roll_cooldown-2%.title": "puffish_skills.categories.luck+0.25.title",
    "puffish_skills.categories.roll_distance+4%_roll_cooldown-2%.description": "puffish_skills.categories.luck+0.25.description",
    "puffish_skills.categories.jump+4%.title": "puffish_skills.categories.jump+8%.title",
    "puffish_skills.categories.armor+8%.title": "puffish_skills.categories.armor+20%.title",
    "puffish_skills.categories.toughness+5%.title": "puffish_skills.categories.toughness+20%.title",
    "puffish_skills.categories.melee_damage+3.5%.title": "puffish_skills.categories.melee_damage+12%.title",
    "puffish_skills.categories.lethality+3.5%.title": "puffish_skills.categories.lethality.title",
    "puffish_skills.categories.attack_speed+2%.title": "puffish_skills.categories.attack_speed+6%.title",
    "puffish_skills.categories.movement_speed+3%.title": "puffish_skills.categories.movement_speed+6%.title",
    "puffish_skills.categories.holy_power+3%_self_healing+3%.title": "puffish_skills.categories.healing+12%.title",
    "puffish_skills.categories.holy_power+3%_self_healing+3%.description": "puffish_skills.categories.healing+12%.description",
    "puffish_skills.categories.stamina+10%.title": "puffish_skills.categories.stamina+8%.title",
    "puffish_skills.categories.fire_power+3%_critical_chance+1%.title": "puffish_skills.categories.fire+12%.title",
    "puffish_skills.categories.fire_power+3%_critical_chance+1%.description": "puffish_skills.categories.fire+12%.description",
    "puffish_skills.categories.frost_power+3%_spell_haste+1%.title": "puffish_skills.categories.frost+12%.title",
    "puffish_skills.categories.frost_power+3%_spell_haste+1%.description": "puffish_skills.categories.frost+12%.description",
    "puffish_skills.categories.arcane_power+3%_critical_damage+1%.title": "puffish_skills.categories.arcane+12%.title",
    "puffish_skills.categories.arcane_power+3%_critical_damage+1%.description": "puffish_skills.categories.arcane+12%.description",
    "puffish_skills.categories.artifact_damage.title": "puffish_skills.categories.damage.title.1",
    "puffish_skills.categories.artifact_damage.title.1": "puffish_skills.categories.fyrdmg+5.title.3",
    "puffish_skills.categories.warriors_devotion_damage.title": "puffish_skills.categories.maxhealth+5.title.3",
    "puffish_skills.categories.artifact_damage_soul.title": "puffish_skills.categories.fyrdmg+5.title.1",
    "puffish_skills.categories.artifact_damage_soul.description": "puffish_skills.categories.maxhealth+5.title.1",
    "puffish_skills.categories.haste_fire.title": "puffish_skills.categories.maxhealth+5.title.1",
    "puffish_skills.categories.haste_fire.description": "puffish_skills.categories.fyrdmg+5.title.1",
}


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
    if trans_key in existing_translations and isinstance(existing_translations[trans_key], str):
        existing_value = existing_translations[trans_key]
        if not existing_value.startswith("__MISSING__ "):
            return existing_value, "existing"
    if trans_key in seed_translations and isinstance(seed_translations[trans_key], str):
        return seed_translations[trans_key], "seed"
    alias_key = ALIAS_TRANSLATION_KEYS.get(trans_key)
    if alias_key and alias_key in seed_translations and isinstance(seed_translations[alias_key], str):
        return seed_translations[alias_key], f"alias:{alias_key}"
    return infer_readable_translation(trans_key), "generated"

def get_content_hash(text):
    """生成内容的唯一标识，用于区分同一技能中不同文本"""
    return hash(text) % 100000

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
    print(f"已生成语言文件: {lang_path}")
    print(f"自动生成词条数量: {len(set(generated_keys))}")

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    process_json_files(base_dir)

if __name__ == "__main__":
    main()
