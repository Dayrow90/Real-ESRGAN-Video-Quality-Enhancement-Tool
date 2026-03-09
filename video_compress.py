# -*- coding: utf-8 -*-

import os
import subprocess


def to_h265(input_path, output_path, crf=22, preset="medium", use_gpu=False):
    if not os.path.isfile(input_path):
        print(f"input_path not exist: {input_path}")
        return False

    if os.path.isdir(output_path):
        file_name = os.path.basename(input_path)
        output_path = os.path.join(output_path, file_name)

    if os.path.isfile(output_path):
        print(f"output_path already exist: {output_path}")
        return False

    # 构建 FFmpeg 命令
    # 基础命令
    cmd = ["ffmpeg", "-i", input_path]

    # 视频编码部分
    if use_gpu:
        # 尝试使用 NVIDIA NVENC H.265 编码器
        # 注意：GPU编码通常比CPU同预设下体积稍大，但速度快几十倍
        cmd.extend(
            [
                "-c:v",
                "hevc_nvenc",
                "-cq",
                str(crf),  # NVENC 使用 CQ (Constant Quality) 对应 CRF
                "-preset",
                preset,
            ]
        )
        print("💡 检测到启用 GPU 加速 (NVIDIA NVENC)...")
    else:
        # 使用 CPU x265 编码器 (压缩率通常优于同速度的GPU)
        cmd.extend(
            [
                "-c:v",
                "libx265",
                "-crf",
                str(crf),
                "-preset",
                preset,
                "-tag:v",
                "hvc1",  # 兼容 macOS QuickTime 播放
            ]
        )
        print("💡 使用 CPU 编码 (libx265)...")

    # 音频编码部分 (转换为 AAC，128k 对于大多数情况足够，也可设为 192k)
    cmd.extend(["-c:a", "aac", "-b:a", "128k"])

    # 其他优化
    cmd.extend(
        [
            "-movflags",
            "+faststart",  # 允许视频在未完全下载时开始播放
            "-y",  # 覆盖输出文件
            output_path,
        ]
    )

    try:
        print(" ".join(cmd))

        # 执行命令
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        _, stderr = process.communicate()
        if process.returncode != 0:
            print(
                f"压缩视频失败(code:{process.returncode}): {stderr.decode('utf-8', errors='ignore')}"
            )
            return False
        elif not os.path.exists(output_path):
            # 简单的成功判断
            print("❌ 压缩过程似乎已完成但未生成文件。")
            return False

        original_size = os.path.getsize(input_path) / (1024 * 1024)
        compressed_size = os.path.getsize(output_path) / (1024 * 1024)
        ratio = (1 - compressed_size / original_size) * 100

        print("=" * 40)
        print("✅ 压缩完成!")
        print(f"📂 原始大小: {original_size:.2f} MB")
        print(f"📦 压缩后: {compressed_size:.2f} MB")
        print(f"📉 体积减少: {ratio:.1f}%")
        print(f"💾 保存位置: {output_path}")
        print("=" * 40)
        return True

    except subprocess.CalledProcessError as e:
        print("❌ 压缩失败! 错误信息:")
        print(e.stderr)
        return False
    except Exception as e:
        print(f"❌ 发生未知错误: {str(e)}")
        return False
