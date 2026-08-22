#!/usr/bin/env python3
"""
Steam Workshop 批量订阅工具

从本地 Mods 文件夹中提取 Steam 创意工坊 ID，支持三种订阅方式：
  1. [全自动] 通过 Steam Web API 直接订阅（需要 API Key）
  2. [半自动] 生成 HTML 页面，通过 steam:// 协议逐个打开
  3. [SteamCMD] 生成批量下载脚本

====== PyCharm 运行 ======
  方式一：直接运行，脚本会交互式询问参数
  方式二：配置 Run Configuration，在 Parameters 中填入参数
  方式三：修改下方 CONFIG 区域，然后直接 Run

  获取 Steam Web API Key: https://steamcommunity.com/dev/apikey
  （需要 Steam 账号消费满 $5 USD）

用法:
    python steam_workshop_subscriber.py
    python steam_workshop_subscriber.py "D:\Steam\steamapps\common\RimWorld\Mods"
    python steam_workshop_subscriber.py "D:\Steam\steamapps\common\RimWorld\Mods" --appid 294100 --auto-subscribe
"""

# ============================================================
# PyCharm 快捷配置区 —— 直接在这里修改参数后 Run 即可
# ============================================================
CONFIG = {
    # 模组文件夹路径（None = 运行时交互询问）
    "directory": None,
    # Steam 游戏 AppID（None = 自动检测或使用默认值 294100）
    "appid": None,
    # Steam Web API Key，用于全自动订阅（None = 从环境变量 STEAM_API_KEY 读取）
    "api_key": None,
    # 全自动模式：直接通过 Web API 订阅（需要 api_key）
    "auto_subscribe": False,
    # 生成 SteamCMD 下载脚本
    "steamcmd": False,
    # 仅列出 ID，不生成任何文件
    "list_only": False,
    # 输出路径（None = 在扫描目录下生成）
    "output": None,
}
# ============================================================

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

# ── 常见游戏的 Steam AppID ──────────────────────────────────
KNOWN_GAMES: dict[str, str] = {
    "294100": "RimWorld",
    "108600": "Project Zomboid",
    "281990": "Stellaris",
    "236850": "Europa Universalis IV",
    "394360": "Hearts of Iron IV",
    "255710": "Cities: Skylines",
    "489830": "The Elder Scrolls V: Skyrim Special Edition",
    "440900": "Conan Exiles",
    "322330": "Don't Starve Together",
    "252950": "Rocket League (legacy)",
    "346110": "ARK: Survival Evolved",
    "252490": "Rust",
    "4000": "Garry's Mod",
    "550": "Left 4 Dead 2",
    "730": "Counter-Strike 2",
    "570": "Dota 2",
    "440": "Team Fortress 2",
    "228980": "Steamworks Common Redistributables",
}

STEAM_API_SUBSCRIBE_URL = "https://api.steampowered.com/IPublishedFileService/Subscribe/v1/"
STEAM_API_KEY_URL = "https://steamcommunity.com/dev/apikey"


# ╔══════════════════════════════════════════════════════════════╗
# ║                    Workshop ID 提取                         ║
# ╚══════════════════════════════════════════════════════════════╝

def extract_workshop_id_from_name(folder_name: str) -> str | None:
    """从纯数字文件夹名提取 Workshop ID。"""
    if folder_name.isdigit() and len(folder_name) >= 7:
        return folder_name
    return None


def extract_workshop_id_from_about_xml(mod_path: Path) -> str | None:
    """从 About/About.xml 中提取 Workshop ID（URL 或字段）。"""
    candidates = [
        mod_path / "About" / "About.xml",
        mod_path / "About.xml",
    ]
    for xml_path in candidates:
        if not xml_path.exists():
            continue
        try:
            text = xml_path.read_text(encoding="utf-8", errors="ignore")

            # 1) 从 steamcommunity.com URL 中提取
            m = re.search(r"steamcommunity\.com/sharedfiles/filedetails/\?id=(\d{7,})", text)
            if m:
                return m.group(1)

            # 2) 尝试解析 XML 找 workshop/publishedfileid
            try:
                root = ET.fromstring(text)
                for elem in root.iter():
                    tag = elem.tag.lower() if elem.tag else ""
                    if any(kw in tag for kw in ("workshop", "steam", "publishedfileid")):
                        if elem.text and elem.text.strip().isdigit():
                            wid = elem.text.strip()
                            if len(wid) >= 7:
                                return wid
                    for av in elem.attrib.values():
                        if av.isdigit() and len(av) >= 7:
                            return av
            except ET.ParseError:
                pass
        except Exception:
            continue
    return None


