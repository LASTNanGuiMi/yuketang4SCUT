# yuketang4SCUT

面向华南理工大学雨课堂的视频辅助脚本，使用 Python 运行，通过本地配置管理登录信息。

## 为什么有这个版本

这个项目是在 [hewei2723/yuketang](https://github.com/hewei2723/yuketang) 的基础上修改整理的。

我在使用原项目时遇到了接口请求异常、限流重试出错和运行较慢的问题，于是针对这些问题进行了修复，并重新整理了配置方式、进度提示和异常处理，形成了现在的 SCUT 版本。

## 做了哪些修改

- **接口地址处理**：自动提取网站根地址，避免把课程页面地址误当成接口前缀。
- **批量心跳与连接复用**：减少重复连接和小批请求带来的开销，参数可自行调整。
- **正确重试**：遇到限流时等待后重试原接口，保留原来的 JSON 请求体。
- **读取已有进度**：跳过已完成的视频，从服务器保存的记录继续处理。
- **异常时及时停止**：请求有超时和有限重试；进度连续不增长时停止当前视频，避免无限循环。
- **完成状态更明确**：根据服务器返回的完成标记或 100% 进度判断完成，并汇总处理结果。
- **登录信息与源码分离**：真实 Cookie 放在不进入 Git 提交的本地配置中，公开仓库只提供空白示例。

## 开始使用

需要先安装 Python 3。下面的命令以 Windows PowerShell 为例。

### 1. 获取代码并安装依赖

当前可运行版本位于 `main` 分支：

```powershell
git clone --branch main https://github.com/LASTNanGuiMi/yuketang4SCUT.git
Set-Location yuketang4SCUT
python -m pip install -r requirements.txt
```

如果已经下载了项目，直接在项目文件夹中打开终端，从安装依赖这一步继续即可。

### 2. 创建本地配置

```powershell
Copy-Item config.example.json config.local.json
notepad config.local.json
```

已有 `config.local.json` 时，直接编辑它即可，重复复制会覆盖原来的配置。

配置结构如下，按自己的账号填写两个空白值：

```json
{
  "csrftoken": "",
  "sessionid": "",
  "university_id": "2627",
  "url_root": "https://scut.yuketang.cn/"
}
```

在浏览器登录学校雨课堂后，打开开发者工具，在 Application（应用程序）中的 Cookies 下找到对应站点，复制 `csrftoken`、`sessionid` 和 `university_id`。`url_root` 填写自己学校实际使用的网站地址。

保留 JSON 中的双引号和逗号；学校编号也使用字符串格式。

### 3. 运行

```powershell
python videoHelper.py



