import json
from collections import defaultdict

def main():
    # 读取现有语言文件
    lang_file = "D:\\mc\\mod\\Prominence-II-Chinese\\Source\\vaultpatcher\\i18n\\en_us.json"
    with open(lang_file, 'r', encoding='utf-8') as f:
        translations = json.load(f)
    
    # 读取需要处理的JSON文件
    json_file = "D:\\mc\\mod\\Prominence-II-Chinese\\CNPack\\config\\vaultpatcher_asm\\Prominent-GLOBAL-MC1.20.1-3.9.5.json"
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 用于记录新增的翻译
    new_translations = {}
    # 为每个类名创建独立的计数器
    class_counters = defaultdict(lambda: 1)
    
    # 遍历处理
    for item in data:
        if "target_class" in item and "pairs" in item:
            class_name = item["target_class"].get("name", "").split(".")[-1].lower()
            if not class_name:
                continue
                
            for pair in item["pairs"]:
                if not pair.get("value"):
                    continue
                    
                # 如果value已经是翻译键并且在translations中存在,跳过
                if pair["value"].startswith("vp.") and pair["value"] in translations:
                    continue
                    
                # 如果不是翻译键,生成新的
                if not pair["value"].startswith("vp."):
                    text = pair["value"]
                    key = f"vp.prominent.{class_name}.{class_counters[class_name]}"
                    class_counters[class_name] += 1
                    
                    pair["value"] = key
                    new_translations[key] = text

    # 更新语言文件
    translations.update(new_translations)
    
    # 保存更新后的文件
    with open(lang_file, 'w', encoding='utf-8') as f:
        json.dump(translations, f, indent=4, ensure_ascii=False)
        
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False) 

    print(f"处理完成! 新增了 {len(new_translations)} 个翻译")

if __name__ == "__main__":
    main()