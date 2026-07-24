import asyncio
import os
import json
from pathlib import Path, PurePosixPath
from pprint import pprint
from tempfile import TemporaryDirectory

import paratranz_client
from pydantic import ValidationError

from paratranz_json_split import (
    UploadFile,
    create_split_uploads,
    is_legacy_split_source,
    load_paratranz_config,
    split_for_remote_path,
)

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
                    raise


async def delete_file(api_instance, project_id, remote_file, semaphore):
    async with semaphore:
        for attempt in range(3):
            try:
                await api_instance.delete_file(project_id, file_id=remote_file.id)
                print(f"已清理 Paratranz 旧分片：{remote_file.name}")
                return
            except Exception as e:
                print(f"删除 {remote_file.name} 时出错 (尝试 {attempt + 1}/3): {e}")
                if attempt < 2:
                    await asyncio.sleep((attempt + 1) * 2)
                else:
                    raise


def get_filelist(dir_path):
    filelist = []
    for root, _, files in os.walk(dir_path):
        for file in files:
            if "en_us" in file and file.endswith(".json"):
                filelist.append(os.path.join(root, file))
    return filelist


async def main():
    project_id = int(os.environ["PROJECT_ID"])
    split_configs, _ = load_paratranz_config()
    split_sources = {
        Path("Source") / Path(*config.path.parts) for config in split_configs
    }
    files = [
        Path(file)
        for file in get_filelist("./Source")
        if Path(file) not in split_sources
    ]
    
    async with paratranz_client.ApiClient(configuration) as api_client:
        api_instance = paratranz_client.FilesApi(api_client)
        
        print("正在获取项目文件列表...")
        existing_files = await api_instance.get_files(project_id)
        
        # 限制并发数为 3，避免触发服务器超时或频率限制
        semaphore = asyncio.Semaphore(3)
        
        with TemporaryDirectory(prefix="paratranz-json-split-") as temporary_dir:
            uploads = [
                UploadFile(
                    file,
                    PurePosixPath(os.path.relpath(file, "./Source").replace("\\", "/")),
                )
                for file in files
            ]
            for config in split_configs:
                uploads.extend(
                    create_split_uploads(Path("Source"), config, Path(temporary_dir))
                )

            tasks = []
            for upload in uploads:
                remote_parent = upload.remote_path.parent
                path = "" if remote_parent == PurePosixPath(".") else f"{remote_parent.as_posix()}/"
                tasks.append(
                    upload_file(
                        api_instance,
                        project_id,
                        path,
                        str(upload.local_path),
                        existing_files,
                        semaphore,
                    )
                )
            await asyncio.gather(*tasks)

            desired_paths = {upload.remote_path.as_posix() for upload in uploads}
            stale_files = []
            for remote_file in existing_files:
                remote_path = PurePosixPath(remote_file.name.replace("\\", "/"))
                managed = split_for_remote_path(remote_path, split_configs) is not None
                legacy = is_legacy_split_source(remote_path, split_configs)
                if (managed or legacy) and remote_path.as_posix() not in desired_paths:
                    stale_files.append(remote_file)

            await asyncio.gather(
                *(
                    delete_file(api_instance, project_id, remote_file, semaphore)
                    for remote_file in stale_files
                )
            )


if __name__ == "__main__":
    asyncio.run(main())
