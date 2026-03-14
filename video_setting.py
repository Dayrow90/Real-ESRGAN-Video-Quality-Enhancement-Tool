# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk
import enum
from video_config import ConfigManager
from functools import cmp_to_key


class StrEnum(enum.StrEnum):

    @classmethod
    def from_value(cls, value):
        for _, v in enumerate(cls):
            if value == v.value:
                return v.name
        return ""

    @classmethod
    def values(cls):
        rs = []
        for _, v in enumerate(cls):
            rs.append(v)
        return rs


class ProcStepDesc(StrEnum):
    ALL = "裁剪视频 -> 提取帧 -> 增强帧 -> 合并帧"
    CUT = "裁剪视频"
    EXTRACT = "提取帧"
    ENHANCE = "增强帧"
    MERGE = "合并帧"
    COMPRESS = "压缩视频"


class ProcStep(StrEnum):
    ALL = "all"
    CUT = "cut"
    EXTRACT = "extract"
    ENHANCE = "enhance"
    MERGE = "merge"
    COMPRESS = "compress"

    @classmethod
    def desc(cls, value):
        for v in ProcStep:
            if v.value == value:
                return ProcStepDesc[v.name]
        return value

    @classmethod
    def values(cls):
        return [
            ProcStep.ALL,  # 裁剪视频 -> 提取帧 -> 增强帧 -> 合并帧
            ProcStep.CUT,  # 裁剪视频
            ProcStep.EXTRACT,  # 提取帧
            ProcStep.ENHANCE,  # 增强帧
            ProcStep.MERGE,  # 合并帧
            ProcStep.COMPRESS,  # 压缩视频
        ]


class ProcDone(StrEnum):
    NEXT = "auto"
    STOP = "stop"
    EXIT = "exit"

    @classmethod
    def values(cls):
        return [
            ProcDone.STOP,
            ProcDone.NEXT,
            ProcDone.EXIT,
        ]


class ProcModelDesc(StrEnum):
    ANIME_V3 = "通用动漫视频增强模型"
    X4PLUS = "通用视频增强模型，适用于各种类型的视频"
    X4PLUS_ANIME = "专门针对动漫图像优化的增强模型"


class ProcModel(StrEnum):
    ANIME_V3 = "realesr-animevideov3"
    X4PLUS = "realesrgan-x4plus"
    X4PLUS_ANIME = "realesrgan-x4plus-anime"

    @classmethod
    def desc(cls, value):
        for v in ProcModel:
            if v.value == value:
                return ProcModelDesc[v.name]
        return value

    @classmethod
    def values(cls):
        return [
            ProcModel.ANIME_V3,
            ProcModel.X4PLUS,
            ProcModel.X4PLUS_ANIME,
        ]


"""
-b:v
| 分辨率            |   帧率 (fps)  | 推荐 `-b:v` (H.264)   | 推荐 `-b:v` (H.265/HEVC)  | 适用场景          |
| :---              |   :---        | :---                  | :---                      | :---             |
| 720p (1280x720)   |   30          | 2.5 ~ 4 Mbps          | 1.5 ~ 2.5 Mbps            | 手机观看/弱网     |
| 720p              |   60          | 3.5 ~ 5 Mbps          | 2.5 ~ 3.5 Mbps            | 流畅游戏录屏      |
| 1080p (1920x1080) |   30          | 4 ~ 6 Mbps            | 3 ~ 4.5 Mbps              | B站/YouTube 标准  |
| 1080p             |   60          | 6 ~ 9 Mbps            | 4.5 ~ 6 Mbps              | 高帧率游戏/体育    |
| 2K (2560x1440)    |   30/60       | 10 ~ 15 Mbps          | 6 ~ 10 Mbps               | 高清显示器        |
| 4K (3840x2160)    |   30          | 20 ~ 25 Mbps          | 12 ~ 18 Mbps              | 电视/大屏         |
| 4K                |   60          | 35 ~ 45 Mbps          | 20 ~ 30 Mbps              | 极致画质/蓝光压制  |

"""

