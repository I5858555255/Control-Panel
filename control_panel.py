import tkinter as tk
from tkinter import ttk
import asyncio
import websockets
import functools
import threading
import json
from PIL import Image, ImageTk
import requests
from io import BytesIO
import random
import logging
from datetime import datetime, timedelta
import subprocess

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='control_panel_log.txt',
    filemode='a'
)

# --- WebSocket Server ---
class WebSocketServer:
    def __init__(self, app_instance):
        self.clients = {} # Maps websocket to product_id
        self.app = app_instance
        self.loop = None # Will hold the event loop for this thread
        self.server_task = None

    async def handle_connection(self, websocket, path=None):
        client_id = None
        try:
            logging.info(f"New client connected: {websocket.remote_address}")
            async for message in websocket:
                data = json.loads(message)
                logging.info(f"Received message: {data}")
                
                if data.get("type") == "register":
                    product_id = data.get("productId")
                    image_url = data.get("imageUrl")
                    client_id = product_id
                    
                    if product_id and product_id not in self.clients.values():
                        self.clients[websocket] = product_id
                        # Schedule GUI update in the main thread
                        self.app.master.after(0, self.app.add_product_card, product_id, image_url, websocket)
                    else:
                        logging.warning(f"Product {product_id} is already registered or ID is null.")

        except websockets.exceptions.ConnectionClosed as e:
            logging.info(f"Client {client_id or websocket.remote_address} disconnected. Reason: {e.code} {e.reason}")
        except Exception as e:
            logging.error(f"Error handling client {client_id or websocket.remote_address}: {e}", exc_info=True)
        finally:
            if websocket in self.clients:
                product_id_to_remove = self.clients.pop(websocket)
                self.app.master.after(0, self.app.remove_product_card, product_id_to_remove)

    async def send_message(self, websocket, message):
        try:
            await websocket.send(json.dumps(message))
            logging.info(f"Sent message to {self.clients.get(websocket, 'unknown')}: {message}")
        except websockets.exceptions.ConnectionClosed:
            # The main handler will deal with cleanup
            pass
        except Exception as e:
            logging.error(f"Failed to send message: {e}")

    async def _websocket_handler(self, websocket, path=None):
        await self.handle_connection(websocket, path)

    def start(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.main())

    async def main(self):
        self.loop = asyncio.get_running_loop()
        async with websockets.serve(self._websocket_handler, "localhost", 8765):
            logging.info("WebSocket server started on ws://localhost:8765")
            self.app.master.after(0, self.app.update_status, f"监听中: ws://localhost:8765. 已连接客户端: {len(self.clients)}")
            await asyncio.Future()  # run forever

