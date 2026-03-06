# -*- coding: utf-8 -*-

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
from moviepy import VideoFileClip
from PIL import Image, ImageTk
from video_setting import VideoSetting

class VideoEnhancerTaskBase:
    def __init__(self, parent):
        self.parent     = parent
        self.setting    = parent.setting
        self.log        = parent.log
        self.dialog     = None
        self.vars       = {}

    def get(self, key, default="", skipSetting=False):
        var = self.vars.get(key)
        if not var:
            if skipSetting:
                var = tk.StringVar(value=default)
            else:
                var = self.setting.get(key, default)
            self.vars[key] = var
        return var

    def create_dialog(self, title, w=800, h=400):
        # 创建顶级窗口 (Toplevel)
        root = self.parent.root
        self.dialog = tk.Toplevel(root)
        self.dialog.title(title)
        self.dialog.resizable(True, True)

        # 2. 设置子窗口大小
        sub_w, sub_h = w, h
        self.dialog.minsize(sub_w, sub_h)    # 设置最小尺寸

        # 3. 获取主窗口位置和大小
        root.update_idletasks() # 确保主窗口位置已更新
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
        
    def create_widgets(self, title):
        self.create_dialog(title)

        # 视频文件选择框
        video_frame = tk.Frame(self.dialog)
        video_frame.pack(fill=tk.X, padx=20, pady=5)
        
        tk.Label(video_frame, text="选择视频文件:").pack(anchor=tk.W)
        
        file_frame = tk.Frame(video_frame)
        file_frame.pack(fill=tk.X, pady=5)
        
        self.video_path_var = self.get(VideoSetting.VideoPath, "", True)
        tk.Entry(file_frame, textvariable=self.video_path_var, state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Button(file_frame, text="浏览", command=self.browse_video).pack(side=tk.RIGHT, padx=(5, 0))
        
        # 视频输出选择框
        video_out_frame = tk.Frame(self.dialog)
        video_out_frame.pack(fill=tk.X, padx=20, pady=5)
        
        tk.Label(video_out_frame, text="选择输出目录:").pack(anchor=tk.W)
        
        file_frame = tk.Frame(video_out_frame)
        file_frame.pack(fill=tk.X, pady=5)
        
        self.video_out_var = self.get(VideoSetting.VideoOut)
        tk.Entry(file_frame, textvariable=self.video_out_var, state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Button(file_frame, text="浏览", command=self.browse_video_out).pack(side=tk.RIGHT, padx=(5, 0))
        
        # 参数设置框
        self.params_frame = tk.LabelFrame(self.dialog, text="执行参数", )
        self.params_frame.pack(fill=tk.X, padx=20, pady=10)    
        
        self.cut_head_sec_var = self.get(VideoSetting.CutHeadSec, "0")
        cut_head_frame = tk.Frame(self.params_frame)
        cut_head_frame.pack(fill=tk.X, padx=10, pady=5)

        secs = []
        for i in range(180):
            secs.append(str(i))

        self.cut_head_label = tk.Label(cut_head_frame, text="裁剪开头N秒:")
        self.cut_head_label.pack(side=tk.LEFT)
        self.cut_head_combo = ttk.Combobox(cut_head_frame, textvariable=self.cut_head_sec_var,
                                   values=secs,
                                   width=25)
        self.cut_head_combo.pack(side=tk.RIGHT)

        cut_tail_frame = tk.Frame(self.params_frame)
        cut_tail_frame.pack(fill=tk.X, padx=10, pady=5)

        self.cut_tail_sec_var = self.get(VideoSetting.CutTailSec, "0")
        self.cut_tail_label = tk.Label(cut_tail_frame, text="裁剪结尾N秒:")
        self.cut_tail_label.pack(side=tk.LEFT)
        self.cut_tail_combo = ttk.Combobox(cut_tail_frame, textvariable=self.cut_tail_sec_var,
                                   values=secs,
                                   width=25)
        self.cut_tail_combo.pack(side=tk.RIGHT)
        
        # --- 工具提示窗口 (Toplevel) ---
        # 不要将它 pack() 或 grid() 到任何地方
        self.tooltip_video_cap = tk.Toplevel(self.dialog)
        self.tooltip_video_cap.withdraw() # 初始隐藏
        self.tooltip_video_cap.overrideredirect(True) # 移除窗口边框
        
        # 为工具提示窗口添加一个 Label 来显示图片
        self.img_video_cap_label = tk.Label(self.tooltip_video_cap, bg='white', bd=1, relief='solid')
        self.img_video_cap_label.pack()
        
        # --- 绑定事件 ---
        self.cut_head_label.bind("<Enter>", self.on_enter_cut_head_label)
        self.cut_head_label.bind("<Leave>", self.on_leave_cut_head_label)
        self.cut_tail_label.bind("<Enter>", self.on_enter_cut_tail_label)
        self.cut_tail_label.bind("<Leave>", self.on_leave_cut_tail_label)
        # 确保鼠标离开图片窗口时也隐藏它
        self.tooltip_video_cap.bind("<Leave>", self.on_leave_tooltip_video_cap)
        self.entering_label = None
        self.img_video_cap = None


    def on_enter_cut_head_label(self, *args):
        """鼠标进入按钮时的处理函数"""

        path = self.video_path_var.get()
        if not os.path.isfile(path):
            return
        
        sec = float(self.cut_head_sec_var.get())
        if sec <= 0:
            return
        
        basename = os.path.basename(path)
        output_image_path = os.path.join(self.parent.dir_capture, f"{basename}_head_{sec}.png")
        self.capture_frame(path, output_image_path, sec)
        if not os.path.isfile(output_image_path):
            return
        
        # 获取鼠标指针的屏幕坐标
        x = self.dialog.winfo_pointerx() + 10
        y = self.dialog.winfo_pointery() + 10
        # 定位并显示工具提示窗口
        self.tooltip_video_cap.geometry(f"+{x}+{y}")
        self.tooltip_video_cap.deiconify() # 显示窗口
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
        output_image_path = os.path.join(self.parent.dir_capture, f"{basename}_tail_{sec}.png")
        self.capture_frame(path, output_image_path, -sec)
        if not os.path.isfile(output_image_path):
            return
        
        # 获取鼠标指针的屏幕坐标
        x = self.dialog.winfo_pointerx() + 10
        y = self.dialog.winfo_pointery() + 10
        # 定位并显示工具提示窗口
        self.tooltip_video_cap.geometry(f"+{x}+{y}")
        self.tooltip_video_cap.deiconify() # 显示窗口
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
        under_mouse_id = self.dialog.winfo_containing(
            self.dialog.winfo_pointerx(), 
            self.dialog.winfo_pointery()
        )
        
        # 获取主按钮和图片窗口的顶层窗口widget
        label_toplevel = self.entering_label.winfo_toplevel()
        tooltip_toplevel = self.tooltip_video_cap

        # 如果鼠标不在按钮或图片窗口上，则隐藏
        if (under_mouse_id != self.entering_label and 
            under_mouse_id != label_toplevel and
            under_mouse_id != tooltip_toplevel):
            self.tooltip_video_cap.withdraw()
            self.entering_label = None

    def on_leave_tooltip_video_cap(self, *args):
        """鼠标离开工具提示窗口时的处理函数"""
        self.tooltip_video_cap.withdraw() # 直接隐藏

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
            self.log(f"正在加载视频: {video_path}")
            video_clip = VideoFileClip(video_path)

            # 获取视频总时长
            total_duration = video_clip.duration
            self.log(f"视频总时长: {total_duration:.2f} 秒")

            if time_in_seconds < 0:
                time_in_seconds = time_in_seconds + total_duration

            # 检查时间点是否有效
            if time_in_seconds < 0 or time_in_seconds > total_duration:
                raise ValueError(f"指定的时间点 ({time_in_seconds}s) 超出了视频范围 (0 - {total_duration:.2f}s)。")

            # 2. 提取指定时间点的帧
            self.log(f"正在截取第 {time_in_seconds}s 处的画面...")
            frame_image = video_clip.get_frame(time_in_seconds)

            # 3. 将帧保存为图片
            # moviepy 使用的是 PIL/Pillow 库，所以我们可以直接用它保存
            result_image = Image.fromarray(frame_image)
            
            # 确保输出目录存在
            output_dir = os.path.dirname(output_image_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            result_image.save(output_image_path)
            self.log(f"截图已成功保存到: {output_image_path}")

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
            self.log("错误: 未找到 'PIL' 或 'Pillow' 库。请运行 'pip install Pillow' 安装。")
        except Exception as e:
            self.log(f"发生了一个意外错误: {e}")

    def browse_video(self):
        """浏览选择视频文件"""
        file_path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[
                ("视频文件", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm"),
                ("所有文件", "*.*")
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

class VideoEnhancerTaskCreate(VideoEnhancerTaskBase):
    def __init__(self, parent):
        VideoEnhancerTaskBase.__init__(self, parent)
        self.create_widgets()
        
    def create_widgets(self):
        VideoEnhancerTaskBase.create_widgets(self, "创建任务")
        
        # 控制按钮
        button_frame = tk.Frame(self.dialog)
        button_frame.pack(pady=20)

        save_button = tk.Button(button_frame, text="创建", command=self.on_click_create, 
                                     bg="#4CAF50", fg="white", font=("Arial", 10, "bold"),
                                     padx=20)
        save_button.pack(side=tk.LEFT, padx=10)
        
        cancel_button = tk.Button(button_frame, text="取消", command=self.dialog.destroy, 
                                     bg="#f44336", fg="white", font=("Arial", 10, "bold"),
                                     padx=20)
        cancel_button.pack(side=tk.LEFT, padx=10)


    def on_click_create(self):
        task = {
            VideoSetting.VideoPath  : self.video_path_var.get(),
            VideoSetting.VideoOut   : self.video_out_var.get(),
            VideoSetting.CutHeadSec : self.cut_head_sec_var.get(),
            VideoSetting.CutTailSec : self.cut_tail_sec_var.get(),
        }
        self.setting.set_task(task)
        self.setting.save()
        self.dialog.destroy()
        self.parent.rfsh_tasks()

class VideoEnhancerTaskSetting(VideoEnhancerTaskBase):
    def __init__(self, parent, task):
        VideoEnhancerTaskBase.__init__(self, parent)
        self.create_widgets()

        for key, val in task.items():
            var = self.get(key)
            var.set(val)
        
    def create_widgets(self):
        VideoEnhancerTaskBase.create_widgets(self, "修改任务")
        
        # 控制按钮
        button_frame = tk.Frame(self.dialog)
        button_frame.pack(pady=20)

        save_button = tk.Button(button_frame, text="保存", command=self.on_click_save, 
                                     bg="#4CAF50", fg="white", font=("Arial", 10, "bold"),
                                     padx=20)
        save_button.pack(side=tk.LEFT, padx=10)
        
        cancel_button = tk.Button(button_frame, text="取消", command=self.dialog.destroy, 
                                     bg="#f44336", fg="white", font=("Arial", 10, "bold"),
                                     padx=20)
        cancel_button.pack(side=tk.LEFT, padx=10)


    def on_click_save(self):
        task = {
            VideoSetting.VideoPath  : self.video_path_var.get(),
            VideoSetting.VideoOut   : self.video_out_var.get(),
            VideoSetting.CutHeadSec : self.cut_head_sec_var.get(),
            VideoSetting.CutTailSec : self.cut_tail_sec_var.get(),
        }
        self.setting.set_task(task)
        self.setting.save()
        self.dialog.destroy()
        self.parent.rfsh_tasks()