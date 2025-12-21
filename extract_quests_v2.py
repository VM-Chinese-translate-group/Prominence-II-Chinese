import re
import json
import os

snbt_path = r"d:\mc\mod\Prominence-II-Chinese\CNPack\config\ftbquests\quests\chapters\a_jolly_christmas.snbt"
json_path = r"d:\mc\mod\Prominence-II-Chinese\Source\resourcepacks\vm_translations\assets\quests\lang\en_us.json"

# 从snbt文件名动态提取章节名，生成翻译键前缀
_chapter_name = os.path.basename(snbt_path).replace('.snbt', '')
CHAPTER_PREFIX = f"ftbquests.chapter.{_chapter_name}"

def parse_snbt_list(content, start_index):
    depth = 0
    in_quote = False
    escape = False
    i = content.find('[', start_index)
    if i == -1: return None, -1
    list_start = i + 1
    depth = 1
    i += 1
    while i < len(content):
        char = content[i]
        if escape: escape = False
        elif char == '\\': escape = True
        elif char == '"': in_quote = not in_quote
        elif not in_quote:
            if char == '[': depth += 1
            elif char == ']':
                depth -= 1
                if depth == 0: return content[list_start:i], i
        i += 1
    return None, -1

def get_balanced_braces(content, start_index):
    i = content.find('{', start_index)
    if i == -1: return None, -1
    block_start = i
    depth = 1
    i += 1
    in_quote = False
    escape = False
    while i < len(content):
        char = content[i]
        if escape: escape = False
        elif char == '\\': escape = True
        elif char == '"': in_quote = not in_quote
        elif not in_quote:
            if char == '{': depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0: return content[block_start:i+1], i
        i += 1
    return None, -1

def extract_strings_from_list(list_content):
    results = []
    i = 0
    in_quote = False
    escape = False
    current_start = -1
    while i < len(list_content):
        char = list_content[i]
        if escape: escape = False
        elif char == '\\': escape = True
        elif char == '"':
            if not in_quote:
                in_quote = True
                current_start = i
            else:
                in_quote = False
                val = list_content[current_start+1:i]
                results.append((val, current_start, i+1))
        i += 1
    return results

def process_quest(quest_block, quest_idx, translations):
    base_key = f"{CHAPTER_PREFIX}.quests{quest_idx}"
    
    # STEP 1: Extract and mask tasks/rewards blocks to avoid replacing titles inside them
    # when we process quest-level title
    
    tasks_placeholder = "___TASKS_PLACEHOLDER___"
    rewards_placeholder = "___REWARDS_PLACEHOLDER___"
    
    tasks_block_original = None
    rewards_block_original = None
    
    # Extract tasks block
    tasks_match = re.search(r'(?<!\w)tasks:\s*\[', quest_block)
    if tasks_match:
        start_idx = tasks_match.start()
        content_inside, end_idx = parse_snbt_list(quest_block, start_idx)
        if content_inside is not None:
            list_start_char = quest_block.find('[', start_idx)
            tasks_block_original = quest_block[start_idx:end_idx+1]
            quest_block = quest_block[:start_idx] + tasks_placeholder + quest_block[end_idx+1:]
    
    # Extract rewards block
    rewards_match = re.search(r'(?<!\w)rewards:\s*\[', quest_block)
    if rewards_match:
        start_idx = rewards_match.start()
        content_inside, end_idx = parse_snbt_list(quest_block, start_idx)
        if content_inside is not None:
            rewards_block_original = quest_block[start_idx:end_idx+1]
            quest_block = quest_block[:start_idx] + rewards_placeholder + quest_block[end_idx+1:]
    
    # STEP 2: Now process quest-level title (won't affect tasks/rewards)
    def replace_title(match):
        val = match.group(1)
        # Skip if already a translation key reference
        if val.startswith('{') and val.endswith('}'):
            return match.group(0)
        key = f"{base_key}.title"
        translations[key] = val
        return f'title: "{{{key}}}"'
    
    # (?<!\w) ensures we don't match "subtitle" as "title"
    quest_block = re.sub(r'(?<!\w)title:\s*"((?:[^"\\]|\\.)*)"', replace_title, quest_block)

    # STEP 3: Replace Subtitle (at quest level)
    def replace_subtitle(match):
        val = match.group(1)
        # Skip if already a translation key reference
        if val.startswith('{') and val.endswith('}'):
            return match.group(0)
        key = f"{base_key}.subtitle"
        translations[key] = val
        return f'subtitle: "{{{key}}}"'
    
    quest_block = re.sub(r'(?<!\w)subtitle:\s*"((?:[^"\\]|\\.)*)"', replace_subtitle, quest_block)

    # STEP 4: Replace Description
    desc_match = re.search(r'(?<!\w)description:\s*\[', quest_block)
    if desc_match:
        start_idx = desc_match.start()
        content_inside, end_idx = parse_snbt_list(quest_block, start_idx)
        if content_inside is not None:
            strs = extract_strings_from_list(content_inside)
            new_list_content = content_inside
            for idx, (val, s, e) in enumerate(reversed(strs)):
                real_idx = len(strs) - 1 - idx
                if val.strip() == "": continue
                # Skip if already a translation key reference
                if val.startswith('{') and val.endswith('}'):
                    continue
                key = f"{base_key}.description{real_idx}"
                translations[key] = val
                new_list_content = new_list_content[:s] + f'"{{{key}}}"' + new_list_content[e:]
            
            list_start_char = quest_block.find('[', start_idx)
            quest_block = quest_block[:list_start_char+1] + new_list_content + quest_block[end_idx:]

    # STEP 5: Process tasks block separately
    if tasks_block_original is not None:
        # Parse tasks: [ ... ]
        tasks_inner_match = re.search(r'tasks:\s*\[', tasks_block_original)
        if tasks_inner_match:
            inner_start = tasks_inner_match.start()
            content_inside, inner_end = parse_snbt_list(tasks_block_original, inner_start)
            if content_inside is not None:
                new_tasks_content = ""
                cursor = 0
                task_idx = 0
                while True:
                    obj_str, obj_end = get_balanced_braces(content_inside, cursor)
                    if obj_str is None:
                        new_tasks_content += content_inside[cursor:]
                        break
                    obj_start = content_inside.find('{', cursor)
                    new_tasks_content += content_inside[cursor:obj_start]
                    
                    task_key_base = f"{base_key}.tasks{task_idx}"
                    def replace_task_title(match, tkb=task_key_base):
                        val = match.group(1)
                        # Skip if already a translation key reference
                        if val.startswith('{') and val.endswith('}'):
                            return match.group(0)
                        key = f"{tkb}.title"
                        translations[key] = val
                        return f'title: "{{{key}}}"'
                    
                    new_obj_str = re.sub(r'(?<!\w)title:\s*"((?:[^"\\]|\\.)*)"', replace_task_title, obj_str)
                    new_tasks_content += new_obj_str
                    cursor = obj_end + 1
                    task_idx += 1
                
                list_start_char = tasks_block_original.find('[', inner_start)
                tasks_block_original = tasks_block_original[:list_start_char+1] + new_tasks_content + tasks_block_original[inner_end:]
        
        # Put tasks block back
        quest_block = quest_block.replace(tasks_placeholder, tasks_block_original)
    
    # STEP 6: Put rewards block back (no processing needed for rewards)
    if rewards_block_original is not None:
        quest_block = quest_block.replace(rewards_placeholder, rewards_block_original)

    return quest_block