"""
-cq / -crf
值越小 画质越好 压缩越小 文件越大
值越大 画质越差 压缩更多 文件越小
| 数值范围  | 画质描述                          | 文件大小              | 适用场景 |
| :---      | :---                             | :---                 | :--- |
| 0 - 10    | 视觉无损 / 近无损                 | 极大 (接近原始素材)    | 专业归档、后期制作中间片、极度强迫症 |
| 11 - 15   | 极高画质                          | 很大                  | 蓝光原盘压制、收藏级视频 |
| 16 - 18   | 视觉无损 (Visually Lossless)      | 大                    | 高质量存档推荐值。肉眼几乎看不出与原片的区别。 |
| 19 - 23   | 优秀画质 (Standard High)          | 适中                  | 网络分发推荐值。B站、YouTube 上传的首选区间，画质好且体积合理。 |
| 24 - 28   | 良好画质 (Good)                   | 较小                  | 手机观看、硬盘空间紧张时的折中方案。仔细看能发现轻微噪点或模糊。 |
| 29 - 35   | 一般画质 (Acceptable)             | 小                    | 快速预览、低带宽流媒体、老旧设备播放。 |
| 36 - 51   | 差 / 块状严重                     | 极小                  | 仅用于测试或极端受限环境，通常不可用。 |
"""


def VideoQualityDesc(value):
    value = int(value)
    if value <= 10:
        return "近无损/文件极大 (接近原始素材)"
    elif value <= 15:
        return "极高画质/文件很大"
    elif value <= 18:
        return "视觉无损/文件大"
    elif value <= 23:
        return "优秀画质/文件适中"
    elif value <= 28:
        return "良好画质/文件较小"
    elif value <= 35:
        return "一般画质/文件小"
    return "画质差/文件极小"


"""
| 等级 | 速度 | 压缩效率 (文件大小) | CPU 占用 | 适用场景 |
| :--- | :--- | :--- | :--- | :--- |
| ultrafast | ⚡️ 极快 | ❌ 最差 (文件巨大) | 低 | 直播推流 (必须)、实时录屏 (防止卡顿) |
| superfast | 🚀 很快 | ❌ 差 | 低 | 对时间极度敏感的任务 |
| veryfast | ⚡ 快 | ⚠️ 较差 | 中低 | NVENC 硬件编码的默认值、快速预览 |
| faster | 🏃 较快 | 😐 一般 | 中 | 日常快速转码 |
| fast | 🚶 快 | 😐 一般 | 中 | |
| medium | 🐢 中等 | ✅ 平衡点 | 中高 | x264 的默认值。大多数人的最佳选择。 |
| slow | 🐌 慢 | ✅ 好 | 高 | 追求高压缩率的首选。存档、发布视频。 |
| slower | 🦥 很慢 | ✅ 很好 | 很高 | 极致压缩，时间充裕时使用。 |
| veryslow | 🪨 极慢 | ✅ 极好 | 极高 | 只有当你需要节省每一 MB 空间时才用。 |
| placebo | 💀 龟速 | ➖ 微乎其微的提升 | 爆表 | 不推荐。花费数倍时间，体积仅减少 1-2%，画质肉眼不可见区别。 |

"""


def VideoQualityValues():
    rs = []
    for i in range(52):
        rs.append(str(i))
    rs[0] = ""
    return rs


class VideoEncoderDesc(StrEnum):
    Libx264 = "H.264/CPU"
    Libx265 = "H.265/CPU"
    Nv264 = "H.264/GPU"
    Nv265 = "H.265/GPU"


class VideoEncoder(StrEnum):
    Libx264 = "libx264"
    Libx265 = "libx265"
    Nv264 = "h264_nvenc"
    Nv265 = "hevc_nvenc"

    def is_cpu(self):
        if self.value in [VideoEncoder.Libx264, VideoEncoder.Libx265]:
            return True
        return False

    @classmethod
    def quality_args_name(cls, value):
        name = cls.from_value(value)
        elem = cls[name]
        if elem.is_cpu():
            return "-crf"
        return "-cq"

    @classmethod
    def desc(cls, value):
        for v in cls:
            if v.value == value:
                return VideoEncoderDesc[v.name]
        return value


