# -*- coding: utf-8 -*-
"""
OK 游戏助手 - 统一管理窗口（WeGame 风格游戏库）

设计原则：本窗口只做「启动器」该做的事，默认不碰原启动器的目录；但 working/ 属于
官方仓库范畴（用户已授权可写），仅在用户明确点击「应用到 working 目录」时才写入：
  - 不碰 <app>/repo（git 仓库，镜像 git 只在本启动器 repos/<key> 内）
  - <app>/working 默认只读；「应用到 working 目录」= 覆盖代码文件 + 保留运行数据，
    单次弹窗确认、先终止进程、不产生备份（用户明确不要备份，省空间）
  - <app>/app.json 只读展示；仅应用成功后才写回 current_version（清残留更新中间态）

WeGame 风格卡片：
  - 封面区（渐变底 + 游戏图标）
  - 状态徽章：未安装 / 已安装 / 运行中 / 可更新
  - 按钮：未安装 ->「安装」（打开官方下载页）；已安装 ->「▶ 启动应用」+「原版管理窗口」
  - 只读展示：版本下拉 + 版本说明（changelog，GitHub compare，失败回退 update_note）
  - 窗口内更新：点「更新到 vX」把目标版本下载到本启动器目录 repos/<key>（真实进度条，
    原启动器目录零触碰）；下载完成后可一键「应用到 working 目录」（覆盖代码、保留运行数据、
    更新 app.json 当前版本），或交回「原版管理窗口」由原启动器完成

已收录游戏助手：
  - 异环 (ok-nte)
  - 鸣潮 (ok-ww)
  - 终末地 (ok-end-field) —— 未安装时显示「安装」，点击打开官方下载页
"""

import sys
import os
import re
import json
import ctypes
import subprocess
import traceback
import urllib.request

from PySide6.QtCore import Qt, QTimer, QThread, Signal, QUrl
from PySide6.QtGui import QIcon, QPixmap, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QWidget, QDialog, QHBoxLayout, QVBoxLayout, QGridLayout,
    QMessageBox, QLabel, QScrollArea, QTextEdit, QProgressBar,
)
from qfluentwidgets import (
    setTheme, Theme, CardWidget, IconWidget, StrongBodyLabel,
    CaptionLabel, PushButton, ComboBox, FluentIcon, IndeterminateProgressBar,
)


# ===== 无需自提权（见下方说明） =====
# 早期版本曾在此处用 runas 重启自己（弹 UAC）以管理员身份运行，因为当时 changelog
# 走 spawn ok-*.exe 的 PyAppify API，而 ok-*.exe 的 manifest 要求管理员（740）。
# 现已改为直接读本地 git 仓库（GitVersionFetcher），只读本地文件、不需要管理员，
# 故删除自提权逻辑：既消除每次启动的 UAC 弹窗 + 命令行闪烁，也不再无谓地重启进程。

# ===== 应用配置（从 config.json 加载，避免硬编码路径） =====
LAUNCHER_DIR = os.path.dirname(os.path.abspath(__file__))
# 图标统一使用 ok-script 官网 project-icons（已缓存到启动器自身 assets 目录），
# 各 app 的 app.json / working 默认只读展示；「应用到 working 目录」为用户主动授权的写入动作。
ASSETS_DIR = os.path.join(LAUNCHER_DIR, "assets")
# 独立镜像仓库目录：clone / fetch  ️只发生在这里，原启动器的 repo/ 完全不碰。
# 目录结构：LAUNCHER_REPOS_DIR/<key>/  （即一份独立的 git 仓库）
REPOS_DIR = os.path.join(LAUNCHER_DIR, "repos")


def load_apps():
    """从 config.json 加载应用列表，并将相对路径拼成绝对路径。

    config.json 里的 exe/app_json/working/pythonw/icon 都相对于 install_root，
    这样他人 clone 后只需改 config.json 的 install_root 即可，无需改动代码。
    """
    cfg_path = os.path.join(LAUNCHER_DIR, "config.json")
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        raise RuntimeError(f"读取配置文件失败: {cfg_path} ({e})")

    root = cfg.get("install_root", "D:/OKApps").replace("/", os.sep)
    apps = []
    for a in cfg.get("apps", []):
        def absify(p):
            if not p:
                return ""
            if os.path.isabs(p):
                return p
            return os.path.join(root, p.replace("/", os.sep))
        app = dict(a)
        app["exe"] = absify(a.get("exe", ""))
        app["app_json"] = absify(a.get("app_json", ""))
        app["working"] = absify(a.get("working", ""))
        app["pythonw"] = absify(a.get("pythonw", ""))
        # icon 优先用绝对配置，否则回退到 assets 目录下的同名文件
        icon = a.get("icon", "")
        app["icon"] = absify(icon) if icon and (os.path.isabs(icon) or "/" in icon) else \
            os.path.join(ASSETS_DIR, f"{a.get('key', 'app')}.png")
        apps.append(app)
    return apps


APPS = load_apps()


