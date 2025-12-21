import asyncio
import os
import json
from pprint import pprint
import paratranz_client
from pydantic import ValidationError

configuration = paratranz_client.Configuration(host="https://paratranz.cn/api")
configuration.api_key["Token"] = os.environ["API_TOKEN"]


async def upload_file(api_instance, project_id, path, file, existing_files, semaphore):
    filename = os.path.basename(file)
    remote_full_path = path + filename
    existing_file = next((f for f in existing_files if f.name == remote_full_path), None)

    async with semaphore:
        for attempt in range(3):  # 最多重试 3 次
            try:
                if existing_file:
                    print(f"Updating {remote_full_path} (ID: {existing_file.id}) - Attempt {attempt + 1}")
                    await api_instance.update_file(project_id, file_id=existing_file.id, file=file)
                    print(f"文件已更新！文件路径为：{existing_file.name}")
                else:
                    print(f"Creating {remote_full_path} in {path} - Attempt {attempt + 1}")
                    api_response = await api_instance.create_file(project_id, file=file, path=path)
                    pprint(api_response)
                return  # 成功后退出重试循环
            except Exception as e:
                print(f"处理文件 {file} 时出错 (尝试 {attempt + 1}/3): {e}")
                if attempt < 2:
                    wait_time = (attempt + 1) * 2
                    print(f"等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    if hasattr(e, 'body'):
                        print(f"Error body: {e.body}")


def get_filelist(dir_path):
    filelist = []
    for root, _, files in os.walk(dir_path):
        for file in files:
            if "en_us" in file and file.endswith(".json"):
                filelist.append(os.path.join(root, file))
    return filelist


async def main():
    project_id = int(os.environ["PROJECT_ID"])
    files = get_filelist("./Source")
    
    async with paratranz_client.ApiClient(configuration) as api_client:
        api_instance = paratranz_client.FilesApi(api_client)
        
        print("正在获取项目文件列表...")
        existing_files = await api_instance.get_files(project_id)
        
        # 限制并发数为 3，避免触发服务器超时或频率限制
        semaphore = asyncio.Semaphore(3)
        
        tasks = []
        for file in files:
            # 使用 relpath 获取相对于 Source 的路径，避免开头的 /
            rel_path = os.path.relpath(file, "./Source").replace("\\", "/")
            # filename 是文件名，例如 'en_us.json'
            filename = os.path.basename(file)
            # path 是目录路径，例如 'path/to/'，如果是在根目录则为空字符串
            path = rel_path.replace(filename, "")
            
            tasks.append(upload_file(api_instance, project_id, path, file, existing_files, semaphore))

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
