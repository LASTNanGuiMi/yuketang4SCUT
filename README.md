# yuketang4SCUT

面向华南理工大学雨课堂的视频辅助脚本。使用 Python 运行，登录信息通过本地配置管理。

## 项目说明

本项目基于 [hewei2723/yuketang](https://github.com/hewei2723/yuketang) 修改整理。我在使用原项目时遇到了接口请求异常、限流重试出错和运行较慢的问题，随后针对这些问题进行了修复，并整理了配置方式、进度提示和异常处理。

当前版本包含：

- 自动处理学校网站地址，避免接口路径拼接错误。
- 批量提交心跳、复用连接，并支持调整请求参数。
- 为请求设置超时，正确处理限流和有限重试。
- 读取服务器已有进度，跳过已完成的视频。
- 检测连续停滞，汇总完成及失败结果。
- 将真实登录信息与源码分离，避免随代码提交。

## 快速开始

准备好 Python 3，以下命令以 Windows PowerShell 为例。

### 1. 下载并安装依赖

```powershell
git clone --branch main https://github.com/LASTNanGuiMi/yuketang4SCUT.git
Set-Location yuketang4SCUT
python -m pip install -r requirements.txt
```

已下载项目时，直接在项目目录中安装依赖即可。

### 2. 填写本地配置

首次使用时，复制配置示例：

```powershell
Copy-Item config.example.json config.local.json
notepad config.local.json
```

已有 `config.local.json` 时，直接编辑，避免重复复制覆盖原配置。

```json
{
  "csrftoken": "",
  "sessionid": "",
  "university_id": "2627",
  "url_root": "https://scut.yuketang.cn/"
}
```

在浏览器登录学校雨课堂，打开开发者工具，在 Application（应用程序）中的 Cookies 下找到对应站点，将 `csrftoken`、`sessionid` 和 `university_id` 填入配置。`url_root` 使用自己学校的网站地址。

### 3. 运行

```powershell
python videoHelper.py
```

按终端提示选择课程。需要查看命令行选项时，运行 `python videoHelper.py --help`。

## 仓库结构

```text
yuketang4SCUT/
├── videoHelper.py       # 主程序
├── config.example.json  # 空白配置示例
├── requirements.txt     # Python 依赖
├── README.md            # 项目说明
├── LICENSE             # 许可证
├── .gitignore          # 排除本地配置、缓存和备份
├── .gitattributes      # 统一 Git 文本换行
└── .editorconfig       # 统一编辑器格式
```

`config.local.json` 由使用者在本地创建，已被 Git 忽略。不要将真实 Cookie 写回源码或配置示例。

## 来源与验证

感谢 [hewei2723/yuketang](https://github.com/hewei2723/yuketang) 提供项目基础，以及 [heyblackC/yuketangHelper](https://github.com/heyblackC/yuketangHelper) 提供的早期脚本思路。

代码已进行离线检查；实际进度以服务器返回和网页记录为准。平台接口或校验规则发生变化时，可能需要继续适配。
