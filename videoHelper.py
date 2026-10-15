# -*- coding: utf-8 -*-
# version 5 - reliability and batch heartbeat fixes
# Original author: zk chen
import argparse
import json
import math
import re
import secrets
import time
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests


# 登录信息只放在本地 config.local.json 中，该文件已由 .gitignore 排除。
# 首次使用：复制 config.example.json 为 config.local.json，再填写自己的值。
def load_local_config():
    path = Path(__file__).resolve().with_name("config.local.json")
    try:
        content = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return {}
    except OSError:
        raise SystemExit("无法读取 config.local.json，请检查文件权限。") from None
    try:
        config = json.loads(content)
    except ValueError:
        raise SystemExit(
            "config.local.json 不是有效的 JSON，请检查引号和逗号。"
        ) from None
    if not isinstance(config, dict):
        raise SystemExit("config.local.json 必须是 JSON 对象。")
    for name in ("csrftoken", "sessionid", "university_id", "url_root"):
        if name in config and not isinstance(config[name], str):
            raise SystemExit(
                f"config.local.json 中的 {name} 必须是用双引号包围的字符串。"
            )
    return config


_local_config = load_local_config()
csrftoken = _local_config.get("csrftoken", "").strip()
sessionid = _local_config.get("sessionid", "").strip()
university_id = _local_config.get("university_id", "2627").strip()
url_root = _local_config.get("url_root", "https://scut.yuketang.cn/").strip()
learning_rate = 20  # 每条心跳推进秒数；也可用 --rate 调整
# 以下字段通常不用修改。
heartbeat_batch_size = 100
request_interval = 0.5
request_timeout = (5, 20)
max_retries = 3
max_stalled_rounds = 12
max_video_seconds = 1800
user_id = ""
leaf_type = {"video": 0, "homework": 6, "exam": 5, "recommend": 3, "discussion": 4}


class HelperError(RuntimeError):
    """可以直接展示给使用者的错误。"""


class AuthenticationError(HelperError):
    pass


def normalize_root(value):
    parts = urlsplit(value.strip())
    if parts.scheme not in ("https", "http") or not parts.netloc or parts.username:
        raise HelperError(
            "url_root 必须是完整的网站地址，例如 https://scut.yuketang.cn/"
        )
    # 页面地址 /pro/courselist 不是 API 前缀，API 从域名根目录开始。
    return urlunsplit((parts.scheme, parts.netloc, "/", "", ""))


def create_session():
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Cookie": f"csrftoken={csrftoken}; sessionid={sessionid}; university_id={university_id}; platform_id=3",
            "x-csrftoken": csrftoken,
            "university-id": university_id,
            "xtbz": "cloud",
            "Referer": normalize_root(url_root),
        }
    )
    return session


_session = None


def close_session():
    global _session
    if _session is not None:
        _session.close()
        _session = None


def retry_delay(response):
    value = response.headers.get("Retry-After")
    if value:
        try:
            delay = float(value)
        except ValueError:
            try:
                delay = parsedate_to_datetime(value).timestamp() - time.time()
            except (TypeError, ValueError, OverflowError):
                delay = 2
    else:
        match = re.search(
            r"Expected available in\s*([0-9.]+)\s*seconds?", response.text, re.I
        )
        delay = float(match.group(1)) if match else 2
    if not math.isfinite(delay) or delay > 120:
        raise HelperError("服务器要求等待超过 120 秒，请稍后重新运行。")
    return max(0, delay) + 0.5


