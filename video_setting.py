# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk
from enum import StrEnum
from video_config import ConfigManager
from functools import cmp_to_key


class VideoSetting(StrEnum):
    VideoPath = "video_path"
    VideoOut = "video_out"
    Model = "model"
    Scale = "scale"
    Format = "format"
    Level = "level"
    TileSize = "tile_size"
    ThreadCount = "thread_count"
    BitRate = "bit_rate"
    MaxRate = "max_rate"
    CutHeadSec = "cut_head_sec"
    CutTailSec = "cut_tail_sec"
    FpsForce = "fps_force"
    RunStep = "run_step"


class VideoEnhancerSetting:
    def __init__(self, db_path):
        self.db = ConfigManager(db_path)
        self.vars = {}
        self.tasks = self.db.list_all_task()
        self.sort_tasks()

    def gen_var(self, name, default=""):
        var = self.vars.get(name)
        if var is None:
            var = self.new_var(self.db.get(name, default))
            self.vars[name] = var
        return var

    def new_var(self, default=""):
        cls = tk.StringVar
        if isinstance(default, (int, float)):
            cls = tk.DoubleVar
        return cls(value=default)

    def get(self, name, default=""):
        return self.gen_var(name, default).get()

    def save(self):
        for name, var in self.vars.items():
            self.db.set(name, var.get())

    def showUI(self, root):
        self.create_widgets(root)
        self.dialog.deiconify()

    def hideUI(self):
        self.dialog.withdraw()

    def create_widgets(self, root):
        # 创建顶级窗口 (Toplevel)
        self.dialog = tk.Toplevel(root)
        self.dialog.title("设置")
        self.dialog.resizable(True, True)

        # 2. 设置子窗口大小
        sub_w, sub_h = 800, 400
        self.dialog.minsize(sub_w, sub_h)  # 设置最小尺寸

        # 3. 获取主窗口位置和大小
        root.update_idletasks()  # 确保主窗口位置已更新
        main_x = root.winfo_x()
        main_y = root.winfo_y()
        main_w = root.winfo_width()
        main_h = root.winfo_height()

        # 4. 计算居中位置
        x = main_x + (main_w - sub_w) // 2
        y = main_y + (main_h - sub_h) // 2

        # 5. 设置子窗口几何属性
        self.dialog.geometry(f"{sub_w}x{sub_h}+{x}+{y}")

        # 设置为模态窗口 (使主窗口不可交互)
        self.dialog.transient(root)
        self.dialog.grab_set()

        # 参数设置框
        self.params_frame = tk.LabelFrame(
            self.dialog,
            text="增强参数",
        )
        self.params_frame.pack(fill=tk.X, padx=20, pady=10)

        # 模型选择
        model_frame = tk.Frame(self.params_frame)
        model_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(model_frame, text="增强模型:").pack(side=tk.LEFT)

        self.model_var = self.gen_var("model", "realesr-animevideov3")
        self.model_combo = ttk.Combobox(
            model_frame,
            textvariable=self.model_var,
            values=[
                "realesr-animevideov3",
                "realesrgan-x4plus",
                "realesrgan-x4plus-anime",
            ],
            state="readonly",
            width=25,
        )
        self.model_combo.pack(side=tk.RIGHT)

        # 缩放因子
        scale_frame = tk.Frame(self.params_frame)
        scale_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(scale_frame, text="缩放因子:").pack(side=tk.LEFT)

        self.scale_var = self.gen_var("scale", "4")
        self.scale_combo = ttk.Combobox(
            scale_frame,
            textvariable=self.scale_var,
            values=["2", "3", "4"],
            state="readonly",
            width=25,
        )
        self.scale_combo.pack(side=tk.RIGHT)

        # 模型用途说明
        self.model_description_label = tk.Label(
            model_frame,
            text="通用动漫视频增强模型",
            font=("Arial", 8),
            fg="gray",
            wraplength=700,
            justify="left",
        )
        self.model_description_label.pack(anchor=tk.W, side=tk.RIGHT)

        # thread count for load/proc/save
        thread_count_frame = tk.Frame(self.params_frame)
        thread_count_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(thread_count_frame, text="thread count for load/proc/save:").pack(
            side=tk.LEFT
        )

        cores = ["2", "4", "6", "8", "10", "12", "14", "16"]
        tcs = []
        for _, load in enumerate(cores):
            for _, proc in enumerate(cores):
                for save in enumerate(cores):
                    tcs.append(f"{load}:{proc}:{save}")

        self.thread_count_var = self.gen_var("thread_count", "6:12:16")
        self.thread_count_combo = ttk.Combobox(
            thread_count_frame,
            textvariable=self.thread_count_var,
            #    values=["default", "2:2:2", "4:4:4", "4:8:10", "6:12:14"],
            values=tcs,
            state="readonly",
            width=25,
        )
        self.thread_count_combo.pack(side=tk.RIGHT)

        # 输出格式
        format_frame = tk.Frame(self.params_frame)
        format_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(format_frame, text="输出格式:").pack(side=tk.LEFT)

        self.format_var = self.gen_var("format", "png")
        self.format_combo = ttk.Combobox(
            format_frame,
            textvariable=self.format_var,
            values=["jpg", "png"],
            state="readonly",
            width=25,
        )
        self.format_combo.pack(side=tk.RIGHT)

        # tile-size
        tile_size_frame = tk.Frame(self.params_frame)
        tile_size_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(tile_size_frame, text="tile-size:").pack(side=tk.LEFT)

        self.tile_size_var = self.gen_var("tile_size", "512")
        self.tile_size_combo = ttk.Combobox(
            tile_size_frame,
            textvariable=self.tile_size_var,
            values=[
                "default",
                "32",
                "64",
                "96",
                "128",
                "160",
                "192",
                "256",
                "288",
                "320",
                "352",
                "384",
                "416",
                "448",
                "480",
                "512",
            ],
            state="readonly",
            width=25,
        )
        self.tile_size_combo.pack(side=tk.RIGHT)

        # b:v
        bit_rate_frame = tk.Frame(self.params_frame)
        bit_rate_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(bit_rate_frame, text="b:v").pack(side=tk.LEFT)

        self.bit_rate_var = self.gen_var("bit_rate", "45M")
        self.bit_rate_combo = ttk.Combobox(
            bit_rate_frame,
            textvariable=self.bit_rate_var,
            values=[
                "10M",
                "15M",
                "20M",
                "25M",
                "30M",
                "35M",
                "40M",
                "45M",
                "50M",
                "55M",
                "60M",
                "65M",
                "70M",
                "75M",
                "80M",
            ],
            state="readonly",
            width=25,
        )
        self.bit_rate_combo.pack(side=tk.RIGHT)

        # max rate
        max_rate_frame = tk.Frame(self.params_frame)
        max_rate_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(max_rate_frame, text="max rate").pack(side=tk.LEFT)

        self.max_rate_var = self.gen_var("max_rate", "55M")
        self.max_rate_combo = ttk.Combobox(
            max_rate_frame,
            textvariable=self.max_rate_var,
            values=[
                "10M",
                "15M",
                "20M",
                "25M",
                "30M",
                "35M",
                "40M",
                "45M",
                "50M",
                "55M",
                "60M",
                "65M",
                "70M",
                "75M",
                "80M",
            ],
            state="readonly",
            width=25,
        )
        self.max_rate_combo.pack(side=tk.RIGHT)

        # 强制fps
        fps_force_frame = tk.Frame(self.params_frame)
        fps_force_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(fps_force_frame, text="fps force:").pack(side=tk.LEFT)

        self.fps_force_var = self.gen_var("fps_force", 0)
        self.fps_force_spin = ttk.Spinbox(
            fps_force_frame,
            textvariable=self.fps_force_var,
            from_=0,
            to=100,
            increment=1,
            width=25,
        )
        self.fps_force_spin.pack(side=tk.RIGHT)

        # 控制按钮
        button_frame = tk.Frame(self.dialog)
        button_frame.pack(pady=20)

        save_button = tk.Button(
            button_frame,
            text="保存",
            command=self.save_close,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=20,
        )
        save_button.pack(side=tk.LEFT, padx=10)

        # 绑定模型选择事件
        self.model_var.trace("w", self.on_model_change)

    def on_model_change(self, *args):
        """当模型选择改变时的处理函数"""
        selected_model = self.model_var.get()

        # 更新模型用途说明
        model_descriptions = {
            "realesr-animevideov3": "通用动漫视频增强模型",
            "realesrgan-x4plus": "通用视频增强模型，适用于各种类型的视频",
            "realesrgan-x4plus-anime": "专门针对动漫图像优化的增强模型",
        }

        description = model_descriptions.get(selected_model, "")
        self.model_description_label.config(text=description)

        if selected_model in ["realesrgan-x4plus", "realesrgan-x4plus-anime"]:
            # 固定缩放因子为4
            self.scale_var.set("4")
            # 禁用缩放因子选择
            self.scale_combo.config(state="disabled")
        else:
            # 启用缩放因子选择
            self.scale_combo.config(state="readonly")

    def save_close(self):
        self.save()
        self.dialog.destroy()

    def set_task(self, task):
        video_path = task[VideoSetting.VideoPath]
        for idx, v in enumerate(self.tasks):
            if v[VideoSetting.VideoPath] == video_path:
                self.tasks[idx] = task
                self.db.set_task(video_path, task)
                return

        pos = 1
        if len(self.tasks) > 0:
            pos = self.tasks[len(self.tasks) - 1]["pos"] + 1
        task["pos"] = pos

        self.tasks.append(task)
        self.db.set_task(video_path, task)

    def gen_task(self, video_path):
        for _, v in enumerate(self.tasks):
            if v[VideoSetting.VideoPath] == video_path:
                return v

    def idx_task(self, video_path):
        for idx, v in enumerate(self.tasks):
            if v[VideoSetting.VideoPath] == video_path:
                return idx, v

    def delete_task(self, video_path):
        for idx, v in enumerate(self.tasks):
            if v[VideoSetting.VideoPath] == video_path:
                del self.tasks[idx]
                self.db.delete_task(video_path)
                return v

    def clear_task(self):
        self.tasks = []
        self.db.clear_task()

    def sort_tasks(self):
        for idx, v in enumerate(self.tasks):
            if v.get("pos") is None:
                v["pos"] = idx
                self.db.set_task(v[VideoSetting.VideoPath], v)

        def cmp(v1, v2):
            if v1["pos"] != v2["pos"]:
                return v1["pos"] > v2["pos"]
            return v1[VideoSetting.VideoPath] > v2[VideoSetting.VideoPath]

        sorted(self.tasks, key=cmp_to_key(cmp))

    def fix_task_pos(self):
        for idx, v in enumerate(self.tasks):
            if v.get("pos") is None:
                v["pos"] = idx
                self.db.set_task(v[VideoSetting.VideoPath], v)
            elif v["pos"] != idx:
                v["pos"] = idx
                self.db.set_task(v[VideoSetting.VideoPath], v)

    def save_tasks(self):
        for _, v in enumerate(self.tasks):
            video_path = v[VideoSetting.VideoPath]
            self.db.set_task(video_path, v)