class VideoSettingDefault(StrEnum):
    VideoPath = ""
    VideoOut = ""
    Model = ProcModel.ANIME_V3
    Scale = "4"
    Format = "png"
    Level = "5.1"
    TileSize = "512"
    ThreadCount = "6:12:16"
    BitRate = ""
    MaxRate = ""
    CutHeadSec = "0"
    CutTailSec = "0"
    FpsForce = "0"
    ProcStep = ProcStep.ALL
    ProcDone = ProcDone.NEXT
    Quality = "18"
    Encoder = VideoEncoder.Nv265
    Preset = "medium"


VideoSettingValues = {}


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
    ProcStep = "proc_step"
    ProcDone = "proc_done"
    Quality = "quality"
    Encoder = "enc"
    Preset = "preset"

    @classmethod
    def from_value(cls, value):
        for v in VideoSetting:
            if v.value == value:
                return v.name
        return value

    @classmethod
    def default(cls, value):
        for v in VideoSetting:
            if v.value == value:
                return VideoSettingDefault[v.name]
        return ""

    def values(self):
        global VideoSettingValues
        return VideoSettingValues.get(self.value, [])


def ThreadCountValues():
    rs = [""]
    cores = ["2", "4", "6", "8", "10", "12", "14", "16"]
    for _, load in enumerate(cores):
        for _, proc in enumerate(cores):
            for _, save in enumerate(cores):
                rs.append(f"{load}:{proc}:{save}")
    return rs


def CutSecsValues():
    rs = []
    for i in range(300):
        rs.append(str(i))
    return rs


