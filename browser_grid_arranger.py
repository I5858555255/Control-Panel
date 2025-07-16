# browser_grid_arranger.py

import tkinter as tk
import pygetwindow as gw
import math
import win32api, win32con, win32gui
import os
import subprocess
import time
import logging

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename='log.txt',
        filemode='a'
    )
    logging.info("--- Application Started ---")

def find_chrome_executable():
    logging.info("Attempting to find Chrome executable.")
    """查找 Google Chrome 可执行文件的绝对路径。"""
    possible_paths = [
        r"C:\Users\Administrator\AppData\Local\Google\Chrome\Bin\chrome.exe",
        os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Google\\Chrome\\Application\\chrome.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Google\\Chrome\\Application\\chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google\\Chrome\\Application\\chrome.exe"),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            logging.info(f"Found Chrome executable at: {path}")
            return path
    logging.warning("Chrome executable not found.")
    return None

class BrowserGridArrangerApp:
    def __init__(self, master):
        setup_logging()
        self.master = master
        master.title("浏览器网格排列工具")

        self.browser_windows = {}
        self.selected_windows = {}
        self.opened_windows_by_script = [] # 用于追踪由脚本打开的窗口

        self.frame = tk.Frame(master)
        self.frame.pack(padx=10, pady=10)

        # --- 功能按钮 ---
        self.open_urls_button = tk.Button(self.frame, text="一键打开所有网址", command=self.open_urls_from_file)
        self.open_urls_button.pack(pady=5)

        self.close_opened_button = tk.Button(self.frame, text="一键关闭所有已打开窗口", command=self.close_opened_windows)
        self.close_opened_button.pack(pady=5)
        # --- 结束 ---

        self.refresh_button = tk.Button(self.frame, text="刷新窗口列表", command=self.refresh_windows)
        self.refresh_button.pack(pady=5)

        self.arrange_button = tk.Button(self.frame, text="排列选中的窗口", command=self.arrange_windows)
        self.arrange_button.pack(pady=5)

        self.window_list_frame = tk.LabelFrame(self.frame, text="检测到的浏览器窗口")
        self.window_list_frame.pack(pady=10, fill="both", expand=True)

        self.refresh_windows()

    def open_urls_from_file(self):
        logging.info("open_urls_from_file called.")
        chrome_path = find_chrome_executable()
        if not chrome_path:
            logging.error("错误：未找到 Google Chrome 浏览器。请检查安装路径。")
            print("错误：未找到 Google Chrome 浏览器。请检查安装路径。")
            return

        script_dir = os.path.dirname(os.path.abspath(__file__))
        url_file_path = os.path.join(script_dir, 'itemurl.txt')
        logging.info(f"Looking for URL file at: {url_file_path}")

        if not os.path.exists(url_file_path):
            logging.error(f"错误：URL 文件未找到，路径：{url_file_path}")
            print(f"错误：URL 文件未找到，路径：{url_file_path}")
            return

        with open(url_file_path, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        logging.info(f"Found {len(urls)} URLs in itemurl.txt.")

        if not urls:
            logging.info("信息：itemurl.txt 文件为空，没有要打开的 URL。")
            print("信息：itemurl.txt 文件为空，没有要打开的 URL。")
            return

        browser_titles = ["Chrome", "Firefox", "Edge", "Brave", "Opera", "谷歌浏览器"]
        all_windows_before = {win._hWnd for win in gw.getAllWindows() if win.title and any(b in win.title for b in browser_titles)}

        logging.info(f"正在打开 {len(urls)} 个网址...")
        print(f"正在打开 {len(urls)} 个网址...")
        for url in urls:
            try:
                logging.info(f"Opening URL: {url}")
                subprocess.Popen([chrome_path, url, "--new-window"])
            except Exception as e:
                logging.error(f"打开 URL 时出错 ({url}): {e}")
                print(f"打开 URL 时出错 ({url}): {e}")

        logging.info("正在等待新窗口加载...")
        print("正在等待新窗口加载...")
        start_time = time.time()
        timeout = 30
        newly_opened_handles = set()
        while time.time() - start_time < timeout:
            all_windows_after = gw.getAllWindows()
            current_handles = {win._hWnd for win in all_windows_after if win.title and any(b in win.title for b in browser_titles)}
            newly_opened_handles = current_handles - all_windows_before
            if len(newly_opened_handles) >= len(urls):
                break
            time.sleep(0.5)
        
        self.opened_windows_by_script = [win for win in gw.getAllWindows() if win._hWnd in newly_opened_handles]
        logging.info(f"已识别 {len(self.opened_windows_by_script)} 个新窗口。")
        print(f"已识别 {len(self.opened_windows_by_script)} 个新窗口。")
        self.refresh_windows()

    def close_opened_windows(self):
        logging.info("close_opened_windows called.")
        if not self.opened_windows_by_script:
            logging.info("没有由脚本打开的窗口可供关闭。")
            print("没有由脚本打开的窗口可供关闭。")
            return

        logging.info(f"正在关闭 {len(self.opened_windows_by_script)} 个窗口...")
        print(f"正在关闭 {len(self.opened_windows_by_script)} 个窗口...")
        for window in list(self.opened_windows_by_script):
            try:
                logging.info(f"Closing window: {window.title}")
                window.close()
            except Exception as e:
                logging.error(f"关闭窗口 '{window.title}' 时出错: {e}")
                print(f"关闭窗口 '{window.title}' 时出错: {e}")
        
        self.opened_windows_by_script = []
        logging.info("所有由脚本打开的窗口已关闭。正在刷新列表...")
        print("所有由脚本打开的窗口已关闭。正在刷新列表...")
        time.sleep(1)
        self.refresh_windows()

    def refresh_windows(self):
        logging.info("refresh_windows called.")
        """（可靠版）清空并重新检测所有窗口，默认全部选中。"""
        for widget in self.window_list_frame.winfo_children():
            widget.destroy()

        self.browser_windows = {}
        self.selected_windows = {}

        all_windows = gw.getAllWindows()
        browser_titles = ["Chrome", "Firefox", "Edge", "Brave", "Opera", "谷歌浏览器"]

        detected_count = 0
        for window in all_windows:
            if window.title and any(browser in window.title for browser in browser_titles):
                self.browser_windows[window._hWnd] = window
                var = tk.BooleanVar(value=True) # 简化逻辑：总是新建变量并默认选中
                self.selected_windows[window._hWnd] = var
                cb = tk.Checkbutton(self.window_list_frame, text=window.title, variable=var)
                cb.pack(anchor="w")
                detected_count += 1
        logging.info(f"Detected {detected_count} browser windows.")

        if not self.browser_windows:
            tk.Label(self.window_list_frame, text="未找到打开的浏览器窗口。").pack()

    def arrange_windows(self):
        logging.info("arrange_windows called.")
        """（可靠版）排列当前在界面上被勾选的窗口。"""
        selected_browser_windows = []
        for hwnd, var in self.selected_windows.items():
            if var.get(): # 只相信当前界面的勾选状态
                if hwnd in self.browser_windows:
                    selected_browser_windows.append(self.browser_windows[hwnd])

        num_windows = len(selected_browser_windows)
        logging.info(f"Number of selected windows for arrangement: {num_windows}")
        if num_windows == 0:
            print("没有选中需要排列的窗口。")
            logging.info("No windows selected for arrangement.")
            return

        try:
            monitor_info = win32api.GetMonitorInfo(win32api.MonitorFromPoint((0,0)))
            work_area = monitor_info.get("Work")
            screen_left, screen_top, screen_width, screen_height = work_area
            logging.info(f"Screen work area: Left={screen_left}, Top={screen_top}, Width={screen_width}, Height={screen_height}")
        except Exception as e:
            logging.error(f"Error getting monitor info: {e}")
            print(f"Error getting monitor info: {e}")
            return

        cols = math.ceil(math.sqrt(num_windows))
        rows = math.ceil(num_windows / cols)

        window_width = screen_width // cols
        window_height = screen_height // rows
        logging.info(f"Arrangement grid: {rows} rows, {cols} columns. Window size: {window_width}x{window_height}")

        for i, window in enumerate(selected_browser_windows):
            row = i // cols
            col = i % cols
            x = screen_left + col * window_width
            y = screen_top + row * window_height

            try:
                logging.info(f"Processing window '{window.title}': Current pos=({window.left},{window.top}), size=({window.width},{window.height})")
                # Restore window to normal state if minimized or maximized
                if window.isMinimized or window.isMaximized:
                    logging.info(f"Window '{window.title}' is minimized or maximized, restoring to normal.")
                    window.restore()
                    time.sleep(0.2) # Give it a moment to restore

                logging.info(f"Moving/resizing window '{window.title}' to ({x},{y}) {window_width}x{window_height}")
                window.moveTo(x, y)
                window.resizeTo(window_width, window_height)
                window.activate()

                # Verify actual position and size after operation
                time.sleep(0.1) # Give OS a moment to apply changes
                logging.info(f"Window '{window.title}' actual pos=({window.left},{window.top}), size=({window.width},{window.height})")
                logging.info(f"Successfully moved/resized window '{window.title}'.")
            except Exception as e:
                logging.error(f"无法移动/调整窗口 '{window.title}': {e}")
                print(f"无法移动/调整窗口 '{window.title}': {e}")

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = BrowserGridArrangerApp(root)
        root.mainloop()
    except Exception as e:
        logging.critical(f"Unhandled exception in main loop: {e}", exc_info=True)