<div align="center"> 
   <h1>Prominence II 项目简体中文翻译</h1>
</div>

CurseForge|加载器|整合包版本|汉化维护状态
:-|:-|:-|:-
[链接](https://www.curseforge.com/minecraft/modpacks/prominence-2-rpg)|Fabric|1.20.1 v3.1.5|*翻译中*|

---

汉化项目：[Paratranz](https://paratranz.cn/projects/13782)

汉化发布：[VM汉化组官网](https://vmct-cn.top/modpacks/项目)

项目主管 @[某某](https://github.com/某某)

译者：[查看贡献者排行榜](https://paratranz.cn/projects/13782/leaderboard)


---

# 整合包介绍

整合包介绍

# 自动化Paratranz同步教程

## 1. 设置环境变量

1. 到仓库顶部导航栏: `Settings -> Environments -> New environment` 新建 `PARATRANZ_ENV`
2. 添加加密变量（Environment secrets）: 
   | 名称        | 值                                              |
   |-------------|-------------------------------------------------|
   | API_KEY     | 你的Paratranz token，须有上传文件权限         |
   token可在 <https://paratranz.cn/users/my> 中的设置部分获取。
3. 添加环境变量（Environment variables）: 

   | 名称   | 值                                   |
   |--------|--------------------------------------|
   | ID     | Paratranz项目ID，例如 `10719`         |


## 2. 开始使用

我们的工作流有两种功能：从Paratranz同步到github仓库和从github仓库同步到Paratranz。

它们全都可以手动启动，操作方法请见下图所示：

![](.github/action.png)

其中，Paratranz同步到GitHub仓库工作流会在北京时间每天早上9点和晚上9点自动运行。

下载译文至Github功能可自行修改`.github/workflows`文件夹中的`download_release.yml`自动执行时间，格式为[cron表达式](https://blog.csdn.net/Stromboli/article/details/141962560)。

在有译文更改后，工作流会自动生成一个artifact构件，可在action的运行页面找到并下载。
此外，每有一次译文更改都将自动发布一次标记为预发布的Release。

注：从github仓库同步到Paratranz的工作流很少使用，故支持手动触发。

如果项目已经完成，请在仓库设置（`Settings`）中禁用工作流运行。