VideoSettingValues = {
    VideoSetting.VideoPath: [],
    VideoSetting.VideoOut: [],
    VideoSetting.Model: ProcModel.values(),
    VideoSetting.Scale: ["2", "3", "4"],
    VideoSetting.Format: ["jpg", "png"],
    VideoSetting.Level: [
        "1.0",
        "1.1",
        "1.2",
        "1.3",
        "2.0",
        "2.1",
        "2.2",
        "3.0",
        "3.1",
        "3.2",
        "4.0",
        "4.1",
        "4.2",
        "5.0",
        "5.1",
        "5.2",
    ],
    VideoSetting.TileSize: [
        "",
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
    VideoSetting.ThreadCount: ThreadCountValues(),
    VideoSetting.BitRate: [
        "5M",
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
        "85M",
        "90M",
        "95M",
    ],
    VideoSetting.MaxRate: [
        "5M",
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
        "85M",
        "90M",
        "95M",
    ],
    VideoSetting.CutHeadSec: CutSecsValues(),
    VideoSetting.CutTailSec: CutSecsValues(),
    VideoSetting.FpsForce: [],
    VideoSetting.ProcStep: ProcStep.values(),
    VideoSetting.ProcDone: ProcDone.values(),
    VideoSetting.Encoder: VideoEncoder.values(),
    VideoSetting.Quality: VideoQualityValues(),
}


class VideoEnhancerSetting:
    def __init__(self, db_path):
        self.db = ConfigManager(db_path)
        self.vars = {}
        self.tasks = self.db.list_all_task()
        self.sort_tasks()
        self.showing = False

    def gen_var(self, name, default=None):
        var = self.vars.get(name)
        if var is None:
            if default is None:
                default = VideoSetting.default(name)

            value = self.db.get(name, default)
            if value != default:
                values = VideoSettingValues.get(name) or []
                if len(values) > 0 and value not in values:
                    value = default

            var = self.new_var(value)
            self.vars[name] = var
        return var

    def new_var(self, default=""):
        cls = tk.StringVar
        if isinstance(default, (int, float)):
            cls = tk.DoubleVar
        return cls(value=default)

    def get(self, name, default=None):
        return self.gen_var(name, default).get()

    def save(self):
        for name, var in self.vars.items():
            self.db.set(name, var.get())

    def showUI(self, root):
        if self.showing:
            return

        self.create_widgets(root)
        self.dialog.deiconify()

        # 可选：将窗口居中显示
        self.dialog.lift()  # 将窗口置于所有窗口之上
        self.dialog.focus_set()  # 再次确保焦点设置
        self.showing = True

    def closeUI(self, *args):
        if self.showing:
            self.dialog.destroy()
            self.showing = False

    def save_close(self):
        self.save()
        self.closeUI()

    def create_widgets(self, root):
        # 创建顶级窗口 (Toplevel)
        self.dialog = tk.Toplevel(root)
        self.dialog.title("设置")
        self.dialog.resizable(True, True)

        # 绑定 <Escape> 事件到子窗口
        # 当在这个子窗口上按下 Esc 键时，会调用 close_window 函数
        self.dialog.bind("<Escape>", self.closeUI)
        self.dialog.protocol("WM_DELETE_WINDOW", self.closeUI)  # 监听窗口关闭事件

        # 2. 设置子窗口大小
        sub_w, sub_h = 800, 500
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

        self.model_var = self.gen_var(VideoSetting.Model, ProcModel.ANIME_V3)
        self.model_combo = ttk.Combobox(
            model_frame,
            textvariable=self.model_var,
            values=ProcModel.values(),
            state="readonly",
            width=25,
        )
        self.model_combo.pack(side=tk.RIGHT)

        # 模型用途说明
        self.model_description_label = tk.Label(
            model_frame,
            text="",
            font=("Arial", 8),
            fg="gray",
            wraplength=700,
            justify="left",
        )
        self.model_description_label.pack(anchor=tk.W, side=tk.RIGHT)

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

        # 绑定模型选择事件
        self.model_var.trace("w", self.on_model_change)
        self.on_model_change()

        # thread count for load/proc/save
        thread_count_frame = tk.Frame(self.params_frame)
        thread_count_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(thread_count_frame, text="thread count for load/proc/save:").pack(
            side=tk.LEFT
        )

        self.thread_count_var = self.gen_var(VideoSetting.ThreadCount)
        self.thread_count_combo = ttk.Combobox(
            thread_count_frame,
            textvariable=self.thread_count_var,
            values=VideoSetting.ThreadCount.values(),
            state="readonly",
            width=25,
        )
        self.thread_count_combo.pack(side=tk.RIGHT)

        # 输出格式
        format_frame = tk.Frame(self.params_frame)
        format_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(format_frame, text="输出格式:").pack(side=tk.LEFT)

        self.format_var = self.gen_var(VideoSetting.Format)
        self.format_combo = ttk.Combobox(
            format_frame,
            textvariable=self.format_var,
            values=VideoSetting.Format.values(),
            state="readonly",
            width=25,
        )
        self.format_combo.pack(side=tk.RIGHT)

        # tile-size
        tile_size_frame = tk.Frame(self.params_frame)
        tile_size_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(tile_size_frame, text="tile-size:").pack(side=tk.LEFT)

        self.tile_size_var = self.gen_var(VideoSetting.TileSize)
        self.tile_size_combo = ttk.Combobox(
            tile_size_frame,
            textvariable=self.tile_size_var,
            values=VideoSetting.TileSize.values(),
            state="readonly",
            width=25,
        )
        self.tile_size_combo.pack(side=tk.RIGHT)

        # 编码器
        encoder_frame = tk.Frame(self.params_frame)
        encoder_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(encoder_frame, text="编码器:").pack(side=tk.LEFT)

        self.encoder_var = self.gen_var(VideoSetting.Encoder)
        self.encoder_combo = ttk.Combobox(
            encoder_frame,
            textvariable=self.encoder_var,
            values=VideoEncoder.values(),
            state="readonly",
            width=25,
        )
        self.encoder_combo.pack(side=tk.RIGHT)

        # 编码器说明
        self.encoder_description_label = tk.Label(
            encoder_frame,
            text="",
            font=("Arial", 8),
            fg="gray",
            wraplength=700,
            justify="left",
        )
        self.encoder_description_label.pack(anchor=tk.W, side=tk.RIGHT)

        # 绑定encoder选择事件
        self.encoder_var.trace("w", self.on_encoder_change)
        self.on_encoder_change()

        # 视频质量
        quality_frame = tk.Frame(self.params_frame)
        quality_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(quality_frame, text="视频质量:").pack(side=tk.LEFT)

        self.quality_var = self.gen_var(VideoSetting.Quality)
        self.quality_combo = ttk.Combobox(
            quality_frame,
            textvariable=self.quality_var,
            values=VideoQualityValues(),
            state="readonly",
            width=25,
        )
        self.quality_combo.pack(side=tk.RIGHT)

        # 视频质量说明
        self.quality_description_label = tk.Label(
            quality_frame,
            text="",
            font=("Arial", 8),
            fg="gray",
            wraplength=700,
            justify="left",
        )
        self.quality_description_label.pack(anchor=tk.W, side=tk.RIGHT)

        # 绑定quality选择事件
        self.quality_var.trace("w", self.on_quality_change)
        self.on_quality_change()

        # b:v
        bit_rate_frame = tk.Frame(self.params_frame)
        bit_rate_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(bit_rate_frame, text="b:v").pack(side=tk.LEFT)

        self.bit_rate_var = self.gen_var(VideoSetting.BitRate)
        self.bit_rate_combo = ttk.Combobox(
            bit_rate_frame,
            textvariable=self.bit_rate_var,
            values=VideoSetting.BitRate.values(),
            state="readonly",
            width=25,
        )
        self.bit_rate_combo.pack(side=tk.RIGHT)

        # max rate
        max_rate_frame = tk.Frame(self.params_frame)
        max_rate_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(max_rate_frame, text="max rate").pack(side=tk.LEFT)

        self.max_rate_var = self.gen_var(VideoSetting.MaxRate)
        self.max_rate_combo = ttk.Combobox(
            max_rate_frame,
            textvariable=self.max_rate_var,
            values=VideoSetting.MaxRate.values(),
            state="readonly",
            width=25,
        )
        self.max_rate_combo.pack(side=tk.RIGHT)

        # 强制fps
        fps_force_frame = tk.Frame(self.params_frame)
        fps_force_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(fps_force_frame, text="fps force:").pack(side=tk.LEFT)

        self.fps_force_var = self.gen_var(VideoSetting.FpsForce)
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
        if not self.showing:
            return

        selected_model = self.model_var.get()
        self.model_description_label.config(text=ProcModel.desc(selected_model))

        if selected_model in [ProcModel.X4PLUS, ProcModel.X4PLUS_ANIME]:
            # 固定缩放因子为4
            self.scale_var.set("4")
            # 禁用缩放因子选择
            self.scale_combo.config(state="disabled")
        else:
            # 启用缩放因子选择
            self.scale_combo.config(state="readonly")

    def on_encoder_change(self, *args):
        """当编码器选择改变时的处理函数"""
        encoder = self.encoder_var.get()
        text = VideoEncoder.desc(encoder)
        self.encoder_description_label.config(text=text)

    def on_quality_change(self, *args):
        """当视频质量选择改变时的处理函数"""
        quality = self.quality_var.get()
        text = VideoQualityDesc(quality)
        self.quality_description_label.config(text=text)

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
        for _, v in enumerate(self.tasks):
            if v.get("pos") is None:
                v["pos"] = 0
                self.db.set_task(v[VideoSetting.VideoPath], v)

        def cmp(v1, v2):
            if v1["pos"] != v2["pos"]:
                return v1["pos"] > v2["pos"]
            return v1[VideoSetting.VideoPath] > v2[VideoSetting.VideoPath]

        sorted(self.tasks, key=cmp_to_key(cmp))

    def fix_task_pos(self):
        for idx, v in enumerate(self.tasks):
            if v.get("pos") != idx:
                v["pos"] = idx
                self.db.set_task(v[VideoSetting.VideoPath], v)

    def save_tasks(self):
        for _, v in enumerate(self.tasks):
            video_path = v[VideoSetting.VideoPath]
            self.db.set_task(video_path, v)