def extract_workshop_id_from_path(path: Path) -> str | None:
    """从 workshop/content/<appid>/<id> 路径结构中提取 ID。"""
    parts = path.parts
    for i, part in enumerate(parts):
        if part.lower() == "workshop" and i + 2 < len(parts):
            if parts[i + 1].lower() == "content":
                if parts[i + 2].isdigit():
                    if i + 3 < len(parts) and parts[i + 3].isdigit():
                        return parts[i + 3]
    return None


def scan_mods_directory(directory: Path) -> dict[str, dict]:
    """扫描目录，返回 {workshop_id: info_dict}。"""
    results: dict[str, dict] = {}
    if not directory.exists():
        print(f"[错误] 目录不存在: {directory}")
        sys.exit(1)

    for item in sorted(directory.iterdir()):
        if not item.is_dir():
            continue
        name = item.name
        info = {"folder_name": name, "path": str(item), "source": ""}

        wid = (
            extract_workshop_id_from_name(name)
            or extract_workshop_id_from_path(item)
            or extract_workshop_id_from_about_xml(item)
        )
        if wid:
            # 确定来源
            if name.isdigit() and name == wid:
                info["source"] = "文件夹名"
            elif "workshop" in str(item).lower():
                info["source"] = "路径结构"
            else:
                info["source"] = "About.xml"
            info["workshop_id"] = wid
            results[wid] = info

    return results


# ╔══════════════════════════════════════════════════════════════╗
# ║              全自动订阅：Steam Web API                      ║
# ╚══════════════════════════════════════════════════════════════╝

