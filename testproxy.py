import tkinter as tk
from tkinter import ttk
import requests
import socket
import socks
import time
import threading
from queue import Queue

class ProxyTesterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("代理服务器测试工具 v2.0")
        self.proxy_list = []
        self.item_ids = []
        self.result_queue = Queue()
        
        # 初始化界面
        self.setup_ui()
        
        # 启动结果处理循环
        self.process_results()

    def setup_ui(self):
        # 输入区域
        input_frame = ttk.Frame(self.root, padding=10)
        input_frame.grid(row=0, column=0, sticky="ew")

        ttk.Label(input_frame, text="IP:").grid(row=0, column=0, padx=5)
        self.ip_entry = ttk.Entry(input_frame, width=15)
        self.ip_entry.grid(row=0, column=1, padx=5)

        ttk.Label(input_frame, text="端口:").grid(row=0, column=2, padx=5)
        self.port_entry = ttk.Entry(input_frame, width=8)
        self.port_entry.grid(row=0, column=3, padx=5)

        ttk.Label(input_frame, text="类型:").grid(row=0, column=4, padx=5)
        self.type_combo = ttk.Combobox(input_frame, values=["HTTP", "HTTPS", "SOCKS4", "SOCKS5"], width=8)
        self.type_combo.current(0)
        self.type_combo.grid(row=0, column=5, padx=5)

        add_btn = ttk.Button(input_frame, text="添加代理", command=self.add_proxy)
        add_btn.grid(row=0, column=6, padx=5)

        del_btn = ttk.Button(input_frame, text="删除选中", command=self.delete_proxy)
        del_btn.grid(row=0, column=7, padx=5)

        # 测试按钮
        test_frame = ttk.Frame(self.root)
        test_frame.grid(row=1, column=0, pady=5)
        test_btn = ttk.Button(test_frame, text="开始测试", command=self.start_test)
        test_btn.pack(side=tk.LEFT, padx=5)

        # 结果表格
        columns = ("ip", "port", "type", "real_ip", "country", "city", "isp", "latency", "status")
        self.tree = ttk.Treeview(
            self.root, columns=columns, show="headings", height=15
        )
        
        # 设置列宽和标题
        col_settings = [
            ("IP地址", 120),
            ("端口", 80),
            ("类型", 80),
            ("实际IP", 120),
            ("国家", 100),
            ("城市", 100),
            ("ISP", 150),
            ("延迟(ms)", 100),
            ("状态", 100)
        ]
        
        for idx, (heading, width) in enumerate(col_settings):
            self.tree.heading(columns[idx], text=heading)
            self.tree.column(columns[idx], width=width, anchor=tk.CENTER)
        
        self.tree.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")

    def add_proxy(self):
        ip = self.ip_entry.get()
        port = self.port_entry.get()
        proxy_type = self.type_combo.get()
        
        if ip and port and proxy_type:
            self.proxy_list.append({
                "ip": ip,
                "port": port,
                "type": proxy_type
            })
            self.tree.insert("", "end", values=(
                ip, port, proxy_type, 
                "", "", "", "", 
                "待测试", "待测试"
            ))
            self.ip_entry.delete(0, tk.END)
            self.port_entry.delete(0, tk.END)

    def delete_proxy(self):
        selected_items = self.tree.selection()
        for item in selected_items:
            index = self.tree.index(item)
            del self.proxy_list[index]
            self.tree.delete(item)

    def start_test(self):
        # 清空旧的测试结果
        self.item_ids = []
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # 插入新的测试条目
        for proxy in self.proxy_list:
            item_id = self.tree.insert("", "end", values=(
                proxy["ip"],
                proxy["port"],
                proxy["type"],
                "测试中...",
                "测试中...",
                "测试中...",
                "测试中...",
                "测试中...",
                "测试中..."
            ))
            self.item_ids.append(item_id)
            
        # 启动测试线程
        for idx, proxy in enumerate(self.proxy_list):
            thread = threading.Thread(
                target=self.test_proxy,
                args=(self.item_ids[idx], proxy)
            )
            thread.start()

    def test_proxy(self, item_id, proxy):
        start_time = time.time()
        status = "失败"
        latency = "超时"
        real_ip = "N/A"
        country = "N/A"
        city = "N/A"
        isp = "N/A"

        try:
            # 测试代理连接
            if proxy["type"].startswith("SOCKS"):
                socks_version = socks.SOCKS5 if proxy["type"] == "SOCKS5" else socks.SOCKS4
                socks.set_default_proxy(
                    socks_version,
                    proxy["ip"],
                    int(proxy["port"])
                )
                socket.socket = socks.socksocket
                response = requests.get("http://httpbin.org/ip", timeout=10)
            else:
                proxies = {
                    "http": f"{proxy['type'].lower()}://{proxy['ip']}:{proxy['port']}",
                    "https": f"{proxy['type'].lower()}://{proxy['ip']}:{proxy['port']}"
                }
                response = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=10)

            if response.status_code == 200:
                status = "成功"
                latency = f"{(time.time() - start_time) * 1000:.2f}"
                
                # 获取实际出口IP
                real_ip = response.json()['origin'].split(', ')[0]
                
                # 获取地理位置信息
                geo_info = self.get_geo_info(real_ip)
                country = geo_info.get('country', 'N/A')
                city = geo_info.get('city', 'N/A')
                isp = geo_info.get('isp', 'N/A')

        except Exception as e:
            status = f"失败: {str(e)}"
        finally:
            if proxy["type"].startswith("SOCKS"):
                socks.set_default_proxy()

        # 提交结果到队列
        self.result_queue.put((
            item_id,
            real_ip,
            country,
            city,
            isp,
            latency,
            status
        ))

    def get_geo_info(self, ip):
        try:
            response = requests.get(f"http://ip-api.com/json/{ip}?fields=status,message,country,city,isp", timeout=5)
            data = response.json()
            if data['status'] == 'success':
                return {
                    "country": data.get('country', 'N/A'),
                    "city": data.get('city', 'N/A'),
                    "isp": data.get('isp', 'N/A')
                }
            return {
                "country": "失败",
                "city": data.get('message', 'N/A'),
                "isp": "N/A"
            }
        except Exception as e:
            return {
                "country": "错误",
                "city": str(e),
                "isp": "N/A"
            }

    def process_results(self):
        while not self.result_queue.empty():
            item_id, real_ip, country, city, isp, latency, status = self.result_queue.get()
            
            # 获取当前值并更新
            current_values = list(self.tree.item(item_id, 'values'))
            update_fields = {
                3: real_ip,
                4: country,
                5: city,
                6: isp,
                7: latency,
                8: status
            }
            
            for idx, value in update_fields.items():
                current_values[idx] = value
            
            self.tree.item(item_id, values=current_values)
        
        self.root.after(100, self.process_results)

if __name__ == "__main__":
    root = tk.Tk()
    app = ProxyTesterApp(root)
    root.mainloop()