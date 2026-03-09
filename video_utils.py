# -*- coding: utf-8 -*-

import sys, datetime

sys_stdout = sys.stdout
sys_stderr = sys.stderr

class TeeTerminal:
    def __init__(self, terminal, fn_write):
        self.terminal = terminal
        self.fn_write = fn_write

    def write(self, msg):
        msg.strip()
        if msg == "":
            return
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.terminal.write(f"[{timestamp}] {msg}\n")
        self.fn_write(msg)

    def flush(self):
        # flush 方法也需要定义，确保缓冲区内容被立即处理
        self.terminal.flush()

# fn_write = function(msg)
def redirect_std_err(fn_write):
    global sys_stderr
    sys.stderr = TeeTerminal(sys_stderr, fn_write)

# fn_write = function(msg)
def redirect_std_out(fn_write):
    global sys_stdout
    sys.stdout = TeeTerminal(sys_stdout, fn_write)
    