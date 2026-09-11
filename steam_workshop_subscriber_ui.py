# -*- coding: utf-8 -*-
"""Steam 创意工坊 Mod 更新工具(图形界面版)

把创意工坊已下载的 Mod 文件夹复制/更新到 RimWorld 的 Mods 目录。
配置保存在脚本同目录的 config.json 中。
"""

import json
import os
import queue
import shutil
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# 打包成 exe 后 __file__ 指向临时解压目录,配置要跟 exe 放在一起
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

DEFAULT_CONFIG = {
    "source_dir": r"D:\Steam\steamapps\workshop\content\294100",
    "target_dir": r"D:\Steam\steamapps\common\RimWorld\Mods",
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except OSError as e:
        messagebox.showwarning("保存配置失败", f"无法写入配置文件:\n{e}")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Steam 创意工坊 Mod 更新工具")
        self.geometry("760x640")
        self.minsize(640, 520)

        self.cfg = load_config()
        self.log_queue = queue.Queue()
        self.worker = None

        self._build_ui()
        self.after(100, self._poll_log_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.scan_source()

    # ---------- UI 构建 ----------

    def _build_ui(self):
        # 目录设置
        dir_frame = ttk.LabelFrame(self, text="目录设置")
        dir_frame.pack(fill="x", padx=10, pady=(10, 5))

        ttk.Label(dir_frame, text="工坊目录:").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        self.source_var = tk.StringVar(value=self.cfg["source_dir"])
        ttk.Entry(dir_frame, textvariable=self.source_var).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(dir_frame, text="浏览...", command=lambda: self._browse(self.source_var)).grid(row=0, column=2, padx=5)

        ttk.Label(dir_frame, text="Mods 目录:").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        self.target_var = tk.StringVar(value=self.cfg["target_dir"])
        ttk.Entry(dir_frame, textvariable=self.target_var).grid(row=1, column=1, sticky="ew", padx=5)
        ttk.Button(dir_frame, text="浏览...", command=lambda: self._browse(self.target_var)).grid(row=1, column=2, padx=5)

        dir_frame.columnconfigure(1, weight=1)

        # 手动输入创意工坊 ID
        input_frame = ttk.LabelFrame(self, text="手动输入创意工坊 ID(支持空格 / 逗号 / 换行分隔多个)")
        input_frame.pack(fill="x", padx=10, pady=5)

        self.id_entry = ttk.Entry(input_frame)
        self.id_entry.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        self.id_entry.bind("<Return>", lambda e: self.add_manual_ids())
        ttk.Button(input_frame, text="添加", command=self.add_manual_ids).pack(side="left", padx=(0, 5))

        # Mod 列表区
        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # 左侧:已下载
        left_frame = ttk.LabelFrame(list_frame, text="工坊目录中已下载的 Mod")
        left_frame.grid(row=0, column=0, sticky="nsew")

        self.scanned_list = tk.Listbox(left_frame, selectmode="extended")
        self.scanned_list.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)
        scan_scroll = ttk.Scrollbar(left_frame, command=self.scanned_list.yview)
        scan_scroll.pack(side="left", fill="y", pady=5)
        self.scanned_list.config(yscrollcommand=scan_scroll.set)

        scan_btns = ttk.Frame(left_frame)
        scan_btns.pack(side="left", fill="y", padx=5)
        ttk.Button(scan_btns, text="扫描目录", command=self.scan_source).pack(fill="x", pady=2)
        ttk.Button(scan_btns, text="全选", command=lambda: self.scanned_list.select_set(0, "end")).pack(fill="x", pady=2)
        ttk.Button(scan_btns, text="添加 →", command=self.add_selected).pack(fill="x", pady=2)

        # 右侧:待更新列表
        mid_frame = ttk.LabelFrame(list_frame, text="待更新列表")
        mid_frame.grid(row=0, column=1, sticky="nsew", padx=8)

        self.pending_list = tk.Listbox(mid_frame, selectmode="extended")
        self.pending_list.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)
        pend_scroll = ttk.Scrollbar(mid_frame, command=self.pending_list.yview)
        pend_scroll.pack(side="left", fill="y", pady=5)
        self.pending_list.config(yscrollcommand=pend_scroll.set)

        pend_btns = ttk.Frame(mid_frame)
        pend_btns.pack(side="left", fill="y", padx=5)
        ttk.Button(pend_btns, text="移除选中", command=self.remove_selected).pack(fill="x", pady=2)
        ttk.Button(pend_btns, text="清空", command=lambda: self.pending_list.delete(0, "end")).pack(fill="x", pady=2)

        list_frame.columnconfigure(0, weight=1)
        list_frame.columnconfigure(1, weight=1)
        list_frame.rowconfigure(0, weight=1)

        # 操作区
        action_frame = ttk.Frame(self)
        action_frame.pack(fill="x", padx=10, pady=5)
        self.start_btn = ttk.Button(action_frame, text="开始更新", command=self.start_update)
        self.start_btn.pack(side="left")
        self.progress = ttk.Progressbar(action_frame, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=10)

        # 日志
        log_frame = ttk.LabelFrame(self, text="日志")
        log_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        self.log_text = tk.Text(log_frame, height=10, state="disabled", wrap="word")
        self.log_text.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)
        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        log_scroll.pack(side="left", fill="y", pady=5)
        self.log_text.config(yscrollcommand=log_scroll.set)

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(12, 0, 0, 6)).pack(fill="x")

    def _browse(self, var):
        path = filedialog.askdirectory(initialdir=var.get() if os.path.isdir(var.get()) else "/")
        if path:
            var.set(path.replace("/", "\\"))

    # ---------- 列表操作 ----------

    def scan_source(self):
        self.scanned_list.delete(0, "end")
        src = self.source_var.get().strip()
        if not os.path.isdir(src):
            self.set_status("工坊目录不存在,请检查路径")
            return
        folders = sorted(
            (f for f in os.listdir(src) if os.path.isdir(os.path.join(src, f))),
            key=lambda s: (len(s), s),
        )
        if folders:
            self.scanned_list.insert("end", *folders)
        self.set_status(f"扫描完成:发现 {len(folders)} 个已下载的 Mod")

    def add_manual_ids(self):
        raw = self.id_entry.get()
        ids = [part.strip() for part in raw.replace("，", ",").replace(" ", ",").replace("\t", ",").split(",")]
        existing = list(self.pending_list.get(0, "end")) if self.pending_list.size() else []
        added, skipped = 0, 0
        for mod_id in ids:
            if not mod_id or not mod_id.isdigit():
                if mod_id:
                    skipped += 1
                continue
            if mod_id in existing:
                skipped += 1
                continue
            self.pending_list.insert("end", mod_id)
            existing.append(mod_id)
            added += 1
        self.id_entry.delete(0, "end")
        msg = f"手动添加 {added} 个 ID"
        if skipped:
            msg += f",跳过 {skipped} 个(无效或重复)"
        self.set_status(msg)

    def add_selected(self):
        existing = list(self.pending_list.get(0, "end")) if self.pending_list.size() else []
        for index in self.scanned_list.curselection():
            mod_id = self.scanned_list.get(index)
            if mod_id not in existing:
                self.pending_list.insert("end", mod_id)
                existing.append(mod_id)
        self.set_status(f"待更新列表共 {self.pending_list.size()} 项")

    def remove_selected(self):
        for index in reversed(self.pending_list.curselection()):
            self.pending_list.delete(index)
        self.set_status(f"待更新列表共 {self.pending_list.size()} 项")

    # ---------- 更新逻辑 ----------

    def start_update(self):
        if self.worker and self.worker.is_alive():
            return

        src = self.source_var.get().strip()
        dst = self.target_var.get().strip()
        mod_list = list(self.pending_list.get(0, "end"))

        if not os.path.isdir(src):
            messagebox.showerror("错误", f"工坊目录不存在:\n{src}")
            return
        if not mod_list:
            messagebox.showinfo("提示", "待更新列表为空,请先添加要更新的 Mod。")
            return
        if not messagebox.askyesno(
            "确认更新",
            f"将更新 {len(mod_list)} 个 Mod:\n{src} → {dst}\n\n已存在的旧版本会被先删除再复制,是否继续?",
        ):
            return

        self.cfg["source_dir"], self.cfg["target_dir"] = src, dst
        save_config(self.cfg)

        self.start_btn.config(state="disabled")
        self.progress.config(value=0, maximum=len(mod_list))
        self.log(f"=== 准备处理 {len(mod_list)} 个指定 Mod ===")
        self.worker = threading.Thread(target=self._update_worker, args=(src, dst, mod_list), daemon=True)
        self.worker.start()

    def _update_worker(self, src, dst, mod_list):
        success, fail = 0, 0
        for i, folder in enumerate(mod_list, 1):
            src_path = os.path.join(src, folder)
            dst_path = os.path.join(dst, folder)
            try:
                if not os.path.exists(src_path):
                    self.log(f"[跳过] 源文件夹中未找到: {folder}")
                    fail += 1
                    continue

                os.makedirs(dst, exist_ok=True)
                if os.path.exists(dst_path):
                    self.log(f"[清理] 正在删除旧版本: {folder} ...")
                    shutil.rmtree(dst_path)

                self.log(f"[复制] 正在安装/更新: {folder} ...")
                shutil.copytree(src_path, dst_path)
                self.log(f"[成功] {folder} 处理完成。")
                success += 1
            except Exception as e:
                self.log(f"[错误] 处理 {folder} 时失败: {e}")
                fail += 1
            finally:
                self.log_queue.put(("progress", i))

        self.log_queue.put(("done", (success, fail)))

    # ---------- 日志 / 状态 ----------

    def log(self, message):
        self.log_queue.put(("log", message))

    def _poll_log_queue(self):
        try:
            while True:
                kind, payload = self.log_queue.get_nowait()
                if kind == "log":
                    self.log_text.config(state="normal")
                    self.log_text.insert("end", payload + "\n")
                    self.log_text.see("end")
                    self.log_text.config(state="disabled")
                elif kind == "progress":
                    self.progress.step(1)
                elif kind == "done":
                    success, fail = payload
                    self.log("=" * 20 + " 任务结束 " + "=" * 20)
                    self.log(f"成功: {success} 个 / 失败或跳过: {fail} 个")
                    self.start_btn.config(state="normal")
                    self.set_status(f"任务结束:成功 {success} 个,失败/跳过 {fail} 个")
                    messagebox.showinfo("完成", f"更新完成!\n\n成功: {success} 个\n失败/跳过: {fail} 个")
        except queue.Empty:
            pass
        self.after(100, self._poll_log_queue)

    def set_status(self, text):
        self.status_var.set(text)

    def _on_close(self):
        self.cfg["source_dir"] = self.source_var.get().strip()
        self.cfg["target_dir"] = self.target_var.get().strip()
        save_config(self.cfg)
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