def request_json(method, path, **kwargs):
    global _session
    if _session is None:
        _session = create_session()
    url = normalize_root(url_root) + path.lstrip("/")
    for attempt in range(max_retries + 1):
        try:
            response = _session.request(
                method, url, timeout=request_timeout, allow_redirects=False, **kwargs
            )
        except requests.RequestException as exc:
            # POST 超时不能确定是否已入库，避免立即重复提交。
            if method.upper() == "GET" and attempt < max_retries:
                time.sleep(min(2**attempt, 8))
                continue
            raise HelperError(
                f"{path} 请求失败（{type(exc).__name__}），请检查网络后重新运行。"
            ) from exc
        if response.status_code in (401, 403) or 300 <= response.status_code < 400:
            raise AuthenticationError(
                "登录已失效或无访问权限，请更新 csrftoken、sessionid、university_id。"
            )
        limited = response.status_code == 429 or re.search(
            r"Expected available in\s*[0-9.]+\s*seconds?", response.text, re.I
        )
        if limited:
            if attempt == max_retries:
                raise HelperError(
                    "多次遇到服务器限流，请降低 --batch-size 或增加 --interval。"
                )
            delay = retry_delay(response)
            print(f"服务器限流，等待 {delay:g} 秒后重试当前请求。")
            time.sleep(delay)
            continue  # 保留原 URL、params 和 JSON 请求体
        if (
            response.status_code >= 500
            and method.upper() == "GET"
            and attempt < max_retries
        ):
            time.sleep(min(2**attempt, 8))
            continue
        if response.status_code >= 400:
            raise HelperError(f"接口 {path} 返回 HTTP {response.status_code}。")
        try:
            payload = response.json()
        except ValueError as exc:
            raise HelperError(
                f"接口 {path} 未返回 JSON，请检查域名和登录状态。"
            ) from exc
        if not isinstance(payload, dict):
            raise HelperError(f"接口 {path} 返回了无法识别的数据结构。")
        if payload.get("success") is False:
            raise HelperError(f"接口 {path} 拒绝请求，请检查登录状态或降低速率。")
        if payload.get("code") in (401, 403, "401", "403"):
            raise AuthenticationError("接口提示登录失效，请更新 Cookie。")
        # 某些旧接口只通过 code 表示错误，不提供 success。
        code = payload.get("code")
        if (
            code is not None
            and str(code) not in ("0", "200")
            and payload.get("success") is not True
        ):
            raise HelperError(f"接口 {path} 返回错误码 {code}。")
        return payload


def nonnegative_number(value, name, default=0):
    if value is None or value == "":
        return float(default)
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise HelperError(f"接口的 {name} 字段不是数字。") from exc
    if not math.isfinite(result) or result < 0:
        raise HelperError(f"接口的 {name} 字段无效。")
    return result


def get_progress(video_id, cid, current_user_id, classroomid):
    payload = request_json(
        "GET",
        "video-log/get_video_watch_progress/",
        params={
            "cid": cid,
            "user_id": current_user_id,
            "classroom_id": classroomid,
            "video_type": "video",
            "vtype": "rate",
            "video_id": video_id,
            "snapshot": 1,
            "term": "latest",
            "uv_id": university_id,
        },
    )
    data = payload.get("data")
    if not isinstance(data, dict):
        raise HelperError("无法读取视频进度：接口缺少 data，请检查登录状态。")
    item = data.get(str(video_id))
    if item is None:
        if data:
            raise HelperError(f"进度接口中找不到视频 {video_id}。")
        item = {}  # 未开始学习的视频可能返回空对象
    if not isinstance(item, dict):
        raise HelperError("视频进度结构异常。")
    rate = nonnegative_number(item.get("rate"), "rate")
    watched = nonnegative_number(item.get("watch_length"), "watch_length")
    completed = str(item.get("completed", "0")).lower() in ("1", "true") or rate >= 1
    duration = nonnegative_number(
        item.get("duration", item.get("video_duration")), "duration"
    )
    return rate, watched, completed, duration