# --- GUI Application ---
class ControlPanelApp:
    def __init__(self, master):
        self.master = master
        master.title("中央控制面板")
        master.geometry("950x700") # Adjusted for better layout
        
        self.ws_server = WebSocketServer(self)
        self.product_cards = {} # Maps product_id to its card frame and widgets

        # --- Main Layout ---
        main_frame = ttk.Frame(master, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Global Settings ---
        settings_frame = ttk.LabelFrame(main_frame, text="全局设置", padding="10")
        settings_frame.pack(fill=tk.X, pady=5)
        
        # Target Time
        ttk.Label(settings_frame, text="目标时间 (时:分:秒):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        now = datetime.now()
        self.hour_var = tk.StringVar(value=now.strftime("%H"))
        self.min_var = tk.StringVar(value=now.strftime("%M"))
        self.sec_var = tk.StringVar(value=now.strftime("%S"))

        ttk.Entry(settings_frame, textvariable=self.hour_var, width=5).grid(row=0, column=1, padx=2)
        ttk.Entry(settings_frame, textvariable=self.min_var, width=5).grid(row=0, column=2, padx=2)
        ttk.Entry(settings_frame, textvariable=self.sec_var, width=5).grid(row=0, column=3, padx=2)

        # Set Time + 30s Button
        set_time_button = ttk.Button(settings_frame, text="当前时间+30秒", command=self.set_time_plus_30s)
        set_time_button.grid(row=0, column=4, padx=5)

        # Current System Time Display
        ttk.Label(settings_frame, text="当前系统时间:").grid(row=0, column=5, padx=15, pady=5, sticky="w")
        self.current_hour_var = tk.StringVar()
        self.current_min_var = tk.StringVar()
        self.current_sec_var = tk.StringVar()
        ttk.Label(settings_frame, textvariable=self.current_hour_var, width=3).grid(row=0, column=6, padx=2)
        ttk.Label(settings_frame, textvariable=self.current_min_var, width=3).grid(row=0, column=7, padx=2)
        ttk.Label(settings_frame, textvariable=self.current_sec_var, width=3).grid(row=0, column=8, padx=2)

        # Decrement Value
        ttk.Label(settings_frame, text="递减值:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.decrement_var = tk.StringVar(value="0.1")
        ttk.Entry(settings_frame, textvariable=self.decrement_var, width=7).grid(row=1, column=1, padx=5)

        # Delays
        ttk.Label(settings_frame, text="检查间隔 (毫秒):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.check_delay_var = tk.StringVar(value="500")
        ttk.Entry(settings_frame, textvariable=self.check_delay_var, width=7).grid(row=2, column=1, padx=5)
        
        ttk.Label(settings_frame, text="结果检查间隔 (毫秒):").grid(row=2, column=2, padx=5, pady=5, sticky="w")
        self.result_delay_var = tk.StringVar(value="1500")
        ttk.Entry(settings_frame, textvariable=self.result_delay_var, width=7).grid(row=2, column=3, padx=5)

        ttk.Label(settings_frame, text="重新提交间隔 (毫秒):").grid(row=2, column=4, padx=5, pady=5, sticky="w")
        self.resubmit_delay_var = tk.StringVar(value="500")
        ttk.Entry(settings_frame, textvariable=self.resubmit_delay_var, width=7).grid(row=2, column=5, padx=5)

        # --- Product List ---
        list_frame = ttk.LabelFrame(main_frame, text="已连接商品", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        canvas = tk.Canvas(list_frame)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        self.current_row = 0
        self.current_col = 0

        self.scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Configure columns to expand equally for 3-column layout
        for i in range(3):
            self.scrollable_frame.grid_columnconfigure(i, weight=1)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # --- Action Buttons ---
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=5)
        
        self.start_button = ttk.Button(action_frame, text="全部开始", command=self.start_all_tasks)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.apply_button = ttk.Button(action_frame, text="应用更改", command=self.apply_all_changes)
        self.apply_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(action_frame, text="全部停止", command=self.stop_all_tasks)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.browser_grid_button = ttk.Button(action_frame, text="Browser Grid Arranger", command=self.run_browser_grid_arranger)
        self.browser_grid_button.pack(side=tk.LEFT, padx=5)

        # --- Status Bar ---
        self.status_var = tk.StringVar(value="初始化中...")
        status_bar = ttk.Label(master, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w")
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Start updating current system time display
        self.update_live_system_time()

    def run_browser_grid_arranger(self):
        try:
            subprocess.Popen(['python', 'browser_grid_arranger.py'])
            self.update_status("Started Browser Grid Arranger")
        except FileNotFoundError:
            self.update_status("Error: 'python' command not found or browser_grid_arranger.py not found.")
        except Exception as e:
            self.update_status(f"Error starting Browser Grid Arranger: {e}")

    def update_live_system_time(self):
        now = datetime.now()
        self.current_hour_var.set(now.strftime("%H"))
        self.current_min_var.set(now.strftime("%M"))
        self.current_sec_var.set(now.strftime("%S"))
        self.master.after(1000, self.update_live_system_time) # Schedule next update in 1 second

    def update_status(self, text):
        self.status_var.set(text)
        logging.info(f"Status Update: {text}")

    def set_time_plus_30s(self):
        now = datetime.now() + timedelta(seconds=30)
        self.hour_var.set(now.strftime("%H"))
        self.min_var.set(now.strftime("%M"))
        self.sec_var.set(now.strftime("%S"))

    def add_product_card(self, product_id, image_url, websocket):
        if product_id in self.product_cards:
            logging.warning(f"Card for product {product_id} already exists.")
            return

        card = ttk.Frame(self.scrollable_frame, padding="2", relief=tk.RIDGE, borderwidth=1)
        card.grid(row=self.current_row, column=self.current_col, padx=2, pady=2, sticky="nsew")

        # Image
        img_label = ttk.Label(card, text="加载图片中...")
        img_label.grid(row=0, column=0, rowspan=3, padx=2, pady=2)
        threading.Thread(target=self.load_image, args=(image_url, img_label), daemon=True).start()

        # Info
        ttk.Label(card, text=f"商品ID: {product_id}", font=("Helvetica", 10, "bold")).grid(row=0, column=1, sticky="w", padx=5)

        # Min Values (changed to Text widget)
        ttk.Label(card, text="最低值(每行一个):").grid(row=1, column=1, sticky="nw", padx=5)
        min_values_text = tk.Text(card, width=10, height=3) # Text widget for multi-line input
        min_values_text.grid(row=1, column=2, sticky="w", padx=5)
        min_values_text.insert(tk.END, "0.0") # Default value

        # SKU Prices
        ttk.Label(card, text="SKU价格(每行一个):").grid(row=1, column=3, sticky="nw", padx=5) # Use "nw" for alignment
        sku_prices_text = tk.Text(card, width=15, height=3) # Text widget for multi-line input
        sku_prices_text.grid(row=1, column=4, sticky="w", padx=5)
        sku_prices_text.insert(tk.END, "0.0") # Default value

        # Auto Decrement
        auto_decrement_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(card, text="自动递减", variable=auto_decrement_var).grid(row=2, column=1, columnspan=2, sticky="w", padx=5)

        self.product_cards[product_id] = {
            "frame": card,
            "min_values_text": min_values_text, # Store the text widget
            "sku_prices_text": sku_prices_text, # Store the text widget
            "auto_decrement_var": auto_decrement_var,
            "websocket": websocket
        }
        self.update_status(f"监听中: ws://localhost:8765. 已连接客户端: {len(self.ws_server.clients)}")
        logging.info(f"Added card for product {product_id}")

        self.current_col += 1
        if self.current_col >= 3:
            self.current_col = 0
            self.current_row += 1

    def remove_product_card(self, product_id):
        if product_id in self.product_cards:
            self.product_cards[product_id]["frame"].destroy()
            del self.product_cards[product_id]
            self.update_status(f"监听中: ws://localhost:8765. 已连接客户端: {len(self.ws_server.clients)}")
            logging.info(f"Removed card for product {product_id}")

    def load_image(self, url, label):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            img_data = response.content
            img = Image.open(BytesIO(img_data))
            # Set image size to 50x50 pixels
            img.thumbnail((50, 50))
            photo = ImageTk.PhotoImage(img)
            
            # Safely update the GUI from the main thread
            def update_gui():
                label.config(image=photo)
                label.image = photo # Keep a reference!
            
            self.master.after(0, update_gui)

        except Exception as e:
            def update_gui_fail():
                label.config(text="图片加载失败")
            self.master.after(0, update_gui_fail)
            logging.error(f"Failed to load image from {url}: {e}")

    def start_all_tasks(self):
        logging.info("--- '全部开始' clicked ---")
        try:
            # Gather fresh global parameters at the moment the button is clicked
            global_params = {
                "targetHour": int(self.hour_var.get()),
                "targetMinute": int(self.min_var.get()),
                "targetSecond": int(self.sec_var.get()),
                "decrementValue": float(self.decrement_var.get()),
                "checkDelay": int(self.check_delay_var.get()),
                "resultCheckDelay": int(self.result_delay_var.get()),
                "resubmitDelay": int(self.resubmit_delay_var.get()),
            }
            logging.info(f"Global parameters for start: {global_params}")

            # Iterate through each client and send their specific settings with the start command
            for product_id, card_info in self.product_cards.items():
                min_values_str = card_info["min_values_text"].get("1.0", tk.END).strip()
                min_values = []
                for p in min_values_str.splitlines():
                    p_stripped = p.strip()
                    if p_stripped:
                        try:
                            min_values.append(float(p_stripped))
                        except ValueError:
                            logging.warning(f"Invalid min value input skipped for product {product_id}: '{p_stripped}'")

                sku_prices_str = card_info["sku_prices_text"].get("1.0", tk.END).strip()
                sku_prices = []
                for p in sku_prices_str.splitlines():
                    p_stripped = p.strip()
                    if p_stripped:
                        try:
                            sku_prices.append(float(p_stripped))
                        except ValueError:
                            logging.warning(f"Invalid SKU price input skipped for product {product_id}: '{p_stripped}'")

                specific_params = {
                    "minValues": min_values, # Changed from minValue
                    "skuPrices": sku_prices, # Changed from realPosValue
                    "autoDecrement": card_info["auto_decrement_var"].get(),
                    "randomDelay": random.randint(0, 500)  # Add a small random delay
                }
                
                message = {
                    "type": "start",
                    "globalParams": global_params,
                    "specificParams": specific_params
                }
                
                asyncio.run_coroutine_threadsafe(
                    self.ws_server.send_message(card_info["websocket"], message),
                    self.ws_server.loop
                )
            self.update_status(f"已向 {len(self.product_cards)} 个客户端发送带有最新设置的 '开始' 命令。")
        except Exception as e:
            logging.error(f"Error in start_all_tasks: {e}", exc_info=True)
            self.update_status(f"错误: {e}")

    def stop_all_tasks(self):
        logging.info("--- '全部停止' clicked ---")
        message = {"type": "stop"}
        for product_id, card_info in self.product_cards.items():
            asyncio.run_coroutine_threadsafe(
                self.ws_server.send_message(card_info["websocket"], message),
                self.ws_server.loop # Use the loop created in the server thread
            )
        self.update_status(f"已向 {len(self.product_cards)} 个客户端发送 '停止' 命令。")

    def apply_all_changes(self):
        logging.info("--- '应用更改' clicked ---")
        try:
            global_params = {
                "targetHour": int(self.hour_var.get()),
                "targetMinute": int(self.min_var.get()),
                "targetSecond": int(self.sec_var.get()),
                "decrementValue": float(self.decrement_var.get()),
                "checkDelay": int(self.check_delay_var.get()),
                "resultCheckDelay": int(self.result_delay_var.get()),
                "resubmitDelay": int(self.resubmit_delay_var.get()),
            }
            logging.info(f"Global parameters for apply: {global_params}")

            for product_id, card_info in self.product_cards.items():
                min_values_str = card_info["min_values_text"].get("1.0", tk.END).strip()
                min_values = []
                for p in min_values_str.splitlines():
                    p_stripped = p.strip()
                    if p_stripped:
                        try:
                            min_values.append(float(p_stripped))
                        except ValueError:
                            logging.warning(f"Invalid min value input skipped for product {product_id}: '{p_stripped}'")

                sku_prices_str = card_info["sku_prices_text"].get("1.0", tk.END).strip()
                sku_prices = []
                for p in sku_prices_str.splitlines():
                    p_stripped = p.strip()
                    if p_stripped:
                        try:
                            sku_prices.append(float(p_stripped))
                        except ValueError:
                            logging.warning(f"Invalid SKU price input skipped for product {product_id}: '{p_stripped}'")

                specific_params = {
                    "minValues": min_values, # Changed from minValue
                    "skuPrices": sku_prices, # Changed from realPosValue
                    "autoDecrement": card_info["auto_decrement_var"].get(),
                }
                
                message = {
                    "type": "apply_settings",
                    "globalParams": global_params,
                    "specificParams": specific_params
                }
                
                asyncio.run_coroutine_threadsafe(
                    self.ws_server.send_message(card_info["websocket"], message),
                    self.ws_server.loop
                )
            self.update_status(f"已向 {len(self.product_cards)} 个客户端发送 '应用更改' 命令。")
        except Exception as e:
            logging.error(f"Error in apply_all_changes: {e}", exc_info=True)
            self.update_status(f"错误: {e}")

    def start_server_thread(self):
        self.server_thread = threading.Thread(target=self.ws_server.start, daemon=True)
        # The loop is now created and managed inside the thread's target function (self.ws_server.start)
        self.server_thread.start()

if __name__ == "__main__":
    logging.info("--- Application Starting ---")
    root = tk.Tk()
    app = ControlPanelApp(root)
    
    # Start the WebSocket server in a separate thread
    app.start_server_thread()
    
    root.mainloop()
    logging.info("--- Application Closed ---")