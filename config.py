# -*- coding: utf-8 -*-
import sqlite3
import json
import os
from contextlib import contextmanager

class ConfigManager:
    """
    一个使用 SQLite 数据库来管理配置的类。
    配置以键值对的形式存储，值可以是任意支持 JSON 序列化的 Python 对象。
    """

    def __init__(self, db_path="app_config.db"):
        """
        初始化配置管理器。

        Args:
            db_path (str): SQLite 数据库文件的路径。默认为 'app_config.db'。
        """
        self.db_path = db_path
        # 在初始化时就创建数据表（如果不存在）
        self._create_table()

    @contextmanager
    def get_db_connection(self):
        """
        提供一个数据库连接的上下文管理器，在操作完成后自动关闭连接。
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 这样可以通过列名访问结果
        try:
            yield conn
        finally:
            conn.close()

    def _create_table(self):
        """
        创建用于存储配置的表。
        """
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            ''')
            conn.commit()

    def set(self, key: str, value):
        """
        设置一个配置项。

        Args:
            key (str): 配置项的键。
            value: 配置项的值，可以是字符串、数字、列表或字典等。
        """
        serialized_value = json.dumps(value)
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                (key, serialized_value)
            )
            conn.commit()

    def get(self, key: str, default=None):
        """
        获取一个配置项的值。

        Args:
            key (str): 配置项的键。
            default: 如果键不存在，则返回此默认值。

        Returns:
            配置项的值，或默认值。
        """
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                # 使用 json.loads 将存储的 JSON 字符串反序列化回 Python 对象
                return json.loads(row['value'])
            else:
                return default

    def delete(self, key: str):
        """
        删除一个配置项。

        Args:
            key (str): 要删除的配置项的键。
        """
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM config WHERE key = ?", (key,))
            conn.commit()

    def list_all(self):
        """
        列出所有配置项。

        Returns:
            一个包含所有 (key, value) 元组的列表。
        """
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM config")
            rows = cursor.fetchall()
            # 反序列化所有值
            return [(row['key'], json.loads(row['value'])) for row in rows]