def one_video_watcher(video_id, video_name, cid, user_id, classroomid, skuid):
    video_id, classroomid = str(video_id), str(classroomid)
    rate, video_frame, completed, duration = get_progress(
        video_id, cid, user_id, classroomid
    )
    if completed:
        print(f"{video_name} 已经学习完毕，跳过。")
        return 1
    print(f"{video_name}，从 {rate:.1%} 开始。")
    page_id = video_id + "_" + secrets.token_hex(4)
    sequence, stalled = 0, 0
    started = time.monotonic()
    for batch in range(1000):
        if time.monotonic() - started >= max_video_seconds:
            raise HelperError(
                f"{video_name} 已达到单视频时间上限，请检查平台是否接受进度。"
            )
        heart_data = []
        timestamp = int(time.time() * 1000)
        for index in range(heartbeat_batch_size):
            position = min(video_frame, duration) if duration else video_frame
            heart_data.append(
                {
                    "i": 5,
                    "et": "loadeddata",
                    "p": "web",
                    "n": "ali-cdn.xuetangx.com",
                    "lob": "cloud4",
                    "cp": position,
                    "fp": 0,
                    "tp": 0,
                    "sp": 2,
                    "ts": str(timestamp),
                    "u": int(user_id),
                    "uip": "",
                    "c": cid,
                    "v": int(video_id),
                    "skuid": skuid,
                    "classroomid": classroomid,
                    "cc": video_id,
                    # 没有时长字段时保留旧协议兼容值，不据此判断完成。
                    "d": duration or 4976.5,
                    "pg": page_id,
                    "sq": sequence,
                    "t": "video",
                }
            )
            sequence += 1
            video_frame = position + learning_rate
            if duration and position >= duration:
                break
        request_json("POST", "video-log/heartbeat/", json={"heart_data": heart_data})
        # 在查询前等待，给服务端时间写入本批进度。
        time.sleep(max(request_interval, min(stalled, 3)))
        new_rate, watched, completed, new_duration = get_progress(
            video_id, cid, user_id, classroomid
        )
        print(f"学习进度：{new_rate:.1%}（第 {batch + 1} 批）")
        if completed:
            print(f"视频 {video_id} {video_name} 学习完成！")
            return 1
        if new_rate > rate:
            stalled = 0
        else:
            stalled += 1
            if stalled >= max_stalled_rounds:
                raise HelperError(
                    f"{video_name} 连续 {stalled} 批进度未增加，已停止。"
                    "可尝试 --rate 4 --batch-size 3 --interval 2；"
                    "若仍无进度，请检查 Cookie 或平台接口。"
                )
        rate = new_rate
        video_frame = max(video_frame, watched)
        duration = new_duration or duration
    raise HelperError(f"{video_name} 达到最大批次数，已停止。")


def get_videos_ids(course_name, classroom_id, course_sign):
    payload = request_json(
        "GET",
        "mooc-api/v1/lms/learn/course/chapter",
        params={
            "cid": classroom_id,
            "term": "latest",
            "uv_id": university_id,
            "sign": course_sign,
        },
    )
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("course_chapter"), list):
        raise HelperError("无法读取课程章节，请检查课程权限或接口是否变更。")
    videos = {}

    def collect(node):
        if isinstance(node, list):
            for child in node:
                collect(child)
        elif isinstance(node, dict):
            if str(node.get("leaf_type")) == str(leaf_type["video"]) and "id" in node:
                videos[node["id"]] = str(node.get("name", node["id"]))
            for key in ("section_leaf_list", "leaf_list"):
                collect(node.get(key, []))

    collect(data["course_chapter"])
    print(f"{course_name} 共有 {len(videos)} 个视频。")
    return videos


def parse_options():
    parser = argparse.ArgumentParser(
        description="雨课堂视频助手：修复接口地址、限流及进度检测，支持批量心跳。"
    )
    parser.add_argument(
        "--rate", type=float, default=learning_rate, help="每条心跳推进的秒数，默认 20"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=heartbeat_batch_size,
        help="每批心跳条数，默认 100",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=request_interval,
        help="每批等待秒数，默认 0.5",
    )
    parser.add_argument(
        "--course", type=int, help="课程编号；0 表示全部；省略时交互选择"
    )
    options = parser.parse_args()
    if not math.isfinite(options.rate) or not 0 < options.rate <= 60:
        parser.error("--rate 必须大于 0 且不超过 60")
    if not 1 <= options.batch_size <= 100:
        parser.error("--batch-size 必须在 1～100 之间")
    if not math.isfinite(options.interval) or options.interval < 0.5:
        parser.error("--interval 必须至少为 0.5 秒")
    return options


