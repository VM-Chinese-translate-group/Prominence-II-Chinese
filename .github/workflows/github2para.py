import asyncio
import os
import json
from pprint import pprint
import paratranz_client
from pydantic import ValidationError

configuration = paratranz_client.Configuration(host="https://paratranz.cn/api")
configuration.api_key["Token"] = os.environ["API_TOKEN"]


async def upload_file(api_instance, project_id, path, file, existing_files):
    filename = os.path.basename(file)
    # 构造远程文件的完整路径，用于匹配 existing_files
    remote_full_path = path + filename
    
    # 查找是否已存在
    existing_file = next((f for f in existing_files if f.name == remote_full_path), None)

    try:
        if existing_file:
            print(f"Updating {remote_full_path} (ID: {existing_file.id})")
            await api_instance.update_file(project_id, file_id=existing_file.id, file=file)
            print(f"文件已更新！文件路径为：{existing_file.name}")
        else:
            print(f"Creating {remote_full_path} in {path}")
            api_response = await api_instance.create_file(
                project_id, file=file, path=path
            )
            pprint(api_response)
    except Exception as e:
        print(f"处理文件 {file} 时出错: {e}")
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
        
        tasks = []
        for file in files:
            # 统一路径分隔符并提取相对路径
            rel_path = file.split("Source")[1].replace("\\", "/")
            # path 是目录路径，例如 '/path/to/'
            path = rel_path.replace(os.path.basename(file), "")
            
            tasks.append(upload_file(api_instance, project_id, path, file, existing_files))

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