def steam_api_subscribe(api_key: str, publishedfileid: str, appid: str, timeout: int = 15) -> dict:
    """
    调用 Steam Web API 订阅单个 Workshop 项目。

    POST https://api.steampowered.com/IPublishedFileService/Subscribe/v1/
    参数通过 query string 传递，body 为空。

    参考: steam_workshop_api Rust crate 的实现
      - list_type=1 表示订阅
      - include_dependencies=1 包含依赖项

    返回: {"success": bool, "publishedfileid": str, "message": str}
    """
    # 参数放在 URL query string，不在 POST body
    params = {
        "key": api_key,
        "publishedfileid": publishedfileid,
        "list_type": "1",
        "include_dependencies": "1",
    }
    query_string = urllib.parse.urlencode(params)
    url = f"{STEAM_API_SUBSCRIBE_URL}?{query_string}"

    # 空 body 的 POST 请求
    req = urllib.request.Request(url, data=b"", method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            status_code = resp.getcode()
    except urllib.error.HTTPError as e:
        return {
            "success": False,
            "publishedfileid": publishedfileid,
            "message": f"HTTP {e.code}: {e.reason}",
        }
    except (urllib.error.URLError, OSError) as e:
        return {
            "success": False,
            "publishedfileid": publishedfileid,
            "message": f"网络错误: {e}",
        }

    # HTTP 2xx 即视为成功（API 返回空 {"response": {}} 表示操作成功）
    if 200 <= status_code < 300:
        return {
            "success": True,
            "publishedfileid": publishedfileid,
            "message": "订阅成功",
        }
    else:
        return {
            "success": False,
            "publishedfileid": publishedfileid,
            "message": f"HTTP {status_code}: {raw[:200]}",
        }


def auto_subscribe_all(mods: dict[str, dict], api_key: str, appid: str) -> tuple[int, int, list[dict]]:
    """
    全自动批量订阅。

    返回: (成功数, 失败数, 详细结果列表)
    """
    total = len(mods)
    success = 0
    failed = 0
    results = []
    ids = list(mods.keys())

    print(f"\n{'=' * 55}")
    print(f"🤖 全自动订阅模式 —— 通过 Steam Web API")
    print(f"   共 {total} 个模组，AppID: {appid}")
    print(f"{'=' * 55}\n")

    for i, wid in enumerate(ids, 1):
        info = mods[wid]
        name = info["folder_name"]
        print(f"[{i:3d}/{total}] {wid}  {name[:50]}", end=" ", flush=True)

        result = steam_api_subscribe(api_key, wid, appid)
        results.append(result)

        if result["success"]:
            success += 1
            print("✅ 已订阅")
        else:
            failed += 1
            print(f"❌ {result['message']}")

        # 频率控制：Steam API 没有严格要求，但礼貌间隔
        if i < total:
            time.sleep(0.6)

    return success, failed, results


# ╔══════════════════════════════════════════════════════════════╗
# ║                  HTML 页面生成（半自动）                     ║
# ╚══════════════════════════════════════════════════════════════╝

def generate_html(mods: dict[str, dict], appid: str, output_path: Path) -> None:
    """生成带 steam:// 链接的 HTML 订阅页面。"""
    game_name = KNOWN_GAMES.get(appid, f"AppID {appid}")
    total = len(mods)

    rows = ""
    for wid, info in mods.items():
        folder = info["folder_name"]
        source = info["source"]
        steam_url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={wid}"
        steam_proto = f"steam://url/CommunityFilePage/{wid}"
        rows += (
            f'<tr><td class="tc"><code>{wid}</code></td>'
            f'<td class="tn" title="{info["path"]}">{folder}</td>'
            f'<td class="ts">{source}</td>'
            f'<td class="ta">'
            f'<a href="{steam_url}" target="_blank" class="bw">🌐 网页</a> '
            f'<a href="{steam_proto}" class="bs">🔗 Steam</a>'
            f'</td></tr>\n'
        )

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Steam Workshop 批量订阅 —— {game_name}</title>
<style>
:root{{--bg:#1b1e2f;--card:#252840;--fg:#d0d3e0;--ac:#5c7cfa;--bd:#363b55}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,"Microsoft YaHei",sans-serif;background:var(--bg);color:var(--fg);padding:24px}}
h1{{font-size:1.6rem;margin-bottom:4px}}
.sub{{color:#888;margin-bottom:20px;font-size:.9rem}}
.bar{{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap}}
.btn{{display:inline-block;padding:8px 18px;border-radius:6px;text-decoration:none;font-size:.9rem;font-weight:600;cursor:pointer;border:none;transition:.15s}}
.ba{{background:var(--ac);color:#fff}}.ba:hover{{filter:brightness(1.15)}}
.bc{{background:#3b4252;color:#e0e0e0}}.bc:hover{{background:#4a5166}}
.bw{{background:#296d3e;color:#fff;font-size:.82rem;padding:5px 12px}}
.bs{{background:#1a4786;color:#fff;font-size:.82rem;padding:5px 12px}}
.bw:hover,.bs:hover{{filter:brightness(1.2)}}
table{{width:100%;border-collapse:collapse;background:var(--card);border-radius:10px;overflow:hidden}}
th{{background:#2d3250;text-align:left;padding:12px 16px;font-size:.85rem;color:#9ca3c0}}
td{{padding:10px 16px;font-size:.88rem;border-top:1px solid var(--bd)}}
tr:hover{{background:#2b3052}}
.tc code{{background:#1e2240;padding:2px 8px;border-radius:4px;font-size:.84rem}}
.tn{{max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.ts{{color:#7c829c;font-size:.8rem}}
.ta{{white-space:nowrap}}
.footer{{margin-top:24px;color:#555;font-size:.8rem;text-align:center}}
#pg{{display:none;color:var(--ac);margin-left:12px;font-size:.9rem}}
</style>
</head>
<body>
<h1>🛠️ Steam Workshop 批量订阅</h1>
<p class="sub">{game_name} · 共 <strong>{total}</strong> 个模组 · AppID: {appid}</p>
<div class="bar">
<button class="btn ba" onclick="go()">🚀 批量在 Steam 中打开</button>
<button class="btn bc" onclick="cpy()">📋 复制全部 Workshop ID</button>
<span id="pg"></span>
</div>
<table><thead><tr><th>Workshop ID</th><th>文件夹</th><th>来源</th><th>操作</th></tr></thead><tbody>
{rows}</tbody></table>
<div class="footer">
<p>点击<strong>「批量在 Steam 中打开」</strong>依次打开订阅页面，在 Steam 客户端中点击"订阅"。</p>
<p>如需<strong>全自动订阅</strong>，请获取 <a href="{STEAM_API_KEY_URL}">Steam Web API Key</a> 后使用 <code>--auto-subscribe</code>。</p>
</div>
<script>
const ids={list(mods.keys())};
const pg=document.getElementById('pg');
function slp(ms){{return new Promise(r=>setTimeout(r,ms))}}
async function go(){{pg.style.display='inline';for(let i=0;i<ids.length;i++){{pg.textContent=`${{i+1}}/${{ids.length}} ...`;window.open(`steam://url/CommunityFilePage/${{ids[i]}}`,'_blank');await slp(1200)}}pg.textContent='✅ 完成！';setTimeout(()=>pg.style.display='none',4000)}}
function cpy(){{navigator.clipboard.writeText(ids.join('\\n')).then(()=>{{const b=document.querySelector('.bc');const o=b.textContent;b.textContent='✅ 已复制！';setTimeout(()=>b.textContent=o,2000)}})}}
</script>
</body></html>'''
    output_path.write_text(html, encoding="utf-8")
    print(f"[HTML]       已生成: {output_path}")


# ╔══════════════════════════════════════════════════════════════╗
# ║               SteamCMD 脚本生成                             ║
# ╚══════════════════════════════════════════════════════════════╝

def generate_steamcmd_script(mods: dict[str, dict], appid: str, output_dir: Path) -> None:
    """生成 SteamCMD 批量下载脚本。"""
    bat = output_dir / "steamcmd_download_mods.bat"
    sh = output_dir / "steamcmd_download_mods.sh"

    bat.write_text(
        "\n".join([
            "@echo off",
            f"REM SteamCMD 批量下载 Workshop 模组 (AppID: {appid})",
            "REM 如未安装 steamcmd，请从 https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip 下载",
            "",
            "set STEAMCMD=steamcmd.exe",
            "REM set STEAMCMD=D:\\steamcmd\\steamcmd.exe",
            "",
        ] + [
            f'%STEAMCMD% +login anonymous +workshop_download_item {appid} {wid} +quit\n'
            f"if %ERRORLEVEL% NEQ 0 echo [失败] {wid} && timeout /t 1 /nobreak >nul"
            for wid in mods
        ] + [
            "",
            "echo 全部下载完成！",
            "pause",
        ]),
        encoding="utf-8",
    )
    print(f"[SteamCMD]   已生成: {bat}")

    sh.write_text(
        "\n".join([
            "#!/bin/bash",
            f"# SteamCMD 批量下载 Workshop 模组 (AppID: {appid})",
            'STEAMCMD="${STEAMCMD:-steamcmd}"',
            "",
        ] + [
            f'$STEAMCMD +login anonymous +workshop_download_item {appid} {wid} +quit || '
            f'echo "[失败] {wid}"\nsleep 1'
            for wid in mods
        ]),
        encoding="utf-8",
    )
    sh.chmod(0o755)
    print(f"[SteamCMD]   已生成: {sh}")

    ids_file = output_dir / "workshop_ids.txt"
    ids_file.write_text("\n".join(mods.keys()), encoding="utf-8")
    print(f"[ID 列表]    已生成: {ids_file}")


# ╔══════════════════════════════════════════════════════════════╗
# ║              交互式 / PyCharm 入口                          ║
# ╚══════════════════════════════════════════════════════════════╝

def _auto_detect_appid(directory: Path) -> str | None:
    """从路径中自动检测 AppID。"""
    parts = directory.parts
    for i, p in enumerate(parts):
        if p.lower() == "content" and i >= 1 and parts[i - 1].lower() == "workshop":
            if i + 1 < len(parts) and parts[i + 1].isdigit():
                return parts[i + 1]
    return None


def _pick_game_interactively() -> str:
    """交互式选择游戏 AppID。"""
    print("\n🎮 常见游戏列表:")
    items = sorted(KNOWN_GAMES.items(), key=lambda x: x[1])
    for idx, (aid, name) in enumerate(items, 1):
        print(f"  {idx:2d}. {name:45s} AppID: {aid}")
    print(f"  {'':2s} 也可以直接输入 AppID 数字\n")

    while True:
        choice = input("请输入序号或 AppID (默认 294100=RimWorld): ").strip()
        if not choice:
            return "294100"
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(items):
                return items[idx - 1][0]
            if idx >= 100:  # 可能是 AppID
                return str(idx)
        print("  ⚠️ 无效输入，请重新输入")


def run_interactive(cfg: dict) -> None:
    """
    PyCharm 友好的交互式运行入口。

    当没有命令行参数时，通过 input() 交互询问。
    在 PyCharm 中直接 Run 即可使用。
    """
    print("=" * 55)
    print("  🛠️  Steam Workshop 批量订阅工具")
    print("=" * 55)

    # ── 目录 ──
    directory_str = cfg.get("directory") or input(
        "\n📁 模组文件夹路径:\n"
        "  (如 D:\\Steam\\steamapps\\common\\RimWorld\\Mods)\n"
        "  (或 D:\\Steam\\steamapps\\workshop\\content\\294100)\n"
        "> "
    ).strip().strip('"')
    if not directory_str:
        print("[错误] 必须指定目录路径"); sys.exit(1)
    directory = Path(directory_str)

    # ── AppID ──
    detected = _auto_detect_appid(directory)
    appid = cfg.get("appid")
    if not appid:
        if detected:
            gname = KNOWN_GAMES.get(detected, "未知")
            use = input(f"\n🎮 检测到 AppID: {detected} ({gname})，使用此 AppID？[Y/n]: ").strip().lower()
            appid = detected if use in ("", "y", "yes") else _pick_game_interactively()
        else:
            appid = _pick_game_interactively()

    # ── API Key ──
    api_key = cfg.get("api_key") or os.environ.get("STEAM_API_KEY", "")
    auto_sub = cfg.get("auto_subscribe", False)

    if not auto_sub and not cfg.get("list_only"):
        print(f"\n{'─' * 45}")
        print("请选择订阅方式:")
        print(f"  1. 🤖 全自动 —— 通过 Steam Web API 直接订阅（需要 API Key）")
        print(f"  2. 🌐 半自动 —— 生成 HTML，浏览器中手动点击")
        print(f"  3. 📦 仅 SteamCMD —— 生成批量下载脚本（无需登录）")
        print(f"  4. 📋 仅列出 ID —— 不生成文件")
        mode = input("请输入 [1-4] (默认 2): ").strip() or "2"
    elif cfg.get("list_only"):
        mode = "4"
    else:
        mode = "1"

    if mode == "1":
        if not api_key:
            print(f"\n🔑 需要 Steam Web API Key 才能使用全自动订阅。")
            print(f"   获取地址: {STEAM_API_KEY_URL}")
            print(f"   (需要 Steam 账号消费满 $5 USD)")
            api_key = input("请输入 API Key (输入后不会保存到脚本): ").strip()
            if not api_key:
                print("[错误] 必须提供 API Key"); sys.exit(1)

    # ── 开始扫描 ──
    print(f"\n🔍 扫描: {directory}")
    print(f"🎮 游戏: {KNOWN_GAMES.get(appid, '未知')} (AppID: {appid})")
    print("-" * 45)

    mods = scan_mods_directory(directory)

    if not mods:
        print("\n⚠️  未找到任何 Workshop 模组！")
        print("   请确认路径正确。纯数字文件夹名会被识别为 Workshop ID，")
        print("   非纯数字的会尝试从 About.xml 中提取。")
        sys.exit(0)

    print(f"\n✅ 识别到 {len(mods)} 个模组:\n")
    for wid, info in mods.items():
        print(f"  [{wid}]  {info['folder_name'][:55]}  ({info['source']})")

    # ── 执行 ──
    output_dir = directory

    if mode == "1":
        ok, fail, results = auto_subscribe_all(mods, api_key, appid)
        print(f"\n{'=' * 55}")
        print(f"✅ 订阅完成: {ok} 成功 / {fail} 失败")
        if fail:
            print("失败项目:")
            for r in results:
                if not r["success"]:
                    print(f"  ❌ {r['publishedfileid']}: {r['message']}")

    elif mode == "2":
        html_path = output_dir / "workshop_subscribe.html"
        generate_html(mods, appid, html_path)
        steamcmd_ask = input("\n同时生成 SteamCMD 下载脚本？[y/N]: ").strip().lower()
        if steamcmd_ask in ("y", "yes"):
            generate_steamcmd_script(mods, appid, output_dir)
        print(f"\n💡 用浏览器打开 {html_path} 即可批量订阅。")

    elif mode == "3":
        generate_steamcmd_script(mods, appid, output_dir)

    elif mode == "4":
        print("\n📋 Workshop ID 列表已在上方显示。")

    print("\n✨ 完成！")


# ╔══════════════════════════════════════════════════════════════╗
# ║                    命令行入口                               ║
# ╚══════════════════════════════════════════════════════════════╝

def main_cli() -> None:
    """命令行解析入口（也支持无参数交互模式）。"""
    parser = argparse.ArgumentParser(
        description="Steam Workshop 批量订阅工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
示例:
  # 交互模式（PyCharm 直接 Run）
  python steam_workshop_subscriber.py

  # 扫描并生成 HTML
  python steam_workshop_subscriber.py "D:\\\\Steam\\\\steamapps\\\\common\\\\RimWorld\\\\Mods"

  # 全自动订阅（需要 API Key）
  python steam_workshop_subscriber.py "D:\\\\Steam\\\\steamapps\\\\common\\\\RimWorld\\\\Mods" --appid 294100 --api-key YOUR_KEY --auto-subscribe

  # 扫描 Workshop 缓存目录
  python steam_workshop_subscriber.py "D:\\\\Steam\\\\steamapps\\\\workshop\\\\content\\\\294100"

获取 API Key: {STEAM_API_KEY_URL}
        """,
    )
    parser.add_argument("directory", nargs="?", default=None, help="模组文件夹路径")
    parser.add_argument("--appid", default=None, help="Steam 游戏 AppID (默认: 自动检测或 294100)")
    parser.add_argument("--api-key", default=None, help="Steam Web API Key (也可设置环境变量 STEAM_API_KEY)")
    parser.add_argument("--auto-subscribe", action="store_true", help="全自动模式：通过 Web API 直接订阅")
    parser.add_argument("--steamcmd", action="store_true", help="生成 SteamCMD 批量下载脚本")
    parser.add_argument("--output", "-o", default=None, help="HTML 输出路径")
    parser.add_argument("--list-only", action="store_true", help="仅列出 Workshop ID")

    args = parser.parse_args()

    # 如果提供了命令行参数，使用命令行模式
    has_cli_args = any([
        args.directory,
        args.auto_subscribe,
        args.steamcmd,
        args.list_only,
        args.api_key,
    ])

    if has_cli_args:
        # ── 命令行模式 ──
        if not args.directory:
            print("[错误] 请指定模组目录路径"); sys.exit(1)
        directory = Path(args.directory)
        detected = _auto_detect_appid(directory)
        appid = args.appid or detected or "294100"
        api_key = args.api_key or os.environ.get("STEAM_API_KEY", "")

        print(f"🔍 扫描目录: {directory}")
        print(f"🎮 游戏 AppID: {appid} ({KNOWN_GAMES.get(appid, '未知游戏')})")
        print("-" * 50)

        mods = scan_mods_directory(directory)
        if not mods:
            print("\n⚠️  未找到任何 Workshop 模组。"); sys.exit(0)

        print(f"\n✅ 找到 {len(mods)} 个模组:\n")
        for wid, info in mods.items():
            print(f"  [{wid}] {info['folder_name'][:55]}  ({info['source']})")

        if args.list_only:
            return

        if args.auto_subscribe:
            if not api_key:
                print(f"\n[错误] 全自动订阅需要 API Key，请用 --api-key 指定")
                print(f"获取地址: {STEAM_API_KEY_URL}")
                sys.exit(1)
            auto_subscribe_all(mods, api_key, appid)
        else:
            html_path = Path(args.output) if args.output else directory / "workshop_subscribe.html"
            generate_html(mods, appid, html_path)
            if args.steamcmd:
                generate_steamcmd_script(mods, appid, directory)
            print(f"\n💡 浏览器打开 {html_path.name}，点击按钮即可批量订阅。")
    else:
        # ── 交互模式（PyCharm 友好）──
        run_interactive({
            "directory": CONFIG.get("directory"),
            "appid": CONFIG.get("appid"),
            "api_key": CONFIG.get("api_key") or os.environ.get("STEAM_API_KEY", ""),
            "auto_subscribe": CONFIG.get("auto_subscribe", False),
            "list_only": CONFIG.get("list_only", False),
        })


if __name__ == "__main__":
    # PyCharm 用户：可以修改顶部 CONFIG 字典后直接 Run
    # 如果 CONFIG 中设置了值，会作为默认值参与交互
    main_cli()