def main():
    global user_id, learning_rate, heartbeat_batch_size, request_interval
    options = parse_options()
    learning_rate, heartbeat_batch_size, request_interval = (
        options.rate,
        options.batch_size,
        options.interval,
    )
    if not all(
        str(value).strip() and str(value).strip().lower() != "yours"
        for value in (csrftoken, sessionid, university_id)
    ):
        raise AuthenticationError(
            "请复制 config.example.json 为 config.local.json，并填写自己的 Cookie 和 university_id。"
        )
    identity = request_json("GET", "edu_admin/check_user_session/")
    identity_data = identity.get("data")
    current_id = identity.get("user_id")
    if current_id is None and isinstance(identity_data, dict):
        current_id = identity_data.get("user_id")
    if current_id is None or not str(current_id).isdigit() or int(current_id) <= 0:
        raise AuthenticationError("无法获取 user_id，请更新登录 Cookie。")
    user_id = str(current_id)
    payload = request_json(
        "GET",
        "mooc-api/v1/lms/user/user-courses/",
        params={
            "status": 1,
            "page": 1,
            "no_page": 1,
            "term": "latest",
            "uv_id": university_id,
        },
    )
    data = payload.get("data")
    courses = data.get("product_list") if isinstance(data, dict) else None
    if not isinstance(courses, list):
        raise HelperError("无法获取课程列表，请检查登录状态和 university_id。")
    if not courses:
        print("当前账号没有可学习的课程。")
        return 0
    required_keys = (
        "course_name",
        "classroom_id",
        "course_sign",
        "sku_id",
        "course_id",
    )
    if any(
        not isinstance(course, dict) or any(key not in course for key in required_keys)
        for course in courses
    ):
        raise HelperError("课程信息字段不完整，平台接口可能发生了变更。")
    for index, course in enumerate(courses, 1):
        print(f"编号：{index} 课名：{course['course_name']}")
    number = options.course
    if number is not None and not 0 <= number <= len(courses):
        raise HelperError(f"课程编号必须在 0～{len(courses)} 之间。")
    while number is None:
        text = input("请输入课程编号，0 表示全部：\n").strip()
        try:
            candidate = int(text)
        except ValueError:
            candidate = -1
        if not 0 <= candidate <= len(courses):
            print("输入不合法，请重新输入。")
            continue
        number = candidate
    selected = courses if number == 0 else [courses[number - 1]]
    completed = failed = 0
    print(
        f"当前参数：每批 {heartbeat_batch_size} 条，每条推进 {learning_rate:g} 秒，间隔 {request_interval:g} 秒。"
    )
    for course in selected:
        try:
            videos = get_videos_ids(
                course["course_name"], course["classroom_id"], course["course_sign"]
            )
        except AuthenticationError:
            raise
        except HelperError as exc:
            print(f"跳过课程：{exc}")
            failed += 1
            continue
        for video_id, name in videos.items():
            try:
                completed += one_video_watcher(
                    video_id,
                    name,
                    course["course_id"],
                    user_id,
                    course["classroom_id"],
                    course["sku_id"],
                )
            except AuthenticationError:
                raise
            except HelperError as exc:
                print(f"视频未完成：{exc}")
                failed += 1
    print(f"处理结束：完成或已完成 {completed} 个视频；失败 {failed} 项。")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n已停止，再次运行会读取服务器保存的进度。")
        raise SystemExit(130)
    except EOFError:
        print("无法读取输入，请在终端运行，或使用 --course 指定课程。")
        raise SystemExit(1)
    except HelperError as exc:
        print(f"错误：{exc}")
        raise SystemExit(1)
    finally:
        close_session()