def process_chapter_properties(content, translations):
    # Process top-level title and subtitle
    base_key = CHAPTER_PREFIX
    
    def replace_title(match):
        val = match.group(1)
        key = f"{base_key}.title"
        translations[key] = val
        return f'title: "{{{key}}}"'
    
    content = re.sub(r'(?<!\w)title:\s*"((?:[^"\\]|\\.)*)"', replace_title, content)
    
    def replace_subtitle(match):
        val = match.group(1)
        key = f"{base_key}.subtitle"
        translations[key] = val
        return f'subtitle: "{{{key}}}"'
    
    content = re.sub(r'(?<!\w)subtitle:\s*"((?:[^"\\]|\\.)*)"', replace_subtitle, content)
    
    return content

def main():
    with open(snbt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    translations = {}
    
    # Find quests: [
    match = re.search(r'(?<!\w)quests:\s*\[', content)
    if not match:
        print("No quests found")
        return

    quests_content_inner, quests_end_idx = parse_snbt_list(content, match.start())
    if quests_content_inner is None:
        print("Failed to parse quests list")
        return
    
    pre_quests = content[:match.start()]
    post_quests = content[quests_end_idx+1:]
    
    # Process quests
    processed_quests_content = ""
    cursor = 0
    quest_idx = 0
    while True:
        obj_str, obj_end = get_balanced_braces(quests_content_inner, cursor)
        if obj_str is None:
            processed_quests_content += quests_content_inner[cursor:]
            break
        obj_start = quests_content_inner.find('{', cursor)
        processed_quests_content += quests_content_inner[cursor:obj_start]
        
        new_obj_str = process_quest(obj_str, quest_idx, translations)
        processed_quests_content += new_obj_str
        
        cursor = obj_end + 1
        quest_idx += 1
        
    # Process top-level properties in pre and post
    pre_quests = process_chapter_properties(pre_quests, translations)
    post_quests = process_chapter_properties(post_quests, translations)
    
    final_snbt = pre_quests + f"quests: [{processed_quests_content}]" + post_quests
    
    with open(snbt_path, 'w', encoding='utf-8') as f:
        f.write(final_snbt)
        
    print(f"Updated SNBT. Extracted {len(translations)} keys.")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    keys_to_remove = [k for k in data if k.startswith(CHAPTER_PREFIX)]
    for k in keys_to_remove:
        del data[k]
        
    data.update(translations)
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        
    print("Updated JSON.")

if __name__ == "__main__":
    main()