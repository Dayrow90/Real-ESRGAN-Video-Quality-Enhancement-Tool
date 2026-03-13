# -*- coding: utf-8 -*-
import os
import sys
import re
import time
import math
import datetime
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import threading
import shutil
import psutil
import cv2
import av
import ffmpeg
from moviepy import VideoFileClip
from PIL import Image, ImageTk
from enum import Enum
from video_setting import *
from video_task import *
import video_compress, video_utils


class ProcState(Enum):
    STOP = 0
    CUT = 1
    EXTRACT = 2
    ENHANCE = 3
    MERGE = 4
    FINISH = 5
    NEXT = 6
    COMPRESS = 7


class VideoEnhancerApp:
    def __init__(self, root):
        self.proc_state = ProcState.STOP
        self.scale_fix_lower = None
        self.video_info = None
        self.cut_video_path = None

        self.root = root
        self.root.title("Real-ESRGAN 视频画质增强工具")
        self.root.geometry("800x900")  # 增大窗口尺寸以容纳注释
        self.root.minsize(800, 900)  # 设置最小尺寸
        self.root.resizable(True, True)

        self.setting = VideoEnhancerSetting("video_enhancer.db")

        # 获取项目根目录
        self.project_root = os.path.dirname(os.path.abspath(__file__))

        # 运行日志
        self.log_messages = []

        # 子进程列表
        self.processes = []

        # 创建界面元素
        self.create_widgets()
        self.rfsh_tasks()

        # 绑定 <Escape> 事件到子窗口
        # 当在这个子窗口上按下 Esc 键时，会调用 close_window 函数
        self.root.bind("<Escape>", self.on_esc)

        # 初始化路径
        self.init_paths()

        self.video_path_var.trace("w", self.on_path_video_change)

        # --- 绑定事件 ---
        self.cut_head_label.bind("<Enter>", self.on_enter_cut_head_label)
        self.cut_head_label.bind("<Leave>", self.on_leave_cut_head_label)
        self.cut_tail_label.bind("<Enter>", self.on_enter_cut_tail_label)
        self.cut_tail_label.bind("<Leave>", self.on_leave_cut_tail_label)
        # 确保鼠标离开图片窗口时也隐藏它
        self.tooltip_video_cap.bind("<Leave>", self.on_leave_tooltip_video_cap)
        self.entering_label = None
        self.img_video_cap = None

        self.on_timer_minute()

        if self.video_path_var.get():
            self.on_path_video_change()

        # 可选：将窗口居中显示
        self.root.lift()  # 将窗口置于所有窗口之上
        self.root.focus_set()  # 再次确保焦点设置

    def gen_var(self, name, default=None):
        return self.setting.gen_var(name, default)

    def create_widgets(self):
        menubar = tk.Menu(self.root)
        # menubar.add_command(label="新建任务", command=self.on_menu_task_create)
        # menubar.add_command(label="自动执行", command=self.on_menu_task_next)
        menubar.add_command(label="默认设置", command=self.on_menu_open_setting)
        self.root.config(menu=menubar)

        self.create_task_treeview()
        self.create_task_menu()

        self.model_var = self.gen_var(VideoSetting.Model)
        self.format_var = self.gen_var(VideoSetting.Format)
        self.level_var = self.gen_var(VideoSetting.Level)
        self.tile_size_var = self.gen_var(VideoSetting.TileSize)
        self.bit_rate_var = self.gen_var(VideoSetting.BitRate)
        self.max_rate_var = self.gen_var(VideoSetting.MaxRate)
        self.thread_count_var = self.gen_var(VideoSetting.ThreadCount)
        self.fps_force_var = self.gen_var(VideoSetting.FpsForce)

        # 参数设置框
        self.params_frame = tk.LabelFrame(
            self.root,
            text="参数",
        )
        self.params_frame.pack(fill=tk.X, padx=20, pady=10)

        # 视频文件选择框
        video_frame = tk.Frame(self.params_frame)
        video_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(video_frame, text="视频文件:").pack(side=tk.LEFT)

        self.video_path_var = self.gen_var(VideoSetting.VideoPath)
        tk.Entry(video_frame, textvariable=self.video_path_var, state="readonly").pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )

        self.browse_video_button = tk.Button(
            video_frame, text="浏览", command=self.browse_video
        )
        self.browse_video_button.pack(side=tk.RIGHT, padx=(5, 0))

        # 视频输出选择框
        video_out_frame = tk.Frame(self.params_frame)
        video_out_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(video_out_frame, text="输出目录:").pack(side=tk.LEFT)

        self.video_out_var = self.gen_var(VideoSetting.VideoOut)
        tk.Entry(
            video_out_frame, textvariable=self.video_out_var, state="readonly"
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.browse_video_out_button = tk.Button(
            video_out_frame, text="浏览", command=self.browse_video_out
        )
        self.browse_video_out_button.pack(side=tk.RIGHT, padx=(5, 0))

        # 执行步骤
        step_frame = tk.Frame(self.params_frame)
        step_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(step_frame, text="执行步骤:").pack(side=tk.LEFT)

        self.step_var = self.gen_var(VideoSetting.ProcStep)
        self.step_combo = ttk.Combobox(
            step_frame,
            textvariable=self.step_var,
            values=ProcStep.values(),
            state="readonly",
            width=25,
        )
        self.step_combo.pack(side=tk.RIGHT)

        # 执行步骤说明
        self.step_description_label = tk.Label(
            step_frame,
            text="",
            font=("Arial", 8),
            fg="gray",
            wraplength=700,
            justify="left",
        )
        self.step_description_label.pack(anchor=tk.W, side=tk.RIGHT)

        self.step_var.trace("w", self.on_step_change)
        self.on_step_change()

        # 缩放因子
        scale_frame = tk.Frame(self.params_frame)
        scale_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(scale_frame, text="缩放因子:").pack(side=tk.LEFT)

        self.scale_var = self.gen_var(VideoSetting.Scale)
        self.scale_combo = ttk.Combobox(
            scale_frame,
            textvariable=self.scale_var,
            values=VideoSetting.Scale.values(),
            state="readonly",
            width=25,
        )
        self.scale_combo.pack(side=tk.RIGHT)

        # 裁剪开头N秒
        self.cut_head_sec_var = self.gen_var(VideoSetting.CutHeadSec)
        cut_head_frame = tk.Frame(self.params_frame)
        cut_head_frame.pack(fill=tk.X, padx=10, pady=5)

        self.cut_head_label = tk.Label(cut_head_frame, text="裁剪开头N秒:")
        self.cut_head_label.pack(side=tk.LEFT)
        self.cut_head_combo = ttk.Combobox(
            cut_head_frame,
            textvariable=self.cut_head_sec_var,
            values=VideoSetting.CutHeadSec.values(),
            width=25,
        )
        self.cut_head_combo.pack(side=tk.RIGHT)

        # 裁剪结尾N秒
        cut_tail_frame = tk.Frame(self.params_frame)
        cut_tail_frame.pack(fill=tk.X, padx=10, pady=5)

        self.cut_tail_sec_var = self.gen_var(VideoSetting.CutTailSec)
        self.cut_tail_label = tk.Label(cut_tail_frame, text="裁剪结尾N秒:")
        self.cut_tail_label.pack(side=tk.LEFT)
        self.cut_tail_combo = ttk.Combobox(
            cut_tail_frame,
            textvariable=self.cut_tail_sec_var,
            values=VideoSetting.CutTailSec.values(),
            width=25,
        )
        self.cut_tail_combo.pack(side=tk.RIGHT)

        # --- 工具提示窗口 (Toplevel) ---
        # 不要将它 pack() 或 grid() 到任何地方
        self.tooltip_video_cap = tk.Toplevel(self.root)
        self.tooltip_video_cap.withdraw()  # 初始隐藏
        self.tooltip_video_cap.overrideredirect(True)  # 移除窗口边框

        # 为工具提示窗口添加一个 Label 来显示图片
        self.img_video_cap_label = tk.Label(
            self.tooltip_video_cap, bg="white", bd=1, relief="solid"
        )
        self.img_video_cap_label.pack()

        # 自动下一个任务
        proc_done_frame = tk.Frame(self.params_frame)
        proc_done_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(proc_done_frame, text="执行结束:").pack(side=tk.LEFT)

        self.proc_done_var = self.gen_var(VideoSetting.ProcDone)
        self.proc_done_combo = ttk.Combobox(
            proc_done_frame,
            textvariable=self.proc_done_var,
            values=VideoSetting.ProcDone.values(),
            state="readonly",
            width=25,
        )
        self.proc_done_combo.pack(side=tk.RIGHT)

        # 日志框
        log_frame = tk.LabelFrame(self.root, text="日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=6, state="disabled"
        )  # 减小高度
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 控制按钮
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=20)

        self.start_button = tk.Button(
            button_frame,
            text="执行",
            command=self.start_enhancement,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=20,
        )
        self.start_button.pack(side=tk.LEFT, padx=10)

        tk.Button(
            button_frame,
            text="退出",
            command=self.exit_application,
            bg="#f44336",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=20,
        ).pack(side=tk.LEFT, padx=10)

    def create_task_treeview(self):
        # 任务列表
        task_frame = tk.LabelFrame(self.root, text="任务")
        task_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        columns = ("video_file", "out_dir")  # 添加 'actions' 列
        self.task_treeview = ttk.Treeview(
            task_frame, columns=columns, show="headings", height=1
        )

        # 定义列标题和宽度
        self.task_treeview.heading("video_file", text="视频文件")
        self.task_treeview.column("video_file", width=400, anchor=tk.W)

        self.task_treeview.heading("out_dir", text="输出目录")
        self.task_treeview.column("out_dir", width=100, anchor=tk.W)

        # 添加滚动条
        scrollbar = ttk.Scrollbar(
            task_frame, orient=tk.VERTICAL, command=self.task_treeview.yview
        )
        self.task_treeview.configure(yscrollcommand=scrollbar.set)

        self.task_treeview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 绑定鼠标右键点击事件
        self.task_treeview.bind("<Button-3>", self.show_task_menu)  # Button-3 代表右键
        self.task_treeview.bind("<Double-1>", self.on_menu_task_setting)

    def create_task_menu(self):
        """创建右键菜单"""
        self.task_menu = tk.Menu(self.root, tearoff=0)
        self.task_menu.add_command(label="新建任务", command=self.on_menu_task_create)
        self.task_menu.add_command(label="自动执行", command=self.on_menu_task_next)
        self.task_menu.add_command(label="刷新列表", command=self.rfsh_tasks)
        self.task_menu.add_command(label="清空列表", command=self.on_menu_task_clear)
        self.task_menu.add_separator()  # 添加一条分割线
        self.task_menu.add_command(label="执行", command=self.on_menu_task_start)
        self.task_menu.add_command(label="覆盖到参数", command=self.on_menu_task_show)
        self.task_menu.add_command(label="设置", command=self.on_menu_task_setting)
        self.task_menu.add_command(label="删除", command=self.on_menu_task_delete)
        self.task_menu.add_separator()  # 添加一条分割线
        self.task_menu.add_command(label="上移到顶", command=self.on_menu_task_up_head)
        self.task_menu.add_command(label="上移", command=self.on_menu_task_up)
        self.task_menu.add_command(label="下移", command=self.on_menu_task_down)
        self.task_menu.add_command(
            label="下移到底", command=self.on_menu_task_down_tail
        )

    def show_task_menu(self, event):
        """显示右键菜单"""
        # 获取被右键点击的项目
        item = self.task_treeview.identify_row(event.y)  # identify_row 返回行的ID
        self.task_treeview.identify_column(event.x)  # identify_column 返回列的ID

        # 如果右键点击在行上，则选中该行
        if item:
            # 选中被点击的行
            self.task_treeview.selection_set(item)
            self.task_treeview.focus(item)  # 将焦点设置到该行

        # 在鼠标指针位置显示菜单
        try:
            self.task_menu.tk_popup(event.x_root, event.y_root)
        finally:
            # tk_popup 是一个阻塞式菜单，必须用 tk_popup() 和 grab_release() 来确保菜单能正常关闭
            self.task_menu.grab_release()

    def rfsh_tasks(self):
        for row in self.task_treeview.get_children():
            self.task_treeview.delete(row)

        for task in self.setting.tasks:
            video_out = task.get(VideoSetting.VideoOut) or self.video_out_var.get()
            values = (task[VideoSetting.VideoPath], video_out)
            self.task_treeview.insert("", tk.END, values=values)

    def on_menu_open_setting(self):
        self.setting.showUI(self.root)

    def on_menu_task_create(self):
        task = None
        selection = self.task_treeview.selection()
        if selection:
            item_id = selection[0]
            video_path = self.task_treeview.item(item_id, "values")[0]
            task = self.setting.gen_task(video_path)
        VideoEnhancerTaskCreate(self, task)

    def on_menu_task_next(self):
        self.proc_state = ProcState.NEXT
        self.proc_done_var.set(ProcDone.NEXT)
        self.log("将于1分钟内自动执行下一个任务...")

    def on_menu_task_clear(self):
        self.setting.clear_task()
        self.rfsh_tasks()

    def on_menu_task_start(self):
        if self.is_running():
            return

        selection = self.task_treeview.selection()
        if not selection:
            return

        item_id = selection[0]
        video_path = self.task_treeview.item(item_id, "values")[0]
        task = self.setting.gen_task(video_path)
        if task and self.show_task(task):
            self.start_enhancement()

    def on_menu_task_show(self):
        if self.is_running():
            return

        selection = self.task_treeview.selection()
        if not selection:
            return

        item_id = selection[0]
        video_path = self.task_treeview.item(item_id, "values")[0]
        task = self.setting.gen_task(video_path)
        if task:
            self.show_task(task)

    def on_menu_task_setting(self, *args):
        selection = self.task_treeview.selection()
        if not selection:
            return

        item_id = selection[0]
        video_path = self.task_treeview.item(item_id, "values")[0]
        task = self.setting.gen_task(video_path)
        if not task:
            return

        VideoEnhancerTaskSetting(self, task)
        self.rfsh_tasks()

    def on_menu_task_up_head(self, *args):
        selection = self.task_treeview.selection()
        if not selection:
            return

        item_id = selection[0]
        video_path = self.task_treeview.item(item_id, "values")[0]
        idx, task = self.setting.idx_task(video_path)
        if not task:
            return

        del self.setting.tasks[idx]
        self.setting.tasks = [task] + self.setting.tasks
        self.setting.fix_task_pos()
        self.rfsh_tasks()

    def on_menu_task_up(self):
        selection = self.task_treeview.selection()
        if not selection:
            return

        item_id = selection[0]
        video_path = self.task_treeview.item(item_id, "values")[0]
        idx, task = self.setting.idx_task(video_path)
        if not task:
            return
        elif idx == 0:
            return

        pre = self.setting.tasks[idx - 1]
        self.setting.tasks[idx - 1] = task
        self.setting.tasks[idx] = pre
        self.setting.fix_task_pos()
        self.rfsh_tasks()

    def on_menu_task_down(self):
        selection = self.task_treeview.selection()
        if not selection:
            return

        item_id = selection[0]
        video_path = self.task_treeview.item(item_id, "values")[0]
        idx, task = self.setting.idx_task(video_path)
        if not task:
            return
        elif idx == (len(self.setting.tasks) - 1):
            return

        ne = self.setting.tasks[idx + 1]
        self.setting.tasks[idx + 1] = task
        self.setting.tasks[idx] = ne
        self.setting.fix_task_pos()
        self.rfsh_tasks()

    def on_menu_task_down_tail(self):
        selection = self.task_treeview.selection()
        if not selection:
            return

        item_id = selection[0]
        video_path = self.task_treeview.item(item_id, "values")[0]
        idx, task = self.setting.idx_task(video_path)
        if not task:
            return

        del self.setting.tasks[idx]
        self.setting.tasks.append(task)
        self.setting.fix_task_pos()
        self.rfsh_tasks()

    def on_menu_task_delete(self):
        selection = self.task_treeview.selection()
        if not selection:
            return

        item_id = selection[0]
        video_path = self.task_treeview.item(item_id, "values")[0]
        self.setting.delete_task(video_path)
        self.rfsh_tasks()

    def show_task(self, task=None):
        if task:
            self.log(f"show_task: {task}")
        elif len(self.setting.tasks) > 0:
            task = self.setting.tasks[0]
            self.log(f"show_task first: {task}")
        else:
            self.log("show_task nothing")
            return

        # 显示任务信息
        for key, val in task.items():
            var = self.gen_var(key, val)
            var.set(val)

        return True

    def is_running(self):
        if self.proc_state == ProcState.STOP:
            return False
        elif self.proc_state == ProcState.FINISH:
            return False
        elif self.proc_state == ProcState.NEXT:
            return False
        return True

    def save_configs(self):
        self.setting.save()

    def init_paths(self):
        """初始化必要的路径"""
        self.dir_output = os.path.join(self.project_root, "output")
        self.dir_frames_extract = os.path.join(self.dir_output, "frames_extract")
        self.dir_frames_enhance = os.path.join(self.dir_output, "frames_enhance")
        self.dir_cut = os.path.join(self.dir_output, "cut")
        self.dir_capture = os.path.join(self.dir_output, "capture")
        self.dir_log = os.path.join(self.dir_output, "log")

        self.create_paths()

        # 创建日志文件
        self.log_path = os.path.join(
            self.dir_log, time.strftime("%Y-%m-%d", time.localtime()) + ".log"
        )
        self.log_file = open(self.log_path, "a+", encoding="utf-8")
        if self.log_file:
            # 重定向print
            video_utils.redirect_std_err(self.log)
            video_utils.redirect_std_out(self.log)

    def create_paths(self):
        # 创建必要的目录
        os.makedirs(self.dir_output, exist_ok=True)
        os.makedirs(self.dir_frames_extract, exist_ok=True)
        os.makedirs(self.dir_frames_enhance, exist_ok=True)
        os.makedirs(self.dir_cut, exist_ok=True)
        os.makedirs(self.dir_capture, exist_ok=True)
        os.makedirs(self.dir_log, exist_ok=True)

    def on_timer_minute(self):
        self.log_text.after(60000, self.on_timer_minute)

        if self.proc_state == ProcState.FINISH:
            self.proc_state = ProcState.NEXT  # 等待1-2分钟再自动执行下一个任务
            self.log("将于1分钟后自动执行下一个任务...")
            return
        elif self.proc_state == ProcState.NEXT:
            self.proc_state = ProcState.STOP
            if self.show_task():
                # self.step_var.set(ProcStep.ALL)
                self.start_enhancement()
            else:
                self.log("任务列表为空...")
            return
        elif self.proc_state == ProcState.ENHANCE:
            files = os.listdir(self.dir_frames_enhance)
            count = len(files)
            total_frames = int(self.video_info.get("extract_frames") or 1)
            percent = (count / total_frames) * 100
            self.log(f"frames enhanced: {percent:03.02f}% - {count}/{total_frames}")
            return

    def on_step_change(self, *args):
        """当模型选择改变时的处理函数"""
        step = self.step_var.get()
        self.step_description_label.config(text=ProcStep.desc(step))

    def on_path_video_change(self, *args):
        self.log("----------")
        path = self.video_path_var.get()
        if os.path.isdir(path):
            if self.video_out_var.get() == "":
                self.video_out_var.set(path)
            return
        elif not os.path.isfile(path):
            return

        if self.video_out_var.get() == "":
            self.video_out_var.set(os.path.dirname(path))

        self.video_info = self.get_video_info(path)
        self.log(f"video_path: {path}")
        self.log(f"video_info: {self.video_info}")

        level = self.cal_video_level(self.video_info)
        level = level and str(float(level))
        self.log(f"cal_video_level: {level}")
        if level in VideoSetting.Level.values():
            self.level_var.set(level)

    def on_enter_cut_head_label(self, *args):
        """鼠标进入按钮时的处理函数"""

        path = self.video_path_var.get()
        if not os.path.isfile(path):
            return

        sec = float(self.cut_head_sec_var.get())
        if sec <= 0:
            return

        basename = os.path.basename(path)
        output_image_path = os.path.join(self.dir_capture, f"{basename}_head_{sec}.png")
        self.capture_frame(path, output_image_path, sec)
        if not os.path.isfile(output_image_path):
            return

        # 获取鼠标指针的屏幕坐标
        x = self.root.winfo_pointerx() + 10
        y = self.root.winfo_pointery() + 10
        # 定位并显示工具提示窗口
        self.tooltip_video_cap.geometry(f"+{x}+{y}")
        self.tooltip_video_cap.deiconify()  # 显示窗口
        self.entering_label = self.cut_head_label

    def on_leave_cut_head_label(self, *args):
        """鼠标离开按钮时的处理函数"""
        # 延迟隐藏，以防鼠标快速移动到图片窗口上导致闪烁
        self.tooltip_video_cap.after(50, self._hide_if_not_over)

    def on_enter_cut_tail_label(self, *args):
        """鼠标进入按钮时的处理函数"""

        path = self.video_path_var.get()
        if not os.path.isfile(path):
            return

        sec = float(self.cut_tail_sec_var.get())
        if sec <= 0:
            return

        basename = os.path.basename(path)
        output_image_path = os.path.join(self.dir_capture, f"{basename}_tail_{sec}.png")
        self.capture_frame(path, output_image_path, -sec)
        if not os.path.isfile(output_image_path):
            return

        # 获取鼠标指针的屏幕坐标
        x = self.root.winfo_pointerx() + 10
        y = self.root.winfo_pointery() + 10
        # 定位并显示工具提示窗口
        self.tooltip_video_cap.geometry(f"+{x}+{y}")
        self.tooltip_video_cap.deiconify()  # 显示窗口
        self.entering_label = self.cut_tail_label

    def on_leave_cut_tail_label(self, *args):
        """鼠标离开按钮时的处理函数"""
        # 延迟隐藏，以防鼠标快速移动到图片窗口上导致闪烁
        self.tooltip_video_cap.after(50, self._hide_if_not_over)

    def _hide_if_not_over(self):
        """辅助函数：检查鼠标是否仍在主按钮或图片窗口上，如果不是则隐藏"""

        if not self.entering_label:
            return

        # 获取当前鼠标所在的窗口ID
        under_mouse_id = self.root.winfo_containing(
            self.root.winfo_pointerx(), self.root.winfo_pointery()
        )

        # 获取主按钮和图片窗口的顶层窗口widget
        label_toplevel = self.entering_label.winfo_toplevel()
        tooltip_toplevel = self.tooltip_video_cap

        # 如果鼠标不在按钮或图片窗口上，则隐藏
        if (
            under_mouse_id != self.entering_label
            and under_mouse_id != label_toplevel
            and under_mouse_id != tooltip_toplevel
        ):
            self.tooltip_video_cap.withdraw()
            self.entering_label = None

    def on_leave_tooltip_video_cap(self, *args):
        """鼠标离开工具提示窗口时的处理函数"""
        self.tooltip_video_cap.withdraw()  # 直接隐藏

    def capture_frame(self, video_path, output_image_path, time_in_seconds):
        """
        对一个视频文件, 截取某一秒的视频截图, 并生成图片文件。

        Args:
            video_path (str): 视频文件的路径。
            output_image_path (str): 输出图片文件的路径 (例如 'screenshot.png')。
            time_in_seconds (float): 要截取画面的时间点，以秒为单位。
        """
        try:
            if os.path.isfile(output_image_path):
                if self.img_video_cap == output_image_path:
                    return
                pil_image = Image.open(output_image_path)
                # 限制图片最大尺寸为 300x300
                max_size = (200, 200)
                pil_image.thumbnail(max_size, Image.Resampling.LANCZOS)
                self.photo_image = ImageTk.PhotoImage(pil_image)
                self.img_video_cap_label.config(image=self.photo_image)
                self.img_video_cap = output_image_path
                return

            # 1. 加载视频文件
            # self.log(f"正在加载视频: {video_path}")
            video_clip = VideoFileClip(video_path)

            # 获取视频总时长
            total_duration = video_clip.duration
            # self.log(f"视频总时长: {total_duration:.2f} 秒")

            if time_in_seconds < 0:
                time_in_seconds = time_in_seconds + total_duration

            # 检查时间点是否有效
            if time_in_seconds < 0 or time_in_seconds > total_duration:
                raise ValueError(
                    f"指定的时间点 ({time_in_seconds}s) 超出了视频范围 (0 - {total_duration:.2f}s)。"
                )

            # 2. 提取指定时间点的帧
            # self.log(f"正在截取第 {time_in_seconds}s 处的画面...")
            frame_image = video_clip.get_frame(time_in_seconds)

            # 3. 将帧保存为图片
            # moviepy 使用的是 PIL/Pillow 库，所以我们可以直接用它保存
            result_image = Image.fromarray(frame_image)

            # 确保输出目录存在
            output_dir = os.path.dirname(output_image_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            result_image.save(output_image_path)
            # self.log(f"截图已成功保存到: {output_image_path}")

            # 4. 关闭 clip 以释放资源
            video_clip.close()

            if os.path.isfile(output_image_path):
                pil_image = Image.open(output_image_path)
                # 限制图片最大尺寸为 300x300
                max_size = (200, 200)
                pil_image.thumbnail(max_size, Image.Resampling.LANCZOS)
                self.photo_image = ImageTk.PhotoImage(pil_image)
                self.img_video_cap_label.config(image=self.photo_image)
                self.img_video_cap = output_image_path

        except FileNotFoundError:
            self.log(f"错误: 找不到视频文件 '{video_path}'")
        except ValueError as e:
            self.log(f"错误: {e}")
        except ImportError:
            self.log(
                "错误: 未找到 'PIL' 或 'Pillow' 库。请运行 'pip install Pillow' 安装。"
            )
        except Exception as e:
            self.log(f"发生了一个意外错误: {e}")

    def detect_video_framerate(self, video_path, threshold_ms=5.0, sample_limit=None):
        """
        分析视频文件以确定它是恒定帧率 (CFR) 还是可变帧率 (VFR)。

        Args:
            video_path (str): 视频文件的路径。
            threshold_ms (float): 判断VFR的阈值（毫秒）。帧间时间间隔的标准差超过此值，则认为是VFR。
                                默认为 5.0 毫秒。
            sample_limit (int, optional): 限制分析的帧数，用于加速大数据集的检查。默认为 None (分析所有帧)。

        Returns:
            dict: 包含分析结果的字典。
                - 'is_vfr': (bool) True 表示 VFR, False 表示 CFR (或接近CFR)。
                - 'std_dev_ms': (float) 帧间时间间隔的标准差（毫秒）。
                - 'avg_interval_ms': (float) 平均帧间时间间隔（毫秒）。
                - 'declared_avg_fps': (float or None) 视频元数据中声明的平均帧率。
                - 'sampled_frames': (int) 实际采样的帧数。
        """
        try:
            with av.open(video_path) as container:
                # 获取第一个视频流
                video_stream = next(
                    (s for s in container.streams if s.type == "video"), None
                )
                if not video_stream:
                    raise ValueError("视频文件中未找到视频流。")

                # 尝试获取元数据中的平均帧率（仅供参考，不一定准确）
                declared_avg_fps = (
                    float(video_stream.average_rate)
                    if video_stream.average_rate
                    else None
                )

                # 存储解码后帧的时间戳 (PTS - Presentation Time Stamp)
                pts_times_sec = []

                for frame in container.decode(video_stream):
                    # 使用 frame.pts * time_base 将 PTS 转换为以秒为单位的时间戳
                    timestamp_sec = frame.pts * video_stream.time_base
                    pts_times_sec.append(timestamp_sec)

                    # 如果设置了采样限制，则达到数量后停止读取
                    if sample_limit and len(pts_times_sec) >= sample_limit:
                        break

                if len(pts_times_sec) < 2:
                    raise ValueError("视频帧数太少，无法进行分析。")

                # 计算每帧之间的时间间隔（秒）
                frame_intervals_sec = [
                    pts_times_sec[i + 1] - pts_times_sec[i]
                    for i in range(len(pts_times_sec) - 1)
                ]

                sum_sec = sum(frame_intervals_sec)
                len_frames = len(frame_intervals_sec)
                # 计算平均时间间隔（秒）
                avg_interval_sec = sum_sec / len_frames

                # 计算时间间隔的标准差（秒）
                variance = sum(
                    (x - avg_interval_sec) ** 2 for x in frame_intervals_sec
                ) / len(frame_intervals_sec)
                std_dev_sec = math.sqrt(variance)

                # 转换为毫秒
                std_dev_ms = std_dev_sec * 1000
                avg_interval_ms = avg_interval_sec * 1000

                sampled_frames = len(pts_times_sec)

                # 判断是否为 VFR
                is_vfr = std_dev_ms > threshold_ms

                return {
                    "is_vfr": is_vfr,
                    "std_dev_ms": std_dev_ms,
                    "avg_interval_ms": avg_interval_ms,
                    "declared_avg_fps": declared_avg_fps,
                    "sampled_frames": sampled_frames,
                    "sum_sec": float(sum_sec * 1000),
                    "len_frames": len_frames,
                }

        except Exception as e:
            self.log(f"分析视频时出错: {e}")
            return None

    def count_decoded_frames(self, video_path):
        """
        使用 PyAV 解码，并通过过滤重复的 PTS 来模拟 FFmpeg 的帧提取逻辑。
        这通常会得到与 'ffmpeg -i input.mp4 %05d.png' 更接近的计数。
        """
        unique_pts_set = set()
        frame_count = 0

        with av.open(video_path) as container:
            video_stream = container.streams.video[0]

            # 重要：确保解码所有帧
            video_stream.codec_context.skip_frame = "NONE"

            for packet in container.demux(video_stream):
                for frame in packet.decode():
                    # 计算该帧的显示时间戳（秒）
                    pts_seconds = frame.pts * video_stream.time_base

                    # 检查这个时间戳是否已经存在
                    # 使用时间戳作为键，可以有效过滤掉重复显示的帧
                    if pts_seconds not in unique_pts_set:
                        unique_pts_set.add(pts_seconds)
                        frame_count += 1
                    # 如果时间戳已存在，则忽略此帧，因为它与前面某个帧是同一时刻显示的

        return frame_count

    def get_ffmpeg_display_timestamps(self, video_path):
        """
        使用 FFmpeg 获取视频中每一帧的显示时间戳 (PTS)。
        这些时间戳对应 FFmpeg 在处理或提取帧时看到的序列。
        """
        cmd = [
            self.path_ffmpeg(),
            "-i",
            video_path,
            "-vf",
            "showinfo",  # 应用 showinfo 过滤器
            "-f",
            "null",  # 不输出视频，丢弃数据
            "-",  # 输出到标准错误 (stderr)
        ]

        try:
            self.log(" ".join(cmd))
            # 创建子进程并添加到进程列表
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            self.processes.append(process)

            _, stderr = process.communicate()
            output = stderr.decode("utf-8", errors="ignore")

            self.log(f"output: {output}")

            # 使用正则表达式匹配 showinfo 输出中的 pts_time
            # 格式类似: [Parsed_showinfo_0 @ 0x...] n:39 pts:1234.567 ...
            pts_pattern = r"pts_time:(\d+\.?\d*)"
            pts_times = [
                float(match)
                for match in re.findall(pts_pattern, output)
                if match != "N/A"
            ]

            return pts_times

        except subprocess.CalledProcessError as e:
            self.log(f"FFmpeg 命令执行失败: {e}")
            return None
        except FileNotFoundError:
            self.log(
                "错误: 未找到 'ffmpeg' 命令。请确保 FFmpeg 已安装并添加到系统 PATH 中。"
            )
            return None

    def analyze_vfr_from_ffmpeg_ts(self, pts_times, threshold_ms=5.0):
        """
        基于 FFmpeg 提供的时间戳列表分析 VFR。
        """
        if not pts_times or len(pts_times) < 2:
            self.log("错误: 时间戳数量不足，无法分析。")
            return None

        # 计算每帧之间的时间间隔（秒）
        frame_intervals_sec = [
            pts_times[i + 1] - pts_times[i] for i in range(len(pts_times) - 1)
        ]

        # 计算平均时间间隔和标准差（秒）
        avg_interval_sec = sum(frame_intervals_sec) / len(frame_intervals_sec)
        variance = sum((x - avg_interval_sec) ** 2 for x in frame_intervals_sec) / len(
            frame_intervals_sec
        )
        std_dev_sec = math.sqrt(variance)

        # 转换为毫秒
        std_dev_ms = std_dev_sec * 1000
        avg_interval_ms = avg_interval_sec * 1000

        sampled_frames = len(pts_times)

        # 判断是否为 VFR
        is_vfr = std_dev_ms > threshold_ms

        return {
            "is_vfr": is_vfr,
            "std_dev_ms": std_dev_ms,
            "avg_interval_ms": avg_interval_ms,
            "sampled_frames": sampled_frames,
            "calculated_fps": 1000 / avg_interval_ms if avg_interval_ms > 0 else 0,
        }

    def check_vfr_with_ffmpeg(self, video_path):
        self.log("正在调用 FFmpeg 获取显示时间戳...")
        ffmpeg_timestamps = self.get_ffmpeg_display_timestamps(video_path)

        if ffmpeg_timestamps is not None:
            self.log(
                f"成功获取 {len(ffmpeg_timestamps)} 个时间戳 (对应 FFmpeg 处理的帧数 {len(ffmpeg_timestamps)})"
            )

            self.log("\n--- 基于 FFmpeg 时间戳的 VFR 分析 ---")
            vfr_result = self.analyze_vfr_from_ffmpeg_ts(
                ffmpeg_timestamps, threshold_ms=5.0
            )

            if vfr_result:
                self.log(f"vfr_result: {vfr_result}")
                self.log(f"采样帧数: {vfr_result['samp  led_frames']}")
                self.log(f"计算得出平均FPS: {vfr_result['calculated_fps']:.2f}")
                self.log(f"帧间隔标准差: {vfr_result['std_dev_ms']:.2f} ms")
                self.log(f"平均帧间隔: {vfr_result['avg_interval_ms']:.2f} ms")

                if vfr_result["is_vfr"]:
                    self.log("\n🔍 结论: 视频是 **VFR (可变帧率)** (基于 FFmpeg 视角)")
                else:
                    self.log(
                        "\n🔍 结论: 视频是 **CFR (恒定帧率)** 或接近CFR (基于 FFmpeg 视角)"
                    )
                self.log("------------------------------------")
        else:
            self.log("无法获取 FFmpeg 时间戳，分析失败。")

    def analyze_vfr_pyav(self, video_path, threshold_ms=5.0, sample_limit=None):
        """
        使用 PyAV 分析视频的解码帧时间戳，判断其是否为 VFR。
        这个方法判断的是视频文件本身的 VFR 特性。

        Args:
            video_path (str): 视频文件的路径。
            threshold_ms (float): 判断VFR的阈值（毫秒）。帧间时间间隔的标准差超过此值，则认为是VFR。
                                默认为 5.0 毫秒。
            sample_limit (int, optional): 限制分析的帧数，用于加速大数据集的检查。默认为 None (分析所有帧)。

        Returns:
            dict: 包含分析结果的字典。
                - 'is_vfr': (bool) True 表示 VFR, False 表示 CFR (或接近CFR)。
                - 'std_dev_ms': (float) 帧间时间间隔的标准差（毫秒）。
                - 'avg_interval_ms': (float) 平均帧间时间间隔（毫秒）。
                - 'calculated_avg_fps': (float) 计算得出的平均帧率。
                - 'sampled_frames': (int) 实际采样的帧数。
                - 'declared_avg_fps': (float or None) 视频元数据中声明的平均帧率。
        """
        try:
            with av.open(video_path) as container:
                # 获取第一个视频流
                video_stream = next(
                    (s for s in container.streams if s.type == "video"), None
                )
                if not video_stream:
                    raise ValueError("视频文件中未找到视频流。")

                # 获取元数据中的平均帧率（仅供参考）
                declared_avg_fps = (
                    float(video_stream.average_rate)
                    if video_stream.average_rate
                    else None
                )

                pts_times_sec = []

                # 确保解码所有帧
                # 注意：这里我们迭代的是解码后的帧对象
                for frame in container.decode(video_stream):
                    # 将 PTS (Presentation Time Stamp) 转换为秒
                    timestamp_sec = frame.time_base * frame.pts
                    if (
                        timestamp_sec is not None and timestamp_sec >= 0
                    ):  # 确保时间戳有效
                        pts_times_sec.append(timestamp_sec)

                    # 如果设置了采样限制，则达到数量后停止读取
                    if sample_limit and len(pts_times_sec) >= sample_limit:
                        break

                if len(pts_times_sec) < 2:
                    raise ValueError("视频帧数太少，无法进行分析。")

                # 计算每帧之间的时间间隔（秒）
                frame_intervals_sec = [
                    pts_times_sec[i + 1] - pts_times_sec[i]
                    for i in range(len(pts_times_sec) - 1)
                ]

                # 计算平均时间间隔（秒）
                avg_interval_sec = sum(frame_intervals_sec) / len(frame_intervals_sec)

                # 计算时间间隔的标准差（秒）
                variance = sum(
                    (x - avg_interval_sec) ** 2 for x in frame_intervals_sec
                ) / len(frame_intervals_sec)
                std_dev_sec = math.sqrt(variance)

                # 转换为毫秒
                std_dev_ms = std_dev_sec * 1000
                avg_interval_ms = avg_interval_sec * 1000

                calculated_avg_fps = (
                    1000.0 / avg_interval_ms if avg_interval_ms > 0 else 0
                )
                sampled_frames = len(pts_times_sec)

                # 判断是否为 VFR
                is_vfr = std_dev_ms > threshold_ms

                return {
                    "is_vfr": is_vfr,
                    "std_dev_ms": std_dev_ms,
                    "avg_interval_ms": avg_interval_ms,
                    "calculated_avg_fps": calculated_avg_fps,
                    "sampled_frames": sampled_frames,
                    "declared_avg_fps": declared_avg_fps,
                }

        except Exception as e:
            print(f"分析视频时出错: {e}", file=sys.stderr)
            return None

    def cal_video_level(self, info):
        scale = int(self.scale_var.get())
        height = info["height"] * scale
        width = info["width"] * scale
        fps = info["fps"]

        """
        根据分辨率和帧率计算满足要求的 H.264 最低 Level。

        Args:
            width (int): 视频宽度 (例如 1920)
            height (int): 视频高度 (例如 1080)
            fps (float): 视频帧率 (例如 30.0)

        Returns:
            str: 对应的 H.264 Level (例如 "4.0", "5.1") 或 None (如果超出支持范围)
        """

        # H.264 Level 表 (Main/High Profile)
        # Level: (MaxMBPS, MaxFS, MaxDPB, MaxBR_kbps)
        # MaxMBPS: 最大宏块处理速率 (宏块/秒)
        # MaxFS: 最大帧大小 (宏块) - 用于计算最大分辨率
        # MaxDPB: 最大解码图片缓存 (宏块) - 对播放设备缓存有要求
        # MaxBR_kbps: 最大比特率 (kbps) - 此处未使用，仅为完整性展示

        # 为了简化计算，我们主要关心 MaxMBPS 和 MaxFS
        h264_levels = {
            1: (1485, 99, 396, 64),
            1.1: (3000, 396, 900, 192),
            1.2: (6000, 396, 2376, 384),
            1.3: (11880, 396, 2376, 768),
            2: (11880, 396, 2376, 2000),
            2.1: (19800, 792, 4752, 4000),
            2.2: (20250, 1620, 8100, 4000),
            3: (40500, 1620, 8100, 10000),
            3.1: (108000, 3600, 18000, 14000),
            3.2: (216000, 5120, 20480, 20000),
            4: (245760, 8192, 32768, 20000),
            4.1: (245760, 8192, 32768, 50000),
            4.2: (522240, 8704, 34816, 50000),
            5: (589824, 22080, 110400, 135000),
            5.1: (983040, 36864, 184320, 240000),
            5.2: (2228224, 36864, 184320, 240000),
        }

        # 1. 计算宏块数 (需要将宽高扩展到 16 的倍数)
        padded_width = math.ceil(width / 16) * 16
        padded_height = math.ceil(height / 16) * 16

        macroblocks_per_frame = (padded_width // 16) * (padded_height // 16)

        # 2. 计算宏块处理速率 (MaxMBPS)
        max_mbps_required = macroblocks_per_frame * fps

        # 3. 查找满足 MaxMBPS 要求的最低 Level
        # 4. 同时验证该 Level 的 MaxFS (最大帧大小) 限制
        target_level = None
        for level_name, (max_mbps, max_fs, _, _) in sorted(h264_levels.items()):
            if max_mbps >= max_mbps_required:
                # 检查分辨率是否也满足 MaxFS 限制
                if macroblocks_per_frame <= max_fs:
                    target_level = level_name
                    break  # 找到满足条件的第一个（最低）Level 即可

        return str(target_level) if target_level is not None else None

    def on_esc(self, *args):
        if not self.is_running():
            self.exit_application()

    def exit_application(self):
        """退出应用程序并结束所有进程"""
        # 终止所有子进程
        for process in self.processes:
            try:
                # 尝试优雅地终止进程
                process.terminate()
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                # 如果进程没有响应，强制终止
                process.kill()
            except Exception as e:
                self.log(f"终止进程时出错: {e}")

        # 查找并终止可能的残留进程
        try:
            current_process = psutil.Process()
            children = current_process.children(recursive=True)
            for child in children:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass

            # 等待进程结束
            _, alive = psutil.wait_procs(children, timeout=3)
            for p in alive:
                try:
                    p.kill()
                except psutil.NoSuchProcess:
                    pass
        except Exception as e:
            self.log(f"清理进程时出错: {e}")

        if self.log_file:
            self.log_file.close()
            self.log_file = None

        # 退出应用
        self.root.quit()
        self.root.destroy()

    def log(self, message):
        """添加日志信息"""

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}"

        # 添加到日志列表
        self.log_messages.append(log_message)

        # 更新日志文本框
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, log_message + "\n")
        self.log_text.config(state="disabled")
        self.log_text.see(tk.END)  # 滚动到最新日志

        # 更新状态标签
        # self.status_var.set(message)
        self.root.update()

        if self.log_file:
            self.log_file.write(log_message + "\n")
            self.log_file.flush()

    def path_ffmpeg(self):
        return "ffmpeg.exe"
        # return os.path.join(self.project_root, "ffmpeg.exe")

    def path_out_frames(self):
        file = "frame%08d." + self.format_var.get()
        return os.path.join(self.dir_frames_enhance, file)

    def path_video_out(self, video_path):
        video_out_dir = self.video_out_var.get() or ""
        if video_out_dir == "":
            # 获取桌面路径
            video_out_dir = os.path.join(os.path.expanduser("~"), "Desktop")

        # 获取原始文件名和扩展名
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        ext = os.path.splitext(video_path)[1]

        # 生成带时间戳的文件名，确保唯一性
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_video_name = f"enhanced_{base_name}_{timestamp}{ext}"
        output_video_path = os.path.join(video_out_dir, output_video_name)

        return output_video_path

    def browse_video(self):
        """浏览选择视频文件"""
        file_path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[
                ("视频文件", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm"),
                ("所有文件", "*.*"),
            ],
        )

        if file_path:
            self.video_path_var.set(file_path)

    def browse_video_out(self):
        """浏览选择视频输出目录"""
        file_path = filedialog.askdirectory(
            title="选择视频输出目录",
            initialdir=self.video_out_var.get(),
        )

        if file_path:
            self.video_out_var.set(file_path)

    def get_video_fps(self, video_path):
        """获取视频的FPS"""
        try:
            self.log("正在获取视频帧率...")

            cmd = [self.path_ffmpeg(), "-i", video_path]

            # 创建子进程并添加到进程列表
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            self.processes.append(process)

            # 修复：同时捕获stdout和stderr，并将它们组合起来进行分析
            stdout, stderr = process.communicate()
            # ffmpeg的详细信息通常输出到stderr，所以我们需要检查stderr
            output = stdout.decode("utf-8", errors="ignore") + stderr.decode(
                "utf-8", errors="ignore"
            )

            self.log("output: " + output)

            # 查找FPS信息 - 改进的模式匹配

            # 首先尝试匹配标准的fps模式
            fps_patterns = [
                r"(\d+(?:\.\d+)?)\s+fps",  # 标准fps模式，如 "23.98 fps"
                r"(\d+(?:\.\d+)?)\s*tbr",  # 平均帧率模式，如 "23.98 tbr"
                r"(\d+(?:\.\d+)?)\s+fps,",  # 带逗号的fps模式
                r",\s*(\d+(?:\.\d+)?)\s+fps",  # 逗号后的fps模式
                r"(\d+(?:\.\d+)?)\s+tbr,",  # 带逗号的tbr模式
                r",\s*(\d+(?:\.\d+)?)\s+tbr",  # 逗号后的tbr模式
            ]

            for pattern in fps_patterns:
                match = re.search(pattern, output, re.IGNORECASE)
                if match:
                    fps = float(match.group(1))
                    self.log(f"检测到视频帧率: {fps} FPS")
                    return fps

            # 如果标准模式都未匹配，尝试更宽松的匹配
            # 匹配任何数字后跟fps或tbr的模式
            loose_patterns = [
                r"(\d+(?:\.\d+)?)\s*[fF][pP][sS]",
                r"(\d+(?:\.\d+)?)\s*[tT][bB][rR]",
            ]

            for pattern in loose_patterns:
                match = re.search(pattern, output)
                if match:
                    fps = float(match.group(1))
                    self.log(f"检测到视频帧率: {fps} FPS")
                    return fps

            self.log("未检测到帧率信息，使用默认值 30 FPS")
            return 30.0  # 默认值
        except Exception as e:
            self.log(f"获取帧率时出错: {e}，使用默认值 30 FPS")
            return 30.0

    def get_video_info(self, video_path):
        cap = cv2.VideoCapture(video_path)

        info = {}
        info["file_size"] = os.path.getsize(video_path)
        info["total_frames"] = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        info["fps"] = cap.get(cv2.CAP_PROP_FPS)
        info["width"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        info["height"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        total_sec = info["total_frames"] / info["fps"]
        info["total_sec"] = total_sec
        hours = int(total_sec // 3600)
        minutes = int((total_sec % 3600) // 60)
        seconds = total_sec % 60  # 保留小数部分
        info["time"] = f"{hours:02d}:{minutes:02d}:{seconds:02.3f}"

        cap.release()
        return info

    def count_dir_frames_extract(self):
        return len(os.listdir(self.dir_frames_extract))

    def count_dir_frames_enhance(self):
        return len(os.listdir(self.dir_frames_enhance))

    def cut_video_ffmpeg(self, video_path):
        """
        使用 ffmpeg-python 裁剪掉 VFR 视频末尾的 N 秒。
        """
        try:
            self.proc_state = ProcState.CUT
            self.cut_video_path = None

            head_sec = float(self.cut_head_sec_var.get())
            tail_sec = float(self.cut_tail_sec_var.get())
            self.log(f"正在裁剪视频({head_sec},{tail_sec})...")

            if head_sec <= 0 and tail_sec <= 0:
                return True

            # 获取视频总时长
            probe = ffmpeg.probe(video_path)
            total_duration = float(
                probe["streams"][0]["duration"]
            )  # 通常取第一个流（视频流）

            # 计算新的开始时间和持续时间
            new_start_time = head_sec
            new_duration = total_duration - head_sec - tail_sec

            if new_duration <= 0:
                raise ValueError(
                    f"要移除的秒数 ({head_sec}) 不能大于或等于视频总时长 ({total_duration})。"
                )

            file_name = os.path.basename(video_path)
            self.cut_video_path = os.path.join(self.dir_cut, file_name)

            # 构建 ffmpeg 流程图
            # 使用 input 的 'ss' 和 't' 参数
            stream = ffmpeg.input(video_path, ss=new_start_time, t=new_duration)
            stream = ffmpeg.output(
                stream, self.cut_video_path, c="copy", avoid_negative_ts="make_zero"
            )

            # 运行命令
            ffmpeg.run(stream, overwrite_output=True)
            self.log(f"裁剪视频已成功处理并保存至: {self.cut_video_path}")

            return True

        except Exception as e:
            messagebox.showerror("错误", f"裁剪视频时出错: {str(e)}")
            self.log(f"裁剪视频时出错: {str(e)}")
            return False

    def extract_frames(self, video_path):
        """从视频中提取帧"""
        try:
            self.log("正在提取视频帧...")
            self.proc_state = ProcState.EXTRACT

            # 清空临时帧目录
            if self.count_dir_frames_extract() > 0:
                shutil.rmtree(self.dir_frames_extract)
                self.create_paths()

            # 提取帧 - 使用更兼容的参数
            cmd = [
                self.path_ffmpeg(),
                "-hwaccel",
                "cuda",  # 启用CUDA硬件加速
                "-i",
                video_path,
                "-vf",
                "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # 确保宽高为偶数
                "-q:v",
                "2",  # JPEG质量 (1-31, 1为最高质量)
                "-start_number",
                "0",  # 从0开始编号
                os.path.join(self.dir_frames_extract, "frame%08d.jpg"),
            ]

            self.log(" ".join(cmd))
            self.log("执行帧提取命令...")
            # 创建子进程并添加到进程列表
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            self.processes.append(process)

            _, stderr = process.communicate()
            if process.returncode != 0:
                # 如果上面的方法失败，尝试基本参数
                cmd = [
                    self.path_ffmpeg(),
                    "-i",
                    video_path,
                    "-q:v",
                    "2",
                    os.path.join(self.dir_frames_extract, "frame%08d.jpg"),
                ]

                self.log(" ".join(cmd))
                self.log("尝试备用帧提取方法...")

                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                self.processes.append(process)

                _, stderr = process.communicate()
                if process.returncode != 0:
                    raise Exception(
                        f"提取帧失败: {stderr.decode('utf-8', errors='ignore')}"
                    )

            self.log(
                "视频帧提取完成, count_dir_frames_extract: "
                + str(self.count_dir_frames_extract())
            )
            return True
        except Exception as e:
            messagebox.showerror("错误", f"提取帧时出错: {str(e)}")
            self.log(f"提取帧时出错: {str(e)}")
            return False

    def enhance_frames(self):
        """使用Real-ESRGAN增强帧"""
        try:
            self.log("正在增强视频帧...")

            # 清空输出帧目录
            if self.count_dir_frames_enhance() > 0:
                shutil.rmtree(self.dir_frames_enhance)
                self.create_paths()

            # 执行增强
            realesrgan_exe = os.path.join(
                self.project_root, "realesrgan-ncnn-vulkan.exe"
            )
            if not os.path.exists(realesrgan_exe):
                raise Exception(
                    "未找到realesrgan-ncnn-vulkan.exe文件，请确保该文件在项目根目录中"
                )

            self.proc_state = ProcState.ENHANCE

            # 构建命令参数
            cmd = [
                realesrgan_exe,
                "-i",
                self.dir_frames_extract,
                "-o",
                self.dir_frames_enhance,
                "-n",
                self.model_var.get(),
                "-s",
                self.scale_var.get(),
                "-f",
                self.format_var.get(),
            ]

            # 如果是jpg格式，添加额外参数提高兼容性
            if self.format_var.get() == "jpg":
                cmd.extend(["-g", "0"])  # 禁用GPU优化以提高兼容性

            # tile-size
            if self.tile_size_var.get() != "default":
                cmd.extend(["-t", self.tile_size_var.get()])

            # thread count for load/proc/save
            if self.thread_count_var.get() != "default":
                cmd.extend(["-j", self.thread_count_var.get()])

            # tta mode
            # if self.tta_mode_var.get() == "enable":
            #     cmd.extend(["-x"])

            self.video_info["extract_frames"] = self.count_dir_frames_extract()
            self.log(" ".join(cmd))
            self.log("执行帧增强命令...")

            # 创建子进程并添加到进程列表
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            self.processes.append(process)

            _, stderr = process.communicate()
            if process.returncode != 0:
                # 尝试不带额外参数的基本命令
                cmd = [
                    realesrgan_exe,
                    "-i",
                    self.dir_frames_extract,
                    "-o",
                    self.dir_frames_enhance,
                    "-n",
                    self.model_var.get(),
                    "-s",
                    self.scale_var.get(),
                    "-f",
                    self.format_var.get(),
                ]

                self.log(" ".join(cmd))
                self.log("尝试备用增强方法...")

                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                self.processes.append(process)

                _, stderr = process.communicate()
                if process.returncode != 0:
                    raise Exception(
                        f"增强帧失败: {stderr.decode('utf-8', errors='ignore')}"
                    )

            self.log("视频帧增强完成")
            return True
        except Exception as e:
            messagebox.showerror("错误", f"增强帧时出错: {str(e)}")
            self.log(f"增强帧时出错: {str(e)}")
            return False

    def merge_frames(self, video_path):
        """将增强后的帧合并为视频"""
        try:
            self.log("正在合并视频帧...")
            self.proc_state = ProcState.MERGE

            # 获取原始视频的FPS
            # fps = self.get_video_fps(video_path)
            fps = float(self.fps_force_var.get())
            if fps <= 0:
                fps = self.video_info["fps"]
                total_sec = self.video_info["total_sec"]
                frames_extract = self.count_dir_frames_enhance()
                total_frames = self.video_info["total_frames"]
                num = frames_extract - total_frames
                if num < 0:
                    num = -num

                if num > fps:
                    # TODO VFR
                    now_sec = frames_extract / fps
                    fps = frames_extract / total_sec
                    fps_sec = frames_extract / fps
                    self.log(
                        f"帧数差异较大: {num}={frames_extract}-{total_frames}, fps={fps}, total_sec={total_sec}, now_sec={now_sec}, fps_sec={fps_sec}"
                    )

            # 视频输出路径
            output_video_path = self.path_video_out(video_path)

            # 合并帧为视频 - 使用针对QQ播放器优化的参数
            # 首先尝试保留音频的版本
            #  cmd = [
            #     self.path_ffmpeg(),
            #     "-r", str(fps),
            #     "-i", os.path.join(self.out_frames_dir, "frame%08d.jpg"),
            #     "-i", video_path,
            #     "-map", "0:v:0",
            #     "-map", "1:a:0",
            #     "-c:a", "aac",  # 使用AAC音频编码提高兼容性
            #     "-c:v", "libx264",
            #     "-preset", "fast",  # 使用快速编码预设
            #     "-crf", "23",  # 视频质量控制
            #     "-r", str(fps),
            #     "-pix_fmt", "yuv420p",
            #     "-profile:v", "baseline",  # 使用baseline profile提高兼容性
            #     "-level", "3.0",  # 使用level 3.0提高兼容性
            #     "-movflags", "+faststart",  # 优化文件结构以便快速开始播放
            #     "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # 确保宽高为偶数
            #     "-g", "30",  # GOP大小
            #     "-bf", "0",  # 不使用B帧以提高兼容性
            #     output_video_path
            # ]
            cmd = [
                self.path_ffmpeg(),
                "-hwaccel",
                "cuda",  # 启用CUDA硬件加速
                "-r",
                str(fps),
                "-i",
                self.path_out_frames(),
                "-i",
                video_path,
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:a",
                "aac",  # 使用AAC音频编码提高兼容性
                # "-c:v", "libx264",
                # '-c:v', 'h264_nvenc',         # 使用NVIDIA H.264编码器
                # '-c:v', 'hevc_vaapi',         # 使用NVIDIA  H.265/HEVC (VAAPI)编码器
                "-c:v",
                "h264_nvenc",  # 使用NVIDIA H.264编码器
                # "-preset", "fast",  # 使用快速编码预设
                "-preset",
                "p6",
                # "-crf", "23",  # 视频质量控制
                "-cq",
                "15",  # h264_nvenc 不能用crf
                "-r",
                str(fps),
                "-pix_fmt",
                "yuv420p",
                # "-profile:v", "baseline",  # 使用baseline profile提高兼容性
                "-profile:v",
                "high",
                "-b:v",
                self.bit_rate_var.get(),
                "-maxrate",
                self.max_rate_var.get(),
                "-bufsize",
                self.max_rate_var.get(),
                # "-level", "3.0",  # 使用level 3.0提高兼容性
                # "-level", "4.1",    # CUDA加速需要用更高的level
                "-level",
                self.level_var.get(),
                "-movflags",
                "+faststart",  # 优化文件结构以便快速开始播放
                "-vf",
                "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # 确保宽高为偶数
                "-g",
                "30",  # GOP大小
                "-bf",
                "0",  # 不使用B帧以提高兼容性
                output_video_path,
            ]

            self.log(" ".join(cmd))
            self.log("执行视频合并命令（带音频）...")
            # 创建子进程并添加到进程列表
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            self.processes.append(process)

            _, stderr = process.communicate()
            if process.returncode != 0:
                self.log(
                    f"执行视频合并命令（带音频）失败(code:{process.returncode}): {stderr.decode('utf-8', errors='ignore')}"
                )

                # 如果上面的方法失败，尝试简化版本（仅视频）
                cmd = [
                    self.path_ffmpeg(),
                    "-r",
                    str(fps),
                    "-i",
                    self.path_out_frames(),
                    "-i",
                    video_path,
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-c:a",
                    "aac",  # 使用AAC音频编码提高兼容性
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",  # 使用快速编码预设
                    "-crf",
                    "23",  # 视频质量控制
                    "-r",
                    str(fps),
                    "-pix_fmt",
                    "yuv420p",
                    "-profile:v",
                    "baseline",  # 使用baseline profile提高兼容性
                    "-level",
                    "3.0",  # 使用level 3.0提高兼容性
                    "-movflags",
                    "+faststart",  # 优化文件结构以便快速开始播放
                    "-vf",
                    "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # 确保宽高为偶数
                    "-g",
                    "30",  # GOP大小
                    "-bf",
                    "0",  # 不使用B帧以提高兼容性
                    output_video_path,
                ]
                # cmd = [
                #     self.path_ffmpeg(),
                #     "-r", str(fps),
                #     "-i", self.path_out_frames(),
                #     "-c:v", "libx264",
                #     "-preset", "fast",
                #     "-crf", "23",
                #     "-r", str(fps),
                #     "-pix_fmt", "yuv420p",
                #     "-profile:v", "baseline",
                #     "-level", "3.0",
                #     "-movflags", "+faststart",
                #     "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                #     "-g", "30",
                #     "-bf", "0",
                #     '-strict', 'experimental',    # 允许实验性编码
                #     output_video_path
                # ]

                self.log(" ".join(cmd))
                self.log("尝试仅视频合并...")

                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                self.processes.append(process)

                _, stderr = process.communicate()
                if process.returncode != 0:
                    self.log(
                        f"尝试仅视频合并失败(code:{process.returncode}): {stderr.decode('utf-8', errors='ignore')}"
                    )
                    # 如果仍然失败，使用最基本的参数
                    cmd = [
                        self.path_ffmpeg(),
                        "-r",
                        str(fps),
                        "-i",
                        self.path_out_frames(),
                        "-c:v",
                        "libx264",
                        "-pix_fmt",
                        "yuv420p",
                        "-preset",
                        "ultrafast",  # 使用最快编码速度
                        output_video_path,
                    ]

                    self.log(" ".join(cmd))
                    self.log("尝试基本视频合并...")

                    process = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                    )
                    self.processes.append(process)

                    _, stderr = process.communicate()
                    if process.returncode != 0:
                        raise Exception(
                            f"合并视频失败: {stderr.decode('utf-8', errors='ignore')}"
                        )

            self.log(f"视频合并完成，输出文件: {output_video_path}")
            self.log(
                "output video info: " + str(self.get_video_info(output_video_path))
            )
            # messagebox.showinfo("完成", f"视频增强完成！输出文件已保存到:\n{output_video_path}")
            return True
        except Exception as e:
            messagebox.showerror("错误", f"合并视频时出错: {str(e)}")
            self.log(f"合并视频时出错: {str(e)}")
            return False

    def has_step(self, dst):
        step = self.step_var.get()
        if step == ProcStep.ALL:
            return True
        return step == dst

    def video_compress(self, video_path):
        self.log("开始视频压缩流程...")
        self.proc_state = ProcState.COMPRESS
        return video_compress.to_h265(
            video_path, self.video_out_var.get(), use_gpu=True
        )

    def enhancement_process(self):
        """执行完整的增强流程"""
        try:
            video_path = self.video_path_var.get()
            if not video_path:
                messagebox.showwarning("警告", "请先选择视频文件")
                self.log("请先选择视频文件")
                return

            if not os.path.exists(video_path):
                messagebox.showerror("错误", "选择的视频文件不存在")
                self.log("选择的视频文件不存在")
                return

            self.save_configs()

            self.log("-----------------------------------------------")
            self.log("step: " + self.step_var.get())
            self.log("video_path: " + video_path)

            if self.step_var.get() == ProcStep.COMPRESS:
                if self.video_compress(video_path):
                    self.proc_state = ProcState.FINISH
                return

            self.log("开始视频增强流程...")

            if not self.has_step(ProcStep.CUT):
                pass
            elif not self.cut_video_ffmpeg(video_path):
                return
            elif self.cut_video_path:
                video_path = self.cut_video_path
                self.video_info = self.get_video_info(video_path)
                self.log(f"video_path: {video_path}")
                self.log(f"video_info: {self.video_info}")

            scale = self.scale_var.get()
            if scale == "4":
                scale = int(scale)
                width = int(self.video_info["width"])
                height = int(self.video_info["height"])
                if (width * scale) >= 4096 or (height * scale) > 4096:
                    self.log(
                        f"scale({scale}) over for {width} * {height}, scale fix to 2..."
                    )
                    self.scale_var.set("2")
                    self.scale_fix_lower = "4"
                    # self.on_path_video_change(None)

            # 步骤1: 提取帧
            if not self.has_step(ProcStep.EXTRACT):
                pass
            elif not self.extract_frames(video_path):
                return

            # 步骤2: 增强帧
            if not self.has_step(ProcStep.ENHANCE):
                pass
            elif not self.enhance_frames():
                return

            # 步骤3: 合并帧
            if not self.has_step(ProcStep.MERGE):
                pass
            elif not self.merge_frames(video_path):
                return

            # 完成
            self.log("视频增强流程完成")
            self.proc_state = ProcState.FINISH

        except Exception as e:
            messagebox.showerror("错误", f"处理过程中发生错误: {str(e)}")
            self.log(f"处理过程中发生错误: {str(e)}")
        finally:
            self.start_button.config(state="normal")
            self.step_combo.config(state="normal")
            self.browse_video_button.config(state="normal")
            self.browse_video_out_button.config(state="normal")

            if self.scale_fix_lower and self.scale_var.get() == "2":
                scale = self.scale_var.get()
                self.log(f"scale({scale}) fix to 4...")
                self.scale_var.set("4")
                self.scale_fix_lower = None

            if self.proc_state != ProcState.FINISH:
                pass
            elif self.setting.delete_task(self.video_path_var.get()):
                self.rfsh_tasks()
                done = self.proc_done_var.get()
                if done == ProcDone.NEXT:
                    self.log(f"wait for {ProcState.NEXT}...")
                    return
                elif done == ProcDone.EXIT:
                    self.exit_application()
                    return
            self.proc_state = ProcState.STOP

    def start_enhancement(self):
        """开始增强过程"""
        # 禁用开始按钮防止重复点击
        self.start_button.config(state="disabled")
        self.step_combo.config(state="disabled")
        self.browse_video_button.config(state="disabled")
        self.browse_video_out_button.config(state="disabled")

        # 在新线程中运行增强过程
        thread = threading.Thread(target=self.enhancement_process)
        thread.daemon = True
        thread.start()


def main():
    root = tk.Tk()
    VideoEnhancerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
