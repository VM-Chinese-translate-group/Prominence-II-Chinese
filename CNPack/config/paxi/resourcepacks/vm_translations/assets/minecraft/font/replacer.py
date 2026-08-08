import json
import re

UNICODE_MAPPING = {
    r'\uF933': r'\uE001', r'\uF934': r'\uE002', r'\uF935': r'\uE003',
    r'\uF937': r'\uE005', r'\uF938': r'\uE006',
    r'\uF939': r'\uE027',
    r'\uF940': r'\uE007', r'\uF941': r'\uE008', r'\uF942': r'\uE009',
    r'\uF943': r'\uE010', r'\uF944': r'\uE011', r'\uF945': r'\uE012',
    r'\uF946': r'\uE013', r'\uF947': r'\uE014', r'\uF948': r'\uE015',
    r'\uF949': r'\uE016', r'\uF950': r'\uE017', r'\uF951': r'\uE018',
    r'\uF952': r'\uE019', r'\uF953': r'\uE020', r'\uF954': r'\uE021',
    r'\uF955': r'\uE022', r'\uF956': r'\uE023', r'\uF957': r'\uE024',
    r'\uF958': r'\uE025', r'\uF959': r'\uE026', r'\uF960': r'\uE028',
    r'\uF961': r'\uE029', r'\uF962': r'\uE030', r'\uF963': r'\uE031',
    r'\uF964': r'\uE032', r'\uF965': r'\uE033', r'\uF966': r'\uE034',
    r'\uF967': r'\uE035', r'\uF968': r'\uE036', r'\uF969': r'\uE037',
    r'\uF96A': r'\uE038', r'\uF96B': r'\uE039', r'\uF96C': r'\uE040',
    r'\uF96D': r'\uE041', r'\uF96E': r'\uE042', r'\uF96F': r'\uE043',
    r'\uF970': r'\uE044', r'\uF971': r'\uE045', r'\uF972': r'\uE046',
    r'\uF973': r'\uE047', r'\uF974': r'\uE048', r'\uF975': r'\uE049',
    r'\uF976': r'\uE050', r'\uF977': r'\uE051'
}

def find_existing_unicode_chars(content):
    """找出文件中实际存在、且在 mapping.txt 中定义的字体码位"""
    pattern = r'\\uF(?:93[357-9]|94[0-9]|95[0-9]|96[0-9A-F]|97[0-7])'
    matches = re.findall(pattern, content, flags=re.IGNORECASE)
    return sorted(list(set(matches)))

def create_mapping(existing_chars):
    """按稳定的 mapping.txt 关系创建映射，避免因 4.0 删除 F936 而整体错位"""
    normalized = {char: char[:2].lower() + char[2:].upper() for char in existing_chars}
    return {char: UNICODE_MAPPING[normalized[char]] for char in existing_chars if normalized[char] in UNICODE_MAPPING}

def remap_unicode_chars(input_file, output_file):
    # 读取JSON文件
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 找出实际存在的字符
    existing_chars = find_existing_unicode_chars(content)
    print(f"找到的Unicode字符: {', '.join(existing_chars)}")
    
    # 创建映射
    char_map = create_mapping(existing_chars)
    print("\n映射关系:")
    for old, new in char_map.items():
        print(f"{old} -> {new}")
    
    # 使用正则表达式进行替换
    pattern = '|'.join(map(re.escape, char_map.keys()))
    new_content = re.sub(pattern, lambda m: char_map[m.group()], content)
    
    # 写入新文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"\n替换完成！新文件已保存为: {output_file}")

# 使用示例
input_file = r"d:\mc\mod\Prominence-II-Chinese\CNPack\config\paxi\resourcepacks\vm_translations\assets\minecraft\font\default.json"
output_file = r"d:\mc\mod\Prominence-II-Chinese\CNPack\config\paxi\resourcepacks\vm_translations\assets\minecraft\font\default_new.json"

remap_unicode_chars(input_file, output_file)
