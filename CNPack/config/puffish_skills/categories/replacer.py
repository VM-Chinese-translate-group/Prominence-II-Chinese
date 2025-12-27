import json
import os
import sys

# Unicode字符映射
UNICODE_MAPPING = {
    '\uF933': '\\uE001', '\uF934': '\\uE002', '\uF935': '\\uE003',
    '\uF936': '\\uE004', '\uF937': '\\uE005', '\uF938': '\\uE006',
    '\uF940': '\\uE007', '\uF941': '\\uE008', '\uF942': '\\uE009',
    '\uF943': '\\uE010', '\uF944': '\\uE011', '\uF945': '\\uE012',
    '\uF946': '\\uE013', '\uF947': '\\uE014', '\uF948': '\\uE015',
    '\uF949': '\\uE016', '\uF950': '\\uE017', '\uF951': '\\uE018',
    '\uF952': '\\uE019', '\uF953': '\\uE020', '\uF954': '\\uE021',
    '\uF955': '\\uE022', '\uF956': '\\uE023', '\uF957': '\\uE024',
    '\uF958': '\\uE025', '\uF959': '\\uE026'
}

def replace_unicode(text):
    if not isinstance(text, str):
        return text
    for old, new in UNICODE_MAPPING.items():
        text = text.replace(old, new)
    return text

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

def get_content_hash(text):
    """生成内容的唯一标识，用于区分同一技能中不同文本"""
    return hash(text) % 100000

def process_json_files(base_dir):
    """处理JSON文件"""
    # 用于保存所有翻译文本
    all_translations = {}
    # 用于追踪同一技能中同一字段内不同文本（hash值）的变体
    content_variants = {}

    # 获取当前脚本的文件名，避免误删
    current_script = os.path.basename(__file__)

    for root, dirs, files in os.walk(base_dir):
        # 1. 清理多余文件
        for file in files:
            if file not in ['definitions.json', 'category.json', current_script]:
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
                    processed_text = replace_unicode(title_text)
                    trans_key = f"puffish_skills.category.{category_name}.title"
                    all_translations[trans_key] = processed_text
                    data["title"] = {"translate": trans_key}
                    modified = True
                
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
                        
                        processed_text = replace_unicode(original_text)
                        all_translations[trans_key] = processed_text
                        skill_data["title"] = {"translate": trans_key}
                        modified = True

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
                        
                        processed_text = replace_unicode(original_text)
                        all_translations[trans_key] = processed_text
                        skill_data["description"] = {"translate": trans_key}
                        modified = True
                
                if modified:
                    with open(definitions_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
                    print(f"已处理 definitions.json: {definitions_file}")
            except Exception as e:
                print(f"处理 definitions.json 出错: {definitions_file}, {e}")

    # 生成语言文件
    lang_path = os.path.join(base_dir, "en_us.json")
    write_lang_file(lang_path, all_translations)
    print(f"已生成语言文件: {lang_path}")

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    process_json_files(base_dir)

if __name__ == "__main__":
    main()
