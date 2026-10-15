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

当前可运行版本位于 `master` 分支：

```powershell
git clone --branch master https://github.com/LASTNanGuiMi/yuketang4SCUT.git
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
```

脚本会列出课程，按提示输入编号；输入 `0` 处理全部课程。

也可以直接指定课程编号：

```powershell
# 处理编号为 1 的课程
python videoHelper.py --course 1

# 处理全部课程
python videoHelper.py --course 0
```

## 参数怎么调整

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| `--course` | 运行时选择 | 课程列表中的编号，`0` 表示全部 |
| `--batch-size` | `100` | 每批心跳条数，范围为 1～100 |
| `--rate` | `20` | 相邻心跳上报的播放位置增加多少秒，大于 0 且不超过 60 |
| `--interval` | `0.5` | 每批提交后查询进度前的最短等待秒数，至少为 0.5 |

遇到限流或进度不增长时，可以尝试降低参数：

```powershell
python videoHelper.py --rate 4 --batch-size 3 --interval 2
```

查看全部选项：

```powershell
python videoHelper.py --help
```

`--rate` 是上报位置的推进参数，不代表真实播放器的倍速。实际进度取决于服务器是否接受这些记录；增大参数不保证更快。遇到连续停滞时，程序还会增加等待时间。

## 进度是怎么得到的

脚本使用本地 Cookie 查询课程和视频列表，读取已有观看记录，再批量提交视频心跳。每批提交后会重新查询服务器进度，依据返回的 `rate` 和 `completed` 判断是否继续。

脚本本身不下载或播放视频。“请求发送成功”和“服务器认可进度”是两件事，请以终端查询到的进度及网页上的实际记录为准。

## 常见问题

**提示登录失效、无权限或无法获取用户 ID**

重新登录雨课堂，更新 `config.local.json` 中的 Cookie，并核对学校编号和网站地址。

**提示配置文件不是有效的 JSON**

检查是否缺少双引号、漏写逗号，或者在最后一个字段后多写了逗号。可以对照 `config.example.json` 修改。

**连续多批进度没有增加**

先尝试上面的较低参数，再检查 Cookie 和网页进度。若仍无变化，可能需要根据当前平台接口重新排查；反复提高参数不一定有效。

**中途停止后需要从头处理吗**

按 `Ctrl+C` 可以停止。再次运行时会读取服务器已保存的进度；已被服务器标记完成的视频会跳过。

## 文件与登录信息

| 文件 | 用途 | 是否上传到 Git |
| --- | --- | --- |
| `videoHelper.py` | 主程序 | 是 |
| `config.example.json` | 空白配置示例 | 是 |
| `config.local.json` | 自己的真实登录信息 | 否，已设置忽略 |
| `requirements.txt` | Python 依赖 | 是 |
| `.gitignore` | 排除本地配置、缓存和备份 | 是 |

不要把真实 Cookie 写回源码，也不要分享自己的 `config.local.json`。登录信息变更后，只需更新本地配置。

## 验证情况与来源

已进行请求错误处理、限流重试、进度停滞、配置读取等离线验证。平台接口和校验规则可能变化，当前版本的实际效果仍需以自己的运行结果为准。

感谢 [hewei2723/yuketang](https://github.com/hewei2723/yuketang) 提供的项目基础，以及更早的 [heyblackC/yuketangHelper](https://github.com/heyblackC/yuketangHelper) 提供的脚本思路。本仓库整理并说明本次针对 SCUT 使用场景的修复与修改。