def ver_key(v):
    """把版本字符串转成可排序的元组，正式版排在 pre/beta/alpha/rc 前面。

    例: v1.3.4 -> (1,3,4,0,0)；v1.3.4-beta.1 -> (1,3,4,1,1)
    """
    m = re.match(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", v or "")
    nums = [int(m.group(i)) if m and m.group(i) else 0 for i in (1, 2, 3)]
    if any(k in v for k in ("beta", "pre", "alpha", "rc", "-b")):
        pre = 0  # 预发布：排在正式版后面（正式版用 999）
        pm = re.search(r"(?:beta|pre|alpha|rc)[.\-]?(\d*)", v)
        prenum = int(pm.group(1)) if pm and pm.group(1) else 0
    else:
        pre = 999  # 正式版：永远排在预发布前面
        prenum = 0
    return (nums[0], nums[1], nums[2], pre, prenum)


def is_prerelease(v):
    """判断版本是否为预发布（beta/alpha/rc/pre）。"""
    return any(k in (v or "").lower() for k in ("beta", "alpha", "rc", "pre"))


def compare_version(a, b):
    """比较两个版本：a > b 返回 1，a < b 返回 -1，相等返回 0。"""
    ka, kb = ver_key(a), ver_key(b)
    return (ka > kb) - (ka < kb)


def format_version_display(version, current):
    """生成下拉框显示文本：vX.Y.Z 正式版（升级/降级/当前）。

    主卡片 ComboBox 和 UpdateDialog 复用此函数，保证标记一致。
    """
    type_label = "测试版" if is_prerelease(version) else "正式版"
    cmp = compare_version(version, current) if current else 0
    if version == current:
        action_label = "当前"
    elif cmp > 0:
        action_label = "升级"
    elif cmp < 0:
        action_label = "降级"
    else:
        action_label = ""
    if action_label:
        return f"{version} {type_label}（{action_label}）"
    return f"{version} {type_label}"


def parse_repo_from_git_url(git_url):
    """从 git_url 解析 owner/repo；支持 GitHub 与 cnb.cool（后者按同路径试 GitHub）。"""
    for pat in [
        r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
        r"https?://cnb\.cool/([^/]+)/([^/]+?)(?:\.git)?/?$",
    ]:
        m = re.match(pat, git_url)
        if m:
            return m.group(1), m.group(2)
    return None, None


# ⚠️ 重要：cnb.cool 源现在**直接走 cnb.cool 自己的 Gitea 兼容 API** 拉 changelog，
# 不再映射到 GitHub。原因：某些 cnb 镜像在 GitHub 上是独立仓库（名字不同），
# 强制映射会拉到错误内容。典型例子：鸣潮 China 源 cnb 仓库名为 `ok-ww-update2`，
# 而 GitHub 对应仓库是 `ok-ww-update`（无 2），两者更新历史不同——映射到 GitHub
# 后 changelog 内容与原启动器（读 cnb 自身）对不上。
# 异环的 cnb 仓库 `BnanZ0/ok-nte-update` 恰好与 GitHub 同名同内容，是特例，
# 此前误以为是普遍规律。故此处映射表留空，cnb 源一律用 cnb API。
CNB_GITHUB_REPO_MAP = {}


def resolve_github_repo(owner, repo):
    """若 cnb.cool 源有已知的 GitHub 真实仓库，返回真实 owner/repo；否则原样返回。"""
    return CNB_GITHUB_REPO_MAP.get((owner, repo), (owner, repo))


def _normalize_tag(tag):
    """去掉 git peeled ref 后缀 '^{}'，避免 v3.5.28^{} 这种脏 tag 混进列表。"""
    if not tag:
        return tag
    if tag.endswith("^{}"):
        tag = tag[:-3]
    return tag


def fetch_versions_from_git_url(git_url):
    """从 git 远程只读拉取所有 tags，按版本号从新到旧排序。失败返回空列表。"""
    if not git_url:
        return []

    owner, repo = parse_repo_from_git_url(git_url)

    # 1) GitHub API 分页拉全量 tags（最快、最完整；cnb.cool 按同路径走 GitHub）
    if owner and repo:
        tags = []
        try:
            for page in range(1, 11):  # 最多 10 页 = 1000 个版本
                url = f"https://api.github.com/repos/{owner}/{repo}/tags?per_page=100&page={page}"
                req = urllib.request.Request(url, headers={"User-Agent": "ok-launcher/1.0"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    data = json.loads(r.read().decode("utf-8"))
                if not data:
                    break
                tags.extend(_normalize_tag(t["name"]) for t in data if "name" in t)
            if tags:
                return sorted(tags, key=ver_key, reverse=True)
        except Exception:
            pass

    # 2) dulwich 兜底（通吃 GitHub / cnb.cool 等 smart HTTP）
    try:
        from dulwich.client import get_transport_and_path

        client, path = get_transport_and_path(git_url)
        refs = client.get_refs(path)
        tags = []
        for ref_name in refs.keys():
            if isinstance(ref_name, bytes):
                ref_name = ref_name.decode("utf-8", "replace")
            if ref_name.startswith("refs/tags/"):
                tag = _normalize_tag(ref_name.replace("refs/tags/", ""))
                if tag and tag not in tags:
                    tags.append(tag)
        if tags:
            return sorted(tags, key=ver_key, reverse=True)
    except Exception:
        pass

    return []


def fetch_changelog(owner, repo, base, head, limit=10):
    """用 GitHub compare API 拉取 base...head 之间的 commits 列表（只读）。

    返回格式化的多行文本；失败抛异常。limit 控制显示最近 N 条。
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/compare/{base}...{head}"
    req = urllib.request.Request(url, headers={"User-Agent": "ok-launcher/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    commits = data.get("commits", [])
    lines = []
    for c in reversed(commits):  # 从新到旧，和原版窗口一致
        msg = c.get("commit", {}).get("message", "").split("\n")[0].strip()
        author = c.get("commit", {}).get("author", {}).get("name", "")
        if not author:
            author = c.get("author", {}).get("login", "") or ""
        if msg:
            lines.append(f"• {msg}" + (f"（{author}）" if author else ""))
    if not lines:
        return "该版本暂无更新说明。"
    return "\n".join(lines[:limit])


def fetch_changelog_cnb(owner, repo, base, head, limit=10):
    """用 cnb.cool 的 Gitea 兼容 API 拉取 head 版本附近的更新 commits（只读）。

    对应 China 源：changelog 直接来自 cnb 镜像仓库本身（与原启动器一致），
    不再映射到 GitHub（否则会拉到不同仓库的内容）。cnb.cool 的 commits API 形如
    /api/v1/repos/{owner}/{repo}/commits?sha={head}&limit={n}，返回从 head 往前
    的 commit 列表（Gitea 格式），正好对应「目标版本的更新说明」。
    """
    sha = urllib.parse.quote(head, safe="")
    url = (f"https://cnb.cool/api/v1/repos/{owner}/{repo}/commits"
           f"?sha={sha}&limit={limit}")
    req = urllib.request.Request(url, headers={"User-Agent": "ok-launcher/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    lines = []
    for c in data:
        msg = c.get("commit", {}).get("message", "").split("\n")[0].strip()
        author = c.get("author", {}).get("login", "") or ""
        if not author:
            author = c.get("commit", {}).get("author", {}).get("name", "")
        if msg:
            lines.append(f"• {msg}" + (f"（{author}）" if author else ""))
    if not lines:
        return "该版本暂无更新说明。"
    return "\n".join(lines[:limit])


class ChangelogFetcher(QThread):
    """后台拉取 changelog（只读，不影响任何本地文件）。

    根据 git_url 来源分发：
      - cnb.cool 源 → cnb.cool 自身 Gitea API（与原启动器一致，不映射到 GitHub）
      - 其它（github.com 等）→ GitHub compare API
    """
    fetched = Signal(str)
    failed = Signal(str)

    def __init__(self, git_url, owner, repo, base, head, parent=None):
        super().__init__(parent)
        self.git_url = git_url
        self.owner = owner
        self.repo = repo
        self.base = base
        self.head = head

    def run(self):
        try:
            if self.git_url.rstrip("/").startswith("https://cnb.cool/"):
                text = fetch_changelog_cnb(self.owner, self.repo, self.base, self.head)
            else:
                text = fetch_changelog(self.owner, self.repo, self.base, self.head)
            self.fetched.emit(text)
        except Exception as e:
            self.failed.emit(str(e))


def calculate_update_notes(update_notes, current_version, target_version):
    """复刻 PyAppify 的 pyappify.calculate_update_notes：

    从版本列表中取 current → target（含两端）区间内每个版本的 update_note，
    拼接成更新说明。版本列表顺序须与 ``--get-version-list`` 返回一致。
    """
    if not isinstance(update_notes, list):
        return []
    versions = [item for item in update_notes
                if isinstance(item, dict) and item.get("version")]

    def normalize(version):
        return str(version or "").lstrip("v")

    def find_index(version):
        normalized = normalize(version)
        for index, item in enumerate(versions):
            if normalize(item["version"]) == normalized:
                return index
        return None

    target_index = find_index(target_version)
    if target_index is None:
        return []

    current_index = find_index(current_version)
    if current_index is None:
        selected = versions[target_index:]
    else:
        first = min(current_index, target_index)
        last = max(current_index, target_index)
        selected = versions[first:last + 1]

    notes = []
    for item in selected:
        raw = item.get("update_note") or []
        if isinstance(raw, list):
            notes.extend(str(n) for n in raw)
        else:
            notes.append(str(raw))
    return notes


class GitVersionFetcher(QThread):
    """后台从各游戏**本地 git 仓库**读取「版本 + 更新说明」列表。

    为什么不用原启动器的 PyAppify ``--get-version-list`` exe API：
    ok-ww / ok-nte 是 Tauri **单实例**应用，该 API 只能在**已运行的实例内部**被处理
    （单实例插件把参数转发给运行中的实例，再由它的 PyAppify 运行时写回 response 文件）。
    从外部 spawn exe 永远进不了这个模式——要么变成 GUI 首实例（弹出原启动器界面），
    要么参数被单实例插件丢弃，导致 response 为空。证据见 ``ok-ww/logs/app.2026-08-20``：
    我们 spawn 的 ok-ww.exe 直接以 ``running with tauri ui`` 启动成完整 GUI，全程无视
    ``--get-version-list`` 参数。

    因此改为直接读本地仓库：tags -> 版本、tag 提交信息 -> 更新说明，
    这正是 PyAppify 自身用的同一份数据（已用 ``git log -1 --format=%B <tag>`` 与原启动器
    ``get_update_notes`` 输出逐字核对一致，如 ok-ww v3.6.4 的 11 条说明完全吻合）。
    不需要 git 在 PATH——优先用 WorkBuddy 自带的 PortableGit（用户机器位于
    ``~/.workbuddy/binaries/PortableGit``），找不到再回退 app.json 缓存。
    只读本地文件、读本地仓库，**绝不启动任何 exe**，因此不会再弹出原启动器。
    """
    fetched = Signal(list)   # list of {version, update_note}
    failed = Signal(str)

    def __init__(self, exe_path, parent=None):
        super().__init__(parent)
        self.exe_path = exe_path

    @staticmethod
    def _find_git():
        import glob, shutil
        base = os.path.join(os.path.expanduser("~"), ".workbuddy",
                            "binaries", "PortableGit", "versions")
        cands = []
        # PortableGit 版本目录：versions/<ver>/mingw64/bin/git.exe
        cands += glob.glob(os.path.join(base, "*", "mingw64", "bin", "git.exe"))
        which = shutil.which("git")
        if which:
            cands.append(which)
        for p in (r"C:\Program Files\Git\bin\git.exe",
                  r"C:\Program Files (x86)\Git\bin\git.exe"):
            if os.path.isfile(p):
                cands.append(p)
        for c in cands:
            if os.path.isfile(c):
                return c
        return None

    def _emit_cached(self, app_json):
        """git 不可用 / 仓库缺失时的兜底：用 app.json 的 available_versions +
        当前版本 update_note，保证下拉框可用、绝不报“获取失败”。"""
        try:
            with open(app_json, "r", encoding="utf-8") as f:
                aj = json.load(f)
            av = aj.get("available_versions") or []
            cur = aj.get("current_version")
            cur_note = aj.get("update_note") or []
            items = []
            for v in av:
                notes = cur_note if v == cur else []
                items.append({"version": v, "update_note": notes})
            if items:
                self.fetched.emit(items)
                return
        except Exception:
            pass
        self.failed.emit("无法读取版本信息（git 不可用且 app.json 缓存缺失）")

    def run(self):
        exe = self.exe_path
        try:
            key = os.path.splitext(os.path.basename(exe))[0]
            app_root = os.path.dirname(exe)
            repo = os.path.join(app_root, "data", "apps", key, "repo")
            app_json = os.path.join(app_root, "data", "apps", key, "app.json")
            git = self._find_git()
            if not git or not os.path.isdir(repo):
                self._emit_cached(app_json)
                return
            # 版本顺序以 app.json 的 available_versions 为准（最新在前），与 get_version_list 一致
            order = []
            try:
                with open(app_json, "r", encoding="utf-8") as f:
                    order = (json.load(f).get("available_versions") or [])
            except Exception:
                order = []
            out = subprocess.run([git, "-C", repo, "tag"],
                                 capture_output=True, text=True,
                                 encoding="utf-8", errors="replace",
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if out.returncode != 0:
                self._emit_cached(app_json)
                return
            tags = [t.strip() for t in out.stdout.splitlines() if t.strip()]
            tag_set = set(tags)
            ordered = [v for v in order if v in tag_set]
            extra = [t for t in tags if t not in set(ordered)]
            ordered += sorted(extra, reverse=True)   # 仓库有但 app.json 未列的，按版本倒序补在后面
            items = []
            for v in ordered:
                msg = subprocess.run([git, "-C", repo, "log", "-1",
                                      "--format=%B", v],
                                     capture_output=True, text=True,
                                     encoding="utf-8", errors="replace",
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if msg.returncode != 0:
                    notes = []
                else:
                    notes = [ln.strip() for ln in msg.stdout.splitlines()
                             if ln.strip()]
                items.append({"version": v, "update_note": notes})
            if not items:
                self._emit_cached(app_json)
                return
            # 落盘一份原始结果（覆盖写），方便核对，也便于排查与 git 上游的差异
            try:
                _ld = os.path.join(LAUNCHER_DIR, "logs")
                os.makedirs(_ld, exist_ok=True)
                with open(os.path.join(_ld, "versions-{}.json".format(key)),
                          "w", encoding="utf-8") as _f:
                    json.dump(items, _f, ensure_ascii=False, indent=1)
            except Exception:
                pass
            self.fetched.emit(items)
        except Exception as e:
            self.failed.emit(str(e))


def parse_git_progress(line):
    """从 dulwich / git 进度文本解析出百分比（取最后一个 N%）。无则 -1。"""
    if isinstance(line, bytes):
        line = line.decode("utf-8", "replace")
    pct = -1
    for m in re.finditer(r"(\d+)%", line):
        pct = int(m.group(1))
    return pct, (line or "").strip()


def ensure_mirror(key, git_url, target_tag=None, progress_cb=None):
    """在 LAUNCHER_REPOS_DIR/<key> 维护一份独立镜像仓库。

    只写启动器自己的目录，原启动器的 repo/working/app.json 完全不碰。
    首次 clone，之后增量 fetch；可选 checkout 到 target_tag。返回本地仓库目录。
    """
    repo_dir = os.path.join(REPOS_DIR, key)
    os.makedirs(repo_dir, exist_ok=True)
    from dulwich import porcelain
    from dulwich.repo import Repo
    from dulwich.client import get_transport_and_path

    if not os.path.isdir(os.path.join(repo_dir, ".git")):
        porcelain.clone(git_url, repo_dir, progress=progress_cb)
    else:
        repo = Repo(repo_dir)
        try:
            client, path = get_transport_and_path(git_url)
            client.fetch(path, repo, progress=progress_cb)
        except Exception:
            # 增量 fetch 失败不致命：本地已有旧镜像，仍可 checkout 已有 tag
            pass
    if target_tag:
        try:
            repo = Repo(repo_dir)
            porcelain.checkout(repo, target_tag, force=True)
        except Exception:
            pass
    return repo_dir


class MirrorUpdater(QThread):
    """后台把目标 tag 拉到本地镜像仓库（只写 launcher/repos/<key>），发真实进度。"""
    progress = Signal(int, str)   # percent（-1 表示未知），text
    done = Signal(str)            # 本地仓库目录
    failed = Signal(str)

    def __init__(self, key, git_url, target_tag, parent=None):
        super().__init__(parent)
        self.key = key
        self.git_url = git_url
        self.target_tag = target_tag

    def _on_progress(self, line):
        pct, text = parse_git_progress(line)
        self.progress.emit(pct, text)

    def run(self):
        try:
            local = ensure_mirror(
                self.key, self.git_url, self.target_tag, self._on_progress
            )
            self.done.emit(local)
        except Exception as e:
            self.failed.emit(str(e))


# ===== 应用：把本地镜像同步到原启动器的 working/（直接覆盖，不备份）=====
# 说明：写的是官方 app 的 working/，属于官方本地安装目录，可写（用户已授权）。
# 不做整目录备份（占空间），但同步只覆盖"代码文件"，运行数据目录/数据库一律保留，
# 且原启动器本身可从仓库 checkout 任意版本做回滚，无需额外备份。

# working/ 里需要保留、绝不从镜像覆盖的运行数据路径（名匹配或后缀匹配）
_PRESERVE_DIRNAMES = {
    "cache", "logs", "config", "custom_chars", "ok_tasks",
    "screenshots", "data", "__pycache__", ".git", "venv", ".venv",
}
_PRESERVE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}


def _sync_repo_to_working(src_dir, dst_dir):
    """从镜像 src_dir 智能同步到 dst_dir：覆盖代码文件，保留运行数据目录/数据库。

    返回 (ok: bool, msg: str)。返回前会对 dst 目录做最小写入（仅代码文件）。
    """
    import shutil
    from pathlib import Path

    src = Path(src_dir)
    dst = Path(dst_dir)
    if not src.is_dir():
        return False, f"镜像目录不存在: {src_dir}"
    if not dst.is_dir():
        return False, f"目标 working 目录不存在: {dst_dir}"

    copied = skipped = 0
    for src_file in src.rglob("*"):
        if src_file.is_dir():
            continue
        rel = src_file.relative_to(src)
        # 跳过运行数据目录 / 数据库
        if any(p in _PRESERVE_DIRNAMES for p in rel.parts):
            skipped += 1
            continue
        if src_file.suffix in _PRESERVE_SUFFIXES:
            skipped += 1
            continue
        dst_file = dst / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)
        copied += 1
    return True, f"已同步 {copied} 个代码文件，保留 {skipped} 个运行数据文件"


def _kill_app_process(app):
    """通过 PowerShell 精确终止命令行含该 app 的 working 目录的 python/pythonw 进程。"""
    working_dir = app.get("working", "")
    if not working_dir:
        return True, "无 working 路径，跳过终止"
    ps_cmd = (
        "Get-CimInstance Win32_Process -Filter \"Name = 'python.exe' or "
        "Name = 'pythonw.exe'\" | Where-Object { $_.CommandLine -like "
        f"\"*{working_dir}*\" }} | ForEach-Object {{ Stop-Process -Id "
        "$_.ProcessId -Force -ErrorAction SilentlyContinue }}"
    )
    try:
        # text=True 解码 PowerShell 输出可能因 GBK/UTF-8 不匹配抛 UnicodeDecodeError，
        # 显式 errors="replace" 保证 reader 线程不炸、主流程稳定。
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True, text=True, errors="replace", timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as e:  # noqa: BLE001
        return False, f"终止进程失败: {e}"
    return True, "已终止运行中的进程"


def _kill_app_by_title(key):
    """按窗口标题关键字精确终止正在运行的原启动器进程。

    与 _is_process_running 监测同源：PyAppify 打包的启动器运行时进程名是内嵌
    pythonw.exe（无独立 ok-nte.exe 镜像名），且 CommandLine 在 wmic 视角被降权清空，
    无法靠 working 目录匹配——但 tasklist /V 的窗口标题稳定可见（如 "ok-nte v1.3.7"）。
    故直接 tasklist 拿 PID 列表后用 taskkill /PID /F 终止，纯 cmd、GBK、零编码坑。

    返回 (ok: bool, msg: str)。
    """
    try:
        import csv as _csv
        import io as _io
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq pythonw.exe", "/V", "/FO", "CSV", "/NH"],
            capture_output=True, text=True,
            encoding="gbk", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        killed = 0
        for row in _csv.reader(_io.StringIO(out.stdout)):
            # CSV: image,pid,session,ses#,mem,status,user,cpu,window title
            if len(row) >= 9 and key in row[8].lower():
                pid = row[1].strip()
                if pid.isdigit():
                    subprocess.run(
                        ["taskkill", "/PID", pid, "/F", "/T"],
                        capture_output=True,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    killed += 1
        if killed:
            return True, f"已强制关闭 {killed} 个运行中的进程"
        return True, "未发现运行中的进程"
    except Exception as e:  # noqa: BLE001
        return False, f"终止进程失败: {e}"


def apply_mirror_to_working(app, target_version, mirror_dir):
    """把 launcher/repos/<key>/ 镜像的 target_version 应用到原启动器 working/。

    流程：①终止运行进程 ②从镜像同步代码文件到 working/ ③更新 app.json 的 current_version。
    返回 (ok: bool, msg: str)。失败时绝不半途修改 app.json。
    """
    import json

    working_dir = app.get("working", "")
    app_json = app.get("app_json", "")
    if not working_dir or not app_json:
        return False, "缺少 working/app_json 路径配置"

    ok, msg = _kill_app_process(app)
    if not ok:
        return False, msg

    ok, msg = _sync_repo_to_working(mirror_dir, working_dir)
    if not ok:
        return False, msg

    # 同步成功后再更新 app.json 的当前版本（失败也不影响已同步的代码）
    try:
        with open(app_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["current_version"] = target_version
        # 清掉原启动器可能残留的更新中间态
        for k in ("update_state", "update_target_version", "update_error"):
            data.pop(k, None)
        with open(app_json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:  # noqa: BLE001
        return False, f"代码已同步成功，但 app.json 写入失败：{e}（可手动修改 current_version）"

    return True, f"已应用 {target_version} 到 working/"


class ApplyWorker(QThread):
    """后台执行 apply_mirror_to_working，发进度/完成/失败信号。"""
    progress = Signal(str)
    done = Signal(bool, str)   # ok, msg

    def __init__(self, app, target_version, mirror_dir, parent=None):
        super().__init__(parent)
        self.app = app
        self.target_version = target_version
        self.mirror_dir = mirror_dir

    def run(self):
        try:
            self.progress.emit("正在终止应用进程…")
            ok, msg = _kill_app_process(self.app)
            if not ok:
                self.done.emit(False, msg)
                return
            self.progress.emit("正在同步代码到 working 目录（保留运行数据）…")
            ok, msg = _sync_repo_to_working(self.mirror_dir, self.app["working"])
            if not ok:
                self.done.emit(False, msg)
                return
            self.progress.emit("正在更新 app.json 当前版本…")
            import json
            with open(self.app["app_json"], "r", encoding="utf-8") as f:
                data = json.load(f)
            data["current_version"] = self.target_version
            for k in ("update_state", "update_target_version", "update_error"):
                data.pop(k, None)
            with open(self.app["app_json"], "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.done.emit(True, f"已应用 {self.target_version} 到 working/")
        except Exception as e:  # noqa: BLE001
            self.done.emit(False, f"应用失败：{e}")


# ===== 仅读取的工具函数（不写任何 app 目录） =====
def load_app_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_current_profile(data):
    """返回当前 profile 字典（根据 current_profile 从 profiles 里找）。"""
    name = data.get("current_profile", "China")
    for p in data.get("profiles", []) or []:
        if p.get("name") == name:
            return p
    if data.get("profiles"):
        return data["profiles"][0]
    return {}


def make_icon(path):
    try:
        if path and os.path.isfile(path):
            pm = QPixmap(path)
            if not pm.isNull():
                return QIcon(pm)
    except Exception:
        pass
    try:
        return FluentIcon.GAME.icon()
    except Exception:
        return QIcon()


def send_to_trash(path):
    """把文件或目录移入 Windows 回收站（可撤销）。返回 (success, message)。"""
    if not os.path.exists(path):
        return False, f"路径不存在：{path}"

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("wFunc", wintypes.UINT),
            ("pFrom", wintypes.LPCWSTR),
            ("pTo", wintypes.LPCWSTR),
            ("fFlags", wintypes.WORD),
            ("fAnyOperationsAborted", wintypes.BOOL),
            ("hNameMappings", wintypes.LPVOID),
            ("lpszProgressTitle", wintypes.LPCWSTR),
        ]

    FO_DELETE = 0x0003
    FOF_ALLOWUNDO = 0x0040
    FOF_NOCONFIRMATION = 0x0010
    FOF_SILENT = 0x0004

    op = SHFILEOPSTRUCTW()
    op.hwnd = None
    op.wFunc = FO_DELETE
    op.pFrom = path + "\0\0"
    op.pTo = None
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
    op.fAnyOperationsAborted = False
    op.hNameMappings = None
    op.lpszProgressTitle = None

    ret = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if ret == 0 and not op.fAnyOperationsAborted:
        return True, "已移入回收站"
    return False, f"操作失败或已被取消（错误码：{ret}）"


def runas(exe, args_list, cwd):
    """以管理员身份运行（弹 UAC）。args_list 为字符串列表。"""
    params = subprocess.list2cmdline(args_list) if args_list else ""
    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, cwd, 1)
    return ret > 32


def run_exe(parent, exe, args=None, cwd=None, need_admin=False, show_errors=True):
    """运行程序：普通方式失败(740)或 need_admin=True 时用 runas 提权。"""
    if not os.path.isfile(exe):
        if show_errors:
            QMessageBox.critical(parent, "失败", f"找不到可执行文件：\n{exe}")
        return False
    args = args or []
    cwd = cwd or os.path.dirname(exe)
    if need_admin:
        return runas(exe, args, cwd)
    try:
        subprocess.Popen(
            [exe] + args, cwd=cwd, shell=False,
            creationflags=0x00000008,  # DETACHED_PROCESS
        )
        return True
    except OSError as e:
        if getattr(e, "winerror", None) == 740 or "740" in str(e):
            return runas(exe, args, cwd)
        if show_errors:
            QMessageBox.critical(parent, "失败", f"无法启动：\n{exe}\n\n错误：{e}")
        return False
    except Exception as e:
        if show_errors:
            QMessageBox.critical(parent, "失败", f"无法启动：\n{exe}\n\n错误：{e}")
        return False


class TagLabel(QLabel):
    def __init__(self, text, bg="#3a3a44", fg="#ffffff"):
        super().__init__(text)
        self.setStyleSheet(
            f"background-color:{bg}; color:{fg}; border-radius:6px; "
            f"padding:2px 8px; font-size:11px;"
        )
        self.setAlignment(Qt.AlignCenter)


class StatusBadge(QLabel):
    """WeGame 风格状态徽章。"""

    def __init__(self, text, color="#cfcfcf", bg="rgba(255,255,255,0.15)"):
        super().__init__(text)
        self.setStyleSheet(
            f"background-color:{bg}; color:{color}; border-radius:9px; "
            f"padding:3px 12px; font-size:12px; font-weight:600;"
        )
        self.setAlignment(Qt.AlignCenter)


class AppCard(CardWidget):
    """一张游戏卡片。静态部分（封面/名称/徽章/状态行）固定，动态部分按安装状态重建。"""

    def __init__(self, app):
        super().__init__()
        self.app = app
        # 单列竖排：只固定宽度（匹配 760px 容器 - 32px 边距），高度随 changelog 内容自动撑开。
        # 之前 setFixedSize(440, 560) 是为 2 列网格设计的，写死高 560 导致长 changelog 被截。
        self.setFixedWidth(720)

        self._version_map = {}  # display text -> raw tag
        self._changelog_worker = None
        self._version_fetcher = None
        self._version_notes_list = None  # 原启动器返回的 [{version, update_note}]（同源）

        # 静态骨架
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)
        root.setAlignment(Qt.AlignTop)

        # 封面区（渐变底 + 游戏图标）
        self.cover = QLabel()
        self.cover.setFixedHeight(150)
        self.cover.setAlignment(Qt.AlignCenter)
        self.cover.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #3b4256, stop:1 #262b3a); border-radius:10px;"
        )
        root.addWidget(self.cover)

        # 名称 + 状态徽章
        head = QHBoxLayout()
        head.setSpacing(10)
        name = StrongBodyLabel(app["display"])
        name.setStyleSheet("font-size:20px; font-weight:700;")
        head.addWidget(name)
        head.addStretch(1)
        self.badge = StatusBadge("已安装", color="#8dffb0", bg="rgba(45,125,50,0.25)")
        head.addWidget(self.badge)
        # 独立运行态标签：仅运行中时显示「● 运行中」，与徽章（已安装/可更新）、
        # 按钮（强制关闭）三者分工互不重复。
        self.run_tag = QLabel("● 运行中")
        self.run_tag.setStyleSheet(
            "color:#8dffb0; font-size:12px; font-weight:600; padding:2px 4px;"
        )
        self.run_tag.setVisible(False)
        head.addWidget(self.run_tag)
        root.addLayout(head)

        # 信息行：版本 / 配置
        info_row = QHBoxLayout()
        info_row.setSpacing(6)
        self.ver_tag = TagLabel("未知", bg="#616161")
        info_row.addWidget(self.ver_tag)
        self.profile_tag = TagLabel("", bg="#3a3a44")
        info_row.addWidget(self.profile_tag)
        info_row.addStretch(1)
        root.addLayout(info_row)

        self.status_label = CaptionLabel("")
        root.addWidget(self.status_label)

        # 更新进度区（持久，不随 body_box 重建）：原启动器更新时实时反映
        self.update_bar = IndeterminateProgressBar()
        self.update_bar.setFixedHeight(6)
        self.update_bar.setVisible(False)
        root.addWidget(self.update_bar)
        self.update_label = CaptionLabel("")
        self.update_label.setVisible(False)
        root.addWidget(self.update_label)

        # 动态内容容器：根据安装状态重建
        self.body_box = QVBoxLayout()
        self.body_box.setSpacing(10)
        root.addLayout(self.body_box)

        root.addStretch(1)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh_data)
        self._timer.start(5000)

        self.rebuild_body()  # 首次填充

    # ===== 动态内容 =====
    def clear_body(self):
        while self.body_box.count():
            item = self.body_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def rebuild_body(self):
        """根据当前 app.json 是否有效，重建动态区。"""
        self.data = load_app_json(self.app["app_json"])
        self.profile = get_current_profile(self.data)
        # 安装与否以「working/main.py 是否真实存在」为准，不依赖 app.json 的 installed 字段
        # （原启动器有时会把 installed 标错，但 working/ 才是「装了」的事实）
        app_dir = os.path.dirname(self.app["app_json"])
        working_main = os.path.join(app_dir, "working", "main.py")
        self._installed = os.path.isfile(working_main)

        # 封面图标（装好后才有真实图标，未安装用默认）
        self.cover.setPixmap(make_icon(self.app["icon"]).pixmap(96, 96))

        # 徽章与信息行
        if self._installed:
            self.ver_tag.setText(self.data.get("current_version") or "未知")
            self.ver_tag.setStyleSheet(
                "background-color:#2e7d32; color:#ffffff; border-radius:6px; "
                "padding:2px 8px; font-size:11px;"
            )
            prof = self.data.get("current_profile", "")
            self.profile_tag.setText(prof)
            self.profile_tag.setVisible(bool(prof))
            # 仅在空白时才覆盖小灰字，避免抢走"已发起启动"过渡提示
            if not self.status_label.text():
                self.status_label.setText(self.get_status_text())
            self.refresh_badge()
        else:
            self.ver_tag.setText("未安装")
            self.ver_tag.setStyleSheet(
                "background-color:#616161; color:#ffffff; border-radius:6px; "
                "padding:2px 8px; font-size:11px;"
            )
            self.profile_tag.clear()
            self.profile_tag.setVisible(False)
            self.status_label.setText("未检测到本地安装")
            self.badge.setText("未安装")
            self.badge.setStyleSheet(
                "background-color:rgba(255,255,255,0.15); color:#cfcfcf; "
                "border-radius:9px; padding:3px 12px; font-size:12px; font-weight:600;"
            )

        # 动态区
        self.clear_body()
        if self._installed:
            self.build_installed_body()
        else:
            self.build_uninstalled_body()

        # 更新进度（含未安装时若 app.json 仍含更新状态，也显示）
        self.update_progress_ui()

    def build_installed_body(self):
        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.start_btn = PushButton("▶  启动应用")
        self.start_btn.setFixedHeight(42)
        self.start_btn.setStyleSheet(
            "QPushButton { background-color:#2e7d32; color:white; border-radius:8px; "
            "font-weight:600; } QPushButton:hover { background-color:#1b5e20; }"
        )
        # 槽随运行态切换（见 _refresh_start_btn），这里不固定 connect
        btn_row.addWidget(self.start_btn, stretch=2)

        self.manager_btn = PushButton("原版管理窗口")
        self.manager_btn.setToolTip("所有「更新 / 系统设置」都在原版启动器里完成")
        self.manager_btn.setFixedHeight(42)
        self.manager_btn.clicked.connect(self.open_manager)
        btn_row.addWidget(self.manager_btn, stretch=1)
        self.body_box.addLayout(btn_row)

        # 卸载：独立整行、红色描边实体按钮，醒目但不刺眼
        self.uninstall_btn = PushButton("卸载此助手")
        self.uninstall_btn.setFixedHeight(38)
        self.uninstall_btn.setStyleSheet(
            "QPushButton { background-color:rgba(255,82,82,0.10); "
            "color:#ff6b6b; border:1px solid #ff5252; border-radius:8px; "
            "font-weight:600; } "
            "QPushButton:hover { background-color:rgba(255,82,82,0.22); "
            "color:#ff8585; } "
            "QPushButton:pressed { background-color:rgba(255,82,82,0.35); }"
        )
        self.uninstall_btn.setCursor(Qt.PointingHandCursor)
        self.uninstall_btn.clicked.connect(self.uninstall_app)
        self.body_box.addWidget(self.uninstall_btn)

        # 更新按钮：已安装卡片总是显示，根据真实完整版本列表判断"是否有可更新版本"
        self.update_btn = PushButton("检查更新中…")
        self.update_btn.setFixedHeight(38)
        self.update_btn.setCursor(Qt.PointingHandCursor)
        self.update_btn.clicked.connect(self.open_update_dialog)
        self.body_box.addWidget(self.update_btn)
        self.refresh_update_button()  # 用当前已知信息立即刷一次

        # 查看版本（只读下拉）
        ver_row = QHBoxLayout()
        ver_row.setSpacing(10)
        ver_row.addWidget(CaptionLabel("查看版本"))
        self.ver_combo = ComboBox()
        self.ver_combo.setMinimumWidth(200)
        self.ver_combo.setPlaceholderText("选择版本查看说明...")
        self.populate_versions()
        ver_row.addWidget(self.ver_combo)

        self.refresh_btn = PushButton("↻ 刷新")
        self.refresh_btn.setFixedHeight(32)
        self.refresh_btn.setFixedWidth(78)
        self.refresh_btn.setToolTip("重新从网络拉取最新版本列表与更新说明")
        self.refresh_btn.clicked.connect(self.manual_refresh)
        ver_row.addWidget(self.refresh_btn)
        ver_row.addStretch(1)
        self.body_box.addLayout(ver_row)

        # 版本说明（changelog，只读）
        self.body_box.addWidget(CaptionLabel("版本说明"))
        self.changelog_text = QTextEdit()
        self.changelog_text.setReadOnly(True)
        # 自适应高度：内容少时 ≥120px 紧凑显示；内容多时按 commit 行数自动撑开。
        # 单列竖排布局下卡片可自由变高，不再设 maxHeight 截断（之前 360px 对长 commit 列表仍不够）。
        # QTextEdit 默认 sizeHint 基于 viewport，不会随 document 增长——需要监听 contentsChanged
        # 主动把 minHeight 调成「document 高度 + 边框 + 内边距」，才能让卡片随 changelog 自由撑高。
        self.changelog_text.setMinimumHeight(120)
        self.changelog_text.setPlaceholderText("选择目标版本后显示更新内容...")
        self.changelog_text.setStyleSheet(
            "QTextEdit { background-color: rgba(0,0,0,0.12); border-radius:6px; "
            "padding:6px; border:none; }"
        )
        self.changelog_text.document().contentsChanged.connect(self._adjust_changelog_height)
        self.body_box.addWidget(self.changelog_text)

        self.ver_combo.currentTextChanged.connect(self.on_version_changed)
        self.load_changelog()  # 初始状态也加载一次

    def build_uninstalled_body(self):
        # 未安装：只有「安装」按钮
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.install_btn = PushButton("安装")
        self.install_btn.setFixedHeight(42)
        self.install_btn.setStyleSheet(
            "QPushButton { background-color:#1976d2; color:white; border-radius:8px; "
            "font-weight:600; } QPushButton:hover { background-color:#1565c0; }"
        )
        self.install_btn.clicked.connect(self.install_app)
        btn_row.addWidget(self.install_btn, stretch=1)
        self.body_box.addLayout(btn_row)

        hint = CaptionLabel(
            "未检测到本地安装。\n点击「安装」打开官方下载页，\n下载安装后本卡片会自动变为「已安装」。"
        )
        hint.setWordWrap(True)
        self.body_box.addWidget(hint)

    # ===== 只读数据 =====
    def manual_refresh(self):
        """手动重新拉取版本列表与说明（只读，不写任何 app 目录）。"""
        self.data = load_app_json(self.app["app_json"])
        self.profile = get_current_profile(self.data)
        self.populate_versions()  # 重新填缓存版本 + 后台拉取完整 github 版本
        self.load_changelog()

    def _adjust_changelog_height(self):
        """按 document 实际高度调整 changelog_text 的 minHeight，让卡片随 commit 列表自动撑开。

        QTextEdit 默认 sizeHint 基于 viewport，不会随 document 增长——必须手动把
        minHeight 设成「document 高度 + 边框 + 内边距」。监听 contentsChanged 后，
        setPlainText/setHtml 一变文档就触发，连带父卡片布局也跟着撑高。
        """
        if not hasattr(self, "changelog_text"):
            return
        doc_h = int(self.changelog_text.document().size().height())
        # frameWidth()*2（上下边框）+ 文档上下内边距 + 4px 微调余量
        extra = self.changelog_text.frameWidth() * 2 + 6
        self.changelog_text.setMinimumHeight(max(120, doc_h + extra))

    def refresh_data(self):
        data = load_app_json(self.app["app_json"])
        now_installed = bool(data)
        if now_installed != self._installed:
            # 用户装好/卸载后刷新整张卡片动态区
            self.rebuild_body()
            return
        if not self._installed:
            return
        self.data = data
        self.profile = get_current_profile(self.data)
        # 仅在空白时才覆盖小灰字，避免抢走"已发起启动"过渡提示
        if not self.status_label.text():
            self.status_label.setText(self.get_status_text())
        self.refresh_badge()
        self.update_progress_ui()
        new_ver = self.data.get("current_version", "") or "未知"
        if self.ver_tag.text() != new_ver:
            self.ver_tag.setText(new_ver)
            self.populate_versions()
            self.load_changelog()
            self.refresh_update_button()

    def _is_process_running(self):
        """判定本 app 对应的原启动器是否真实在跑（兜底 app.json.running 不可靠）。

        监测目标就是那个 exe 程序本体（如 ok-nte.exe）。判定优先级：
          1）先看进程表里是否有该 exe 的镜像名（tasklist /FI IMAGENAME）——最直接、最准；
          2）PyAppify 打包的启动器常以内嵌 pythonw.exe 方式运行（exe 主体藏在 pythonw
             里，进程表里见不到 ok-nte.exe 镜像名，只见 pythonw.exe），且 PyAppify
             会把 CommandLine/ExecutablePath 在 wmic 视角下清空（token 降权），无法靠
             命令行匹配 working 目录。**唯一可靠线索是窗口标题**（tasklist /V CSV 第 9
             列），异环标题固定含 "ok-nte"、鸣潮含 "ok-ww" 等。tasklist 走纯 cmd、
             GBK 编码与 encoding="gbk" 完美匹配，不会有 PowerShell 那种 UTF-16/UTF-8
             编码混乱的坑（曾因 encoding="gbk" 解 PowerShell stdout 抛 UnicodeDecodeError
             导致整条路径静默 return False 的根因）。

        所有子进程走 CREATE_NO_WINDOW，不弹黑窗。
        """
        try:
            exe = self.app.get("exe", "")
            key = os.path.basename(exe).lower().removesuffix(".exe")  # "ok-nte"
            if not key:
                return False

            import subprocess as _sp
            import csv as _csv
            import io as _io
            flags = getattr(_sp, "CREATE_NO_WINDOW", 0)

            # ① 优先查 exe 镜像名（某些版本/状态下进程表里会有 ok-nte.exe）
            out = _sp.run(
                ["tasklist", "/FI", f"IMAGENAME eq {key}.exe", "/NH"],
                capture_output=True, text=True,
                encoding="gbk", errors="replace", creationflags=flags,
            )
            if f"{key}.exe" in out.stdout.lower():
                return True

            # ② 回退：pythonw 形态运行时，按窗口标题定位（cmd GBK、稳）
            #    限定 /FI pythonw.exe 避免扫全表（200 进程会阻塞 2~5 秒）
            out = _sp.run(
                ["tasklist", "/FI", "IMAGENAME eq pythonw.exe",
                 "/V", "/FO", "CSV", "/NH"],
                capture_output=True, text=True,
                encoding="gbk", errors="replace", creationflags=flags,
            )
            for row in _csv.reader(_io.StringIO(out.stdout)):
                # CSV: image,pid,session,ses#,mem,status,user,cpu,window title
                if len(row) >= 9 and key in row[8].lower():
                    return True
            return False
        except Exception:
            return False

    def refresh_badge(self):
        """根据更新/安装状态刷新徽章（仅承载「未安装 / 已安装 / 可更新」语义）。

        运行态由三个独立控件分工，互不重复：
          - 徽章：只显示「已安装 / 可更新 vX」（不写"运行中"）
          - run_tag（徽章右侧独立标签）：仅运行中时显示「● 运行中」绿字
          - 启动按钮：运行中时改写「强制关闭」红底（点它二次确认后杀进程）
        运行判定走 _is_process_running 兜底（app.json.running 不可靠）。
        """
        d = self.data
        running = self._is_process_running() or bool(d.get("running"))
        # 按钮随运行态切换（启动应用 / 强制关闭）
        self._refresh_start_btn(running=running)
        # run_tag：仅运行中可见
        if hasattr(self, "run_tag"):
            self.run_tag.setVisible(bool(running))
        if running:
            self.badge.setText("已安装")
            self.badge.setStyleSheet(
                "background-color:rgba(45,125,50,0.25); color:#8dffb0; "
                "border-radius:9px; padding:3px 12px; font-size:12px; font-weight:600;"
            )
            return
        versions = d.get("available_versions", []) or []
        current = d.get("current_version", "")
        if versions and current and versions[0] != current:
            self.badge.setText(f"可更新 {versions[0]}")
            self.badge.setStyleSheet(
                "background-color:rgba(255,152,0,0.25); color:#ffb74d; "
                "border-radius:9px; padding:3px 12px; font-size:12px; font-weight:600;"
            )
            return
        self.badge.setText("已安装")
        self.badge.setStyleSheet(
            "background-color:rgba(45,125,50,0.25); color:#8dffb0; "
            "border-radius:9px; padding:3px 12px; font-size:12px; font-weight:600;"
        )

    def _refresh_start_btn(self, running: bool):
        """根据运行态切换「启动/关闭」按钮：未运行→「▶ 启动应用」（绿、启动）；
        运行中→「强制关闭」（红、终止进程）。槽随状态动态切换，避免误触发。

        与徽章同源（都基于 _is_process_running）。运行中时按钮可点，点一下直接
        taskkill 掉窗口标题含本 app key 的 pythonw 进程（见 _kill_app_by_title），
        比灰着不能点更实用；关掉后下次轮询自动回落到「▶ 启动应用」。
        """
        if not hasattr(self, "start_btn"):
            return
        # 先断开旧槽，避免状态切换后记重触发
        try:
            self.start_btn.clicked.disconnect()
        except Exception:
            pass
        if running:
            self.start_btn.setText("强制关闭")
            self.start_btn.setEnabled(True)
            self.start_btn.setStyleSheet(
                "QPushButton { background-color:#c62828; color:white; border-radius:8px; "
                "font-weight:600; } QPushButton:hover { background-color:#8e0000; }"
            )
            self.start_btn.clicked.connect(self._on_force_stop)
        else:
            self.start_btn.setText("▶  启动应用")
            self.start_btn.setEnabled(True)
            self.start_btn.setStyleSheet(
                "QPushButton { background-color:#2e7d32; color:white; border-radius:8px; "
                "font-weight:600; } QPushButton:hover { background-color:#1b5e20; }"
            )
            self.start_btn.clicked.connect(self.launch_app)

    def _on_force_stop(self):
        """运行中时「强制关闭」按钮回调：二次确认后终止 ok-nte 进程并刷新。"""
        name = self.app.get("name", os.path.basename(
            self.app.get("exe", "")).lower().removesuffix(".exe"))
        ans = QMessageBox.question(
            self.window(), "强制关闭确认",
            f"确定要强制关闭「{name}」吗？\n\n"
            "该操作会直接终止进程，未保存的数据可能丢失，且无法撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,  # 默认聚焦“否”，防误触
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        key = os.path.basename(self.app.get("exe", "")).lower().removesuffix(".exe")
        ok, msg = _kill_app_by_title(key)
        QMessageBox.information(self.window(), "强制关闭", msg)
        # 立即刷新状态（不依赖下次 5 秒轮询）
        self.refresh_data()

    def refresh_update_button(self):
        """根据下拉框选中的版本（或回退到最新比 current 新的）刷新按钮文案/颜色。

        行为：
          - 下拉选中 > current → "更新到 {X}" 橙色
          - 下拉选中 < current → "降级到 {X}" 蓝色
          - 下拉选中 == current（且后台有更新）→ "更新到 {最新newer}" 橙色
            —— 这样下拉在当前版本时也能立刻看到"有新版本可装"提示
          - 下拉选中 == current（且无更新）→ "已是最新" 灰色
          - 下拉无有效选择 + 后台有更新 → "更新到 {最新newer}" 橙色
          - 下拉无有效选择 + 已是最新 → "已是最新" 灰色
        """
        if not hasattr(self, "update_btn"):
            return
        cur = _normalize_tag(self.data.get("current_version", "")) if self.data else ""

        # 1) 预算"最新比 current 新的"——这是兜底目标
        latest_newer = None
        all_v = getattr(self, "_all_versions", None) or []
        if cur and all_v:
            for v in all_v:
                vn = _normalize_tag(v)
                if vn and compare_version(vn, cur) > 0:
                    latest_newer = vn
                    break

        target = None
        label_prefix = "更新到"

        # 2) 看下拉选中的（仅当 != current 时覆盖 latest_newer；选 current 时不覆盖，
        #    这样按钮会回落到 latest_newer，给出"有新版本可装"的提示）
        if hasattr(self, "ver_combo") and hasattr(self, "_version_map"):
            sel_text = self.ver_combo.currentText()
            sel_raw = self._version_map.get(sel_text)
            if sel_raw:
                sel_norm = _normalize_tag(sel_raw)
                if sel_norm and cur:
                    cmp = compare_version(sel_norm, cur)
                    if cmp > 0:
                        target = sel_norm
                        label_prefix = "更新到"
                    elif cmp < 0:
                        target = sel_norm
                        label_prefix = "降级到"
                    # cmp == 0: 不覆盖，target 保持 None → 走 latest_newer 兜底

        # 3) 兜底 latest_newer
        if not target and latest_newer:
            target = latest_newer
            label_prefix = "更新到"

        # 4) 再兜底到 app.json 缓存（_all_versions 还没拉到的过渡期）
        if not target and self.data:
            avail = self.data.get("available_versions", []) or []
            for v in avail:
                vn = _normalize_tag(v)
                if cur and vn and compare_version(vn, cur) > 0:
                    target = vn
                    label_prefix = "更新到"
                    break

        # 缓存 target，供 open_update_dialog 预选用
        self._current_target = target
        self._current_target_label = (
            f"{label_prefix} {target}" if target else None
        )

        if target:
            # 升降级按钮（升级橙色，降级蓝色以示"回退需谨慎"）
            self.update_btn.setText(f"{label_prefix} {target}")
            self.update_btn.setEnabled(True)
            if label_prefix == "降级到":
                self.update_btn.setStyleSheet(
                    "QPushButton { background-color:rgba(33,150,243,0.15); "
                    "color:#64b5f6; border:1px solid #2196f3; border-radius:8px; "
                    "font-weight:600; } "
                    "QPushButton:hover { background-color:rgba(33,150,243,0.28); }"
                )
            else:
                self.update_btn.setStyleSheet(
                    "QPushButton { background-color:rgba(255,152,0,0.15); "
                    "color:#ffb74d; border:1px solid #ff9800; border-radius:8px; "
                    "font-weight:600; } "
                    "QPushButton:hover { background-color:rgba(255,152,0,0.28); }"
                )
            tip = f"当前 {cur}，{label_prefix} {target}"
            # 特别说明：下拉在当前版本但按钮指向更新的情况
            if hasattr(self, "ver_combo") and hasattr(self, "_version_map"):
                sel_text = self.ver_combo.currentText()
                sel_raw = self._version_map.get(sel_text)
                if sel_raw and cur and _normalize_tag(sel_raw) == cur:
                    tip += "（下拉在当前版本，按钮指向最新可用更新）"
            tip += "（下载写入本启动器目录，下载后可一键应用到 working/）"
            self.update_btn.setToolTip(tip)
        else:
            self.update_btn.setText("已是最新")
            self.update_btn.setEnabled(True)  # 仍可点开看版本/说明
            self.update_btn.setStyleSheet(
                "QPushButton { background-color:rgba(255,255,255,0.05); "
                "color:#9a9a9a; border:1px solid #555; border-radius:8px; "
                "font-weight:500; } "
                "QPushButton:hover { background-color:rgba(255,255,255,0.10); "
                "color:#cccccc; }"
            )
            self.update_btn.setToolTip("当前已是最新版本")

    def get_status_text(self):
        """小灰字 status_label 的文案：仅承担"启动过渡"提示，运行态完全交给徽章。

        之前版本小灰字会显示"运行中/未运行"，跟徽章 1:1 复读（信息冗余）。
        现在空字符串：徽章负责总结态（运行中/已安装/未安装/可更新），
        小灰字仅在刚点启动瞬间显示"已发起启动（等待窗口出现）"，
        5 秒后由 launch_app 的 QTimer.singleShot 清空，回到空白。
        """
        return ""

    def _human_update_state(self, state):
        """把原启动器写的 update_state 翻成中文阶段名。"""
        s = (state or "").lower()
        if any(k in s for k in ("check", "detect", "检测")):
            return "检测更新"
        if any(k in s for k in ("download", "下载")):
            return "下载中"
        if any(k in s for k in ("extract", "unzip", "解压", "decompress")):
            return "解压中"
        if any(k in s for k in ("install", "安装")):
            return "安装中"
        if any(k in s for k in ("finish", "done", "完成")):
            return "即将完成"
        return state or "进行中"

    def update_progress_ui(self):
        """根据 app.json 的 update_state 显示更新进度（只读，不写任何文件）。"""
        d = self.data or {}
        state = (d.get("update_state") or "").strip()
        err = d.get("update_error")

        # 空闲：隐藏
        if not state or state.lower() == "idle":
            self.update_bar.setVisible(False)
            self.update_label.setVisible(False)
            return

        # 出错：红字提示，隐藏进度条
        if "error" in state.lower() or "fail" in state.lower() or err:
            self.update_bar.setVisible(False)
            self.update_label.setVisible(True)
            self.update_label.setStyleSheet("color:#ff6b6b; font-size:12px;")
            msg = str(err) if err else state
            self.update_label.setText(f"更新失败：{msg}")
            return

        # 进行中：显示滚动进度条 + 阶段文字（原启动器未提供精确百分比）
        target = d.get("update_target_version") or ""
        label = f"更新中：{self._human_update_state(state)}"
        if target:
            label += f" → {target}"
        self.update_bar.setVisible(True)
        self.update_label.setVisible(True)
        self.update_label.setStyleSheet("color:#ffb74d; font-size:12px;")
        self.update_label.setText(label)

    def on_version_changed(self):
        """下拉框选中版本变化：刷新版本说明 + 刷新更新/降级按钮。"""
        self.load_changelog()
        self.refresh_update_button()

    def _ensure_current_in_versions(self, versions):
        """确保 current 在 versions 列表里（app.json 可能漏写当前版本，导致下拉里看不到）。

        不强制置顶：按版本号（newest first）插入到正确位置，让 current 出现在它本该在的位置。
        用 ver_key 做存在性比较，避免 refs/tags/vX.Y.Z^{} 这种带 ref 前缀的形态被漏判。
        """
        cur = _normalize_tag(self.data.get("current_version", "")) if self.data else ""
        if not cur:
            return versions
        cur_key = ver_key(cur)
        # 已存在（按 ver_key 比较，含 v 前缀/ refs/tags/ 前缀 / ^{} 后缀的形态都能匹配）就不动
        if any(ver_key(_normalize_tag(v)) == cur_key for v in versions):
            return versions
        cur_n = _normalize_tag(cur)
        # current 不在列表里 → 按 ver_key 排序插入到正确位置（newest first）
        result = list(versions)
        inserted = False
        for i, v in enumerate(versions):
            if ver_key(_normalize_tag(v)) < cur_key:
                result.insert(i, cur_n)
                inserted = True
                break
        if not inserted:
            # current 比所有列出的版本都旧（或无可比）→ 追加到末尾
            result.append(cur_n)
        return result

    def populate_versions(self):
        self.ver_combo.blockSignals(True)
        self.ver_combo.clear()
        self._version_map.clear()
        current = _normalize_tag(self.data.get("current_version", ""))
        versions = self._ensure_current_in_versions(
            self.data.get("available_versions", []) or []
        )
        seen = set()
        for v in versions:
            v = _normalize_tag(v)
            if v in seen:
                continue
            seen.add(v)
            display = format_version_display(v, current)
            self._version_map[display] = v
            self.ver_combo.addItem(display)
        # 打开启动器时默认跳到最新版本，让用户一眼看到有没有更新
        if versions:
            self.ver_combo.setCurrentIndex(0)
        self.ver_combo.blockSignals(False)

        # 后台从各游戏本地 git 仓库读取「版本 + 更新说明」（与原启动器同源，
        # 数据完全一致；不再 spawn 原启动器 exe，避免弹出原启动器 GUI）。只读。
        exe = self.app.get("exe", "")
        if exe and os.path.isfile(exe):
            if self._version_fetcher and self._version_fetcher.isRunning():
                self._version_fetcher.requestInterruption()
                self._version_fetcher.wait(1000)
            worker = GitVersionFetcher(exe, parent=self)
            worker.fetched.connect(self._on_versions_fetched)
            worker.failed.connect(self._on_version_fetch_failed)
            worker.start()
            self._version_fetcher = worker
            self._version_fetch_started = True
            # 异步请求刚发出去时，先在 changelog 上提示一下"正在拉取"，避免用户看到缓存说明
            if hasattr(self, "changelog_text") and self.changelog_text.toPlainText().startswith("该版本"):
                self.changelog_text.setPlainText("正在从原启动器拉取版本说明…")
        else:
            # 无 exe（如未安装）时保留缓存列表，changelog 走兜底说明
            pass

    def _on_versions_fetched(self, items):
        """原启动器版本列表（含 update_note）拉取完成：刷新下拉框与说明缓存。"""
        if not items or not hasattr(self, "ver_combo"):
            return
        # items: 原启动器返回的 list of {version, previous_version, update_note}
        notes_list = [it for it in items
                      if isinstance(it, dict) and it.get("version")]
        if not notes_list:
            return
        self._version_notes_list = notes_list
        version_strings = [_normalize_tag(it["version"]) for it in notes_list]
        current = _normalize_tag(self.data.get("current_version", "")) if self.data else ""
        old_text = self.ver_combo.currentText()
        version_strings = self._ensure_current_in_versions(version_strings)

        self.ver_combo.blockSignals(True)
        self.ver_combo.clear()
        self._version_map.clear()
        seen = set()
        for v in version_strings:
            v = _normalize_tag(v)
            if v in seen:
                continue
            seen.add(v)
            display = format_version_display(v, current)
            self._version_map[display] = v
            self.ver_combo.addItem(display)

        # 尽量保留用户已选；若已选项不存在则默认跳到最新版
        idx = self.ver_combo.findText(old_text)
        self.ver_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.ver_combo.blockSignals(False)
        self._all_versions = version_strings  # 缓存完整列表，供更新对话框/按钮使用
        self.load_changelog()
        self.refresh_update_button()

    def _on_version_fetch_failed(self, error_msg):
        """PyAppify exe 拉版本列表失败：把真实错误显示出来（之前是静默吞掉），便于排查。

        仍然保留 app.json 缓存的版本列表 + 缓存的 update_note 作为兜底，不让界面塌掉。
        """
        # 只在 changelog 还没被用户看到真实数据时，才覆盖提示
        current_text = self.changelog_text.toPlainText() if hasattr(self, "changelog_text") else ""
        if current_text.startswith("正在从原启动器拉取版本说明"):
            self.changelog_text.setPlainText(
                "⚠ 原启动器拉取失败，已回退到 app.json 缓存说明：\n"
                f"  错误：{error_msg}\n\n"
            )
        # 把错误记到启动器日志（terminal / log file），方便事后排查
        try:
            print(f"[GitVersionFetcher] 失败: {error_msg}")
        except Exception:
            pass

    def _show_cached_note(self):
        """在线/原启动器拿不到说明时，回退 app.json 缓存的 update_note。"""
        notes = self.data.get("update_note", []) if self.data else []
        if notes:
            self.changelog_text.setPlainText(
                "在线说明获取失败，已回退到最新版缓存说明：\n\n" +
                "\n".join(f"• {n}" for n in notes)
            )
            return
        self.changelog_text.setPlainText("该版本暂不支持在线显示更新说明。")

    def load_changelog(self):
        """显示 current → 目标版本 的更新说明，数据与原启动器同源（PyAppify 版本列表）。"""
        version = self._version_map.get(self.ver_combo.currentText())
        current = _normalize_tag(self.data.get("current_version", "")) if self.data else ""

        if not version:
            self.changelog_text.clear()
            self.changelog_text.setPlaceholderText("选择目标版本后显示更新内容...")
            return

        notes_list = getattr(self, "_version_notes_list", None)
        if notes_list:
            notes = calculate_update_notes(notes_list, current, version)
            if notes:
                self.changelog_text.setPlainText("\n".join(f"• {n}" for n in notes))
                return
            # 拉到了版本列表但拼不出 notes → 大概率是字段名/嵌套结构和我们的假设不一致。
            # 把 PyAppify 真实返回的前 2 条 sample 出来给用户看，方便排查（不要静默兜底）。
            import json as _dj
            sample = _dj.dumps(notes_list[:2], ensure_ascii=False, indent=1)[:1200]
            self.changelog_text.setPlainText(
                "⚠ 原启动器返回了版本列表但未能解析 update_note。\n"
                "调试信息（PyAppify 真实返回的前 2 条原始结构），"
                "请把这段截图给开发者：\n\n" + sample
            )
            return

        # 兜底：版本列表未就绪或网络不通时，回退到 app.json 缓存的 update_note
        self._show_cached_note()

    # ===== 动作：启动（直接跑游戏助手本体，这是启动器的本职） =====
    def launch_app(self):
        app = self.app
        main_script = (self.profile or {}).get("main_script", "main.py")
        admin = bool((self.profile or {}).get("admin", False))
        main_path = os.path.join(app["working"], main_script)
        pythonw = app["pythonw"]

        if not os.path.isfile(main_path):
            QMessageBox.critical(
                self.window(), "启动失败",
                f"找不到助手主程序：\n{main_path}\n\n请点「原版管理窗口」修复安装。",
            )
            return
        if not os.path.isfile(pythonw):
            QMessageBox.critical(
                self.window(), "启动失败",
                f"找不到 Python：\n{pythonw}\n\n请点「原版管理窗口」修复安装。",
            )
            return

        # CWD=working：保证相对 import 与日志落点正确
        ok = run_exe(
            self.window(), pythonw,
            args=[main_path], cwd=app["working"],
            need_admin=admin, show_errors=True,
        )
        if ok:
            self.status_label.setText("已发起启动（等待窗口出现）")
            # 5 秒后清空，避免与徽章长期 1:1 复读"运行中"造成信息冗余
            QTimer.singleShot(5000, lambda: self.status_label.setText(""))

    # ===== 动作：安装（打开官方下载页，不自动下载，不动任何目录） =====
    def install_app(self):
        url = self.app.get("website", "")
        if url:
            QDesktopServices.openUrl(QUrl(url))
            QMessageBox.information(
                self.window(), "安装",
                f"已打开「{self.app['display']}」官方下载页。\n\n"
                "请下载安装包并安装。装好后本窗口会自动识别为「已安装」。",
            )
        else:
            QMessageBox.information(
                self.window(), "安装",
                f"未配置「{self.app['display']}」的官方下载地址。\n"
                "请到 ok-script.com 手动下载。",
            )

    # ===== 动作：打开原版管理窗口（唯一会改配置的入口，由原启动器自己处理） =====
    def open_manager(self):
        run_exe(self.window(), self.app["exe"], [], need_admin=True)

    # ===== 动作：窗口内更新（下载到本启动器目录，真实进度；应用交回原启动器） =====
    def open_update_dialog(self):
        # 先刷新按钮状态，确保 _current_target 是最新的
        self.refresh_update_button()
        avail = self.data.get("available_versions", []) or []
        all_versions = getattr(self, "_all_versions", None) or avail
        versions = self._ensure_current_in_versions(
            all_versions if all_versions else avail
        )
        cur = _normalize_tag(self.data.get("current_version", ""))

        if not versions:
            QMessageBox.information(
                self.window(), "更新",
                f"「{self.app['display']}」暂无可用版本信息，请稍后再试。"
            )
            return

        # 用户在主窗口下拉里选中的版本
        selected_raw = None
        if hasattr(self, "ver_combo") and hasattr(self, "_version_map"):
            selected_raw = self._version_map.get(self.ver_combo.currentText())

        # preselected 优先级：按钮的目标 > 用户下拉选中 > 当前
        # 这样下拉在 current 时点击按钮，对话框也会打开到 latest_newer（而非 current）
        preselected = (
            getattr(self, "_current_target", None)
            or selected_raw
            or cur
            or None
        )

        git_url = (self.profile or {}).get("git_url", "")
        dlg = UpdateDialog(
            self, self.app, cur, versions, git_url, preselected=preselected
        )
        dlg.exec()

    # ===== 动作：卸载（移入回收站，可撤销；不动其他 app 目录） =====
    def uninstall_app(self):
        app_dir = os.path.dirname(self.app["exe"])
        if not os.path.isdir(app_dir):
            QMessageBox.information(
                self.window(), "卸载",
                f"未找到「{self.app['display']}」安装目录：\n{app_dir}"
            )
            return

        # 本启动器如果位于该 app 目录内，无法卸载自身
        launcher_dir = os.path.normcase(os.path.abspath(os.path.dirname(__file__)))
        app_dir_norm = os.path.normcase(os.path.abspath(app_dir))
        if launcher_dir == app_dir_norm or launcher_dir.startswith(app_dir_norm + os.sep):
            QMessageBox.warning(
                self.window(), "无法卸载",
                f"本启动器位于「{self.app['display']}」的安装目录内，无法在此窗口内卸载自身。\n\n"
                f"如需卸载，请关闭本启动器后手动删除目录：\n{app_dir}"
            )
            return

        # 正在运行则先让用户关闭
        if self.data.get("running"):
            QMessageBox.warning(
                self.window(), "无法卸载",
                f"「{self.app['display']}」正在运行，请先关闭后再卸载。"
            )
            return

        reply = QMessageBox.warning(
            self.window(), "确认卸载",
            f"将把「{self.app['display']}」的安装目录移入回收站：\n\n"
            f"{app_dir}\n\n"
            "此操作可撤销（去回收站还原即可）。是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        ok, msg = send_to_trash(app_dir)
        if ok:
            QMessageBox.information(
                self.window(), "卸载完成",
                f"「{self.app['display']}」{msg}。"
            )
            self.rebuild_body()
        else:
            QMessageBox.critical(
                self.window(), "卸载失败",
                f"{msg}\n\n部分文件可能正在使用中。"
                f"请关闭相关程序后重试，或手动删除目录：\n{app_dir}"
            )


class UpdateDialog(QDialog):
    """窗口内「更新到所选版本」对话框：点开始后自动下载并应用到原启动器 working/。

    流程：点「开始更新」→ 一次确认 → 后台下载镜像到 launcher/repos/<key>（作缓存，
    加速下次增量 fetch）→ 自动终止运行进程 → 同步代码到 app['working']（覆盖代码、
    保留缓存/日志/配置/数据库等运行数据，不备份、不占额外空间）→ 写回 app.json 当前版本。
    失败时可点「打开原版管理窗口」交回原启动器处理。
    写的是官方 app 的本地安装目录，属于官方仓库范畴，可写（用户已授权）。
    """

    def __init__(self, parent, app, current, versions, git_url, preselected=None):
        super().__init__(parent)
        self.app = app
        self.git_url = git_url
        self.versions = versions  # 从新到旧
        self.current = current
        self._worker = None

        self.setWindowTitle(f"更新 {app['display']}")
        self.setMinimumWidth(480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(12)

        # 目标版本选择（与主卡片 ComboBox 用同样的格式化：v3.5.28 正式版（当前））
        row = QHBoxLayout()
        row.addWidget(CaptionLabel("目标版本"))
        self.combo = ComboBox()
        self.combo.setMinimumWidth(240)
        cur_n = _normalize_tag(self.current)
        for i, ver in enumerate(versions):
            label = format_version_display(ver, self.current)
            if i == 0:
                # 最新项：把"（升级）"换成"（最新）"；若它就是当前则合写"（当前·最新）"
                if "（当前）" in label:
                    label = label.replace("（当前）", "（当前·最新）")
                else:
                    label = label.replace("（升级）", "（最新）")
            self.combo.addItem(label)
        # 预选用户在主窗口下拉里选的版本（若有）；否则默认最新
        sel_idx = 0
        if preselected:
            target_n = _normalize_tag(preselected)
            for i, ver in enumerate(versions):
                if _normalize_tag(ver) == target_n:
                    sel_idx = i
                    break
        self.combo.setCurrentIndex(sel_idx)
        row.addWidget(self.combo, stretch=1)
        v.addLayout(row)

        # 真实进度条
        self.bar = QProgressBar()
        self.bar.setFixedHeight(16)
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(True)
        v.addWidget(self.bar)

        self.status = CaptionLabel(
            "点击「开始更新」直接下载并更新到原启动器源程序目录 working/：\n"
            "覆盖代码文件，保留缓存 / 日志 / 配置 / 数据库等运行数据；不备份、不占额外空间。"
        )
        self.status.setWordWrap(True)
        v.addWidget(self.status)

        # 按钮行：第一行 = 下载/关闭；第二行 = 下载完成后的两种应用方式
        btn_row1 = QHBoxLayout()
        self.start_btn = PushButton("开始更新")
        self.start_btn.setFixedHeight(38)
        self.start_btn.clicked.connect(self.start_update)
        btn_row1.addWidget(self.start_btn)

        self.close_btn = PushButton("关闭")
        self.close_btn.setFixedHeight(38)
        self.close_btn.clicked.connect(self.reject)
        btn_row1.addWidget(self.close_btn)
        v.addLayout(btn_row1)

        btn_row2 = QHBoxLayout()
        self.apply_btn = PushButton("打开原版管理窗口")
        self.apply_btn.setFixedHeight(38)
        self.apply_btn.setEnabled(False)
        self.apply_btn.setToolTip(
            "交回原启动器（仅在下载/应用失败时使用，正常情况下已自动更新到 working/）。"
        )
        self.apply_btn.clicked.connect(self.open_manager)
        btn_row2.addWidget(self.apply_btn)
        v.addLayout(btn_row2)

    def start_update(self):
        target = _normalize_tag(self.versions[self.combo.currentIndex()])
        working = self.app.get("working", "")
        # 单次确认（防误点；点开始即自动下载 + 终止进程 + 覆盖 working/ 代码 + 保留运行数据）
        resp = QMessageBox.question(
            self,
            "确认更新到原启动器",
            f"将下载 {target} 并直接更新到原启动器源程序目录：\n{working}\n\n"
            "· 覆盖代码文件，保留缓存 / 日志 / 配置 / 数据库等运行数据\n"
            "· 应用若正在运行会先被终止\n"
            "· 直接覆盖、不产生备份（不占额外空间）\n\n"
            "确认继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return
        self.start_btn.setEnabled(False)
        self.combo.setEnabled(False)
        self.status.setText(f"正在下载 {target}…")
        self.bar.setValue(0)
        self._worker = MirrorUpdater(self.app["key"], self.git_url, target, parent=self)
        self._worker.progress.connect(self.on_progress)
        self._worker.done.connect(self.on_done)
        self._worker.failed.connect(self.on_failed)
        self._worker.start()

    def on_progress(self, pct, text):
        if pct >= 0:
            self.bar.setValue(pct)
            self.status.setText(
                (text[:80] if text else "") or f"下载中… {pct}%"
            )
        else:
            self.status.setText(text or "下载中…")

    def on_done(self, local_dir):
        target = _normalize_tag(self.versions[self.combo.currentIndex()])
        self.bar.setValue(100)
        self.status.setText(
            f"下载完成，正在更新到原启动器 working/（{target}）…"
        )
        # 下载完成自动应用：杀进程 → 同步代码 → 写 app.json（用户无需再点按钮）
        self._apply_worker = ApplyWorker(self.app, target, local_dir, parent=self)
        self._apply_worker.progress.connect(self.status.setText)
        self._apply_worker.done.connect(self.on_apply_done)
        self._apply_worker.start()

    def on_failed(self, msg):
        self.bar.setValue(0)
        self.status.setText(
            f"下载失败：{msg}\n\n可改点「打开原版管理窗口」由原启动器直接更新。"
        )
        self.start_btn.setEnabled(True)
        self.combo.setEnabled(True)

    # 注：原「应用到 working 目录」按钮 + apply_direct 方法已删除，
    # 下载完成后由 on_done 自动调用 ApplyWorker 完成 kill + 同步 + 写 current_version。

    def on_apply_done(self, ok, msg):
        if ok:
            self.bar.setValue(100)
            self.status.setText(
                f"{msg}\n\n运行数据已保留。可关闭本窗口，"
                "再从主窗口点「启动应用」运行新版本。"
            )
            self.apply_btn.setEnabled(True)  # 已自动应用，可选去原版窗口看一眼
        else:
            self.status.setText(
                f"应用失败：{msg}\n\n可改点「打开原版管理窗口」由原启动器处理。"
            )
            self.apply_btn.setEnabled(True)
            self.start_btn.setEnabled(True)
            self.combo.setEnabled(True)

    def open_manager(self):
        run_exe(self, self.app["exe"], [], need_admin=True)
        self.accept()


class Launcher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OK 游戏助手")
        self.setMinimumSize(1020, 640)
        self.resize(1100, 700)
        # 窗口图标用「OK 游戏助手」通用图标，而不是某个具体游戏图标
        self.setWindowIcon(QIcon(os.path.join(ASSETS_DIR, "ok-script-app.png")))

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        title = StrongBodyLabel("OK 游戏助手")
        title.setFixedHeight(56)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "background-color:#2b2b32; color:#ffffff; font-size:20px; font-weight:700;"
        )
        root.addWidget(title)

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(36, 20, 36, 20)
        cl.setSpacing(16)

        hint = CaptionLabel(
            "游戏库：点「▶ 启动应用」直接打开助手主窗口；有新版时点「更新到 vX.Y.Z」"
            "可在本窗口内下载（显示真实进度，仅写入本启动器目录）。\n"
            "正式切换版本 / 系统设置仍请点「原版管理窗口」，由它来完成。"
        )
        hint.setAlignment(Qt.AlignCenter)
        cl.addWidget(hint)

        # 单列竖排：QGridLayout 同行的卡片会强制等高，会把左侧想撑开的 changelog 压住；
        # 改成单列后每张卡片独占一行，宽度由卡内 changelog 自由决定，整体窗口滚动即可。
        card_layout = QVBoxLayout()
        card_layout.setSpacing(20)
        card_layout.setContentsMargins(0, 0, 0, 0)
        for app in APPS:
            card_layout.addWidget(AppCard(app))

        card_container = QWidget()
        card_container.setLayout(card_layout)
        card_container.setMaximumWidth(760)

        card_wrapper = QWidget()
        card_wrapper_layout = QHBoxLayout(card_wrapper)
        card_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        card_wrapper_layout.addStretch(1)
        card_wrapper_layout.addWidget(card_container)
        card_wrapper_layout.addStretch(1)
        cl.addWidget(card_wrapper)
        cl.addStretch(1)

        # 内容区域整体限制最大宽度并居中，避免顶栏提示和卡片在超宽窗口下被拉得太散
        content.setMaximumWidth(1040)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 用 wrapper 让 content 在 scroll area 内水平居中
        wrapper = QWidget()
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.addStretch(1)
        wrapper_layout.addWidget(content)
        wrapper_layout.addStretch(1)
        scroll.setWidget(wrapper)
        root.addWidget(scroll)


def _is_admin():
    """检测当前进程是否以管理员身份运行。"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _relaunch_as_admin():
    """以管理员身份重启本启动器自身（弹 UAC 一次），原进程退出。"""
    exe = sys.executable  # 当前 pythonw.exe
    script = os.path.abspath(__file__)
    cwd = os.path.dirname(script)
    return runas(exe, [script], cwd)


def main():
    # 聚合启动器需要管理员权限才能 taskkill 杀掉 ok-nte 等原启动器进程
    # （实测普通权限下 taskkill / Stop-Process 均被“拒绝访问”）。
    # 非管理员时以 runas 重启自身，仅弹一次 UAC。
    if not _is_admin():
        try:
            _relaunch_as_admin()
        except Exception:
            pass
        sys.exit(0)

    def show_error(etype, value, tb):
        msg = "".join(traceback.format_exception(etype, value, tb))
        try:
            QMessageBox.critical(None, "启动器出错", msg)
        except Exception:
            pass
        sys.__excepthook__(etype, value, tb)

    sys.excepthook = show_error

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    setTheme(Theme.AUTO)
    win = Launcher()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
