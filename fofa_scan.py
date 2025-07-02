import requests
import csv
import base64
import datetime
import os
import time
import random
import concurrent.futures
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 配置常量
BASE_URL = "https://fofa.info/api/v1/search/all"
FOFA_EMAIL = "your_email@example.com"  # 替换为您的邮箱
FOFA_KEY = "your_api_key_here"        # 替换为您的API密钥
QUERY_FILE = "fofa_queries.txt"       # 查询语句文件
LOG_FILE = "fofa_error_log.txt"       # 错误日志
OUTPUT_DIR = "results"                # 输出目录
MAX_RETRIES = 3                       # 最大重试次数
CONCURRENT_WORKERS = 3                # 并发线程数
REQUEST_TIMEOUT = 30                  # 请求超时(秒)
MIN_DELAY = 1.5                       # 最小请求间隔
MAX_DELAY = 3.0                       # 最大请求间隔

# 初始化目录
os.makedirs(OUTPUT_DIR, exist_ok=True)

class FofaScanner:
    def __init__(self):
        # 配置重试策略
        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("https://", adapter)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        })
        self.last_request_time = time.time() - MAX_DELAY
        self.seen_hosts = set()

    def get_output_filename(self):
        """生成带时间戳的输出文件名"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(OUTPUT_DIR, f"fofa_results_{timestamp}.csv")

    def read_queries(self):
        """读取查询文件"""
        if not os.path.exists(QUERY_FILE):
            print(f"[!] 查询文件不存在: {QUERY_FILE}")
            return []

        try:
            with open(QUERY_FILE, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            self.log_error(f"读取查询文件错误: {str(e)}")
            return []

    def log_error(self, message):
        """记录错误日志"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as log:
            log.write(f"[{timestamp}] {message}\n")
        print(f"[!] 错误: {message}")

    def rate_limit(self):
        """请求速率控制"""
        elapsed = time.time() - self.last_request_time
        if elapsed < MIN_DELAY:
            delay = random.uniform(MIN_DELAY - elapsed, MAX_DELAY - elapsed)
            time.sleep(delay)

    def query_fofa_api(self, query):
        """查询FOFA API"""
        if not query:
            return None

        self.rate_limit()
        
        try:
            encoded_query = base64.b64encode(query.encode("utf-8")).decode("utf-8")
            params = {
                "email": FOFA_EMAIL,
                "key": FOFA_KEY,
                "qbase64": encoded_query,
                "fields": "host,ip,title,port,protocol",
                "size": 1000,
                "page": 1
            }

            response = self.session.get(BASE_URL, params=params, timeout=REQUEST_TIMEOUT)
            self.last_request_time = time.time()

            if response.status_code == 200:
                return response.json().get("results", [])
            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 10))
                self.log_error(f"速率限制触发，等待 {retry_after} 秒")
                time.sleep(retry_after)
                return self.query_fofa_api(query)  # 递归重试
            else:
                self.log_error(f"API错误[{response.status_code}]: {response.text}")
                return None

        except requests.exceptions.RequestException as e:
            self.log_error(f"请求失败: {str(e)}")
            return None
        except Exception as e:
            self.log_error(f"未知错误: {str(e)}")
            return None

    def run(self):
        """主执行函数"""
        start_time = time.time()
        output_file = self.get_output_filename()
        print(f"[*] 输出文件: {output_file}")

        queries = self.read_queries()
        if not queries:
            print("[!] 没有可用的查询语句")
            return

        print(f"[*] 找到 {len(queries)} 个查询语句")
        
        # 加载已有记录去重
        if os.path.exists(output_file):
            try:
                with open(output_file, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    next(reader, None)  # 跳过标题
                    for row in reader:
                        if row and len(row) > 0:
                            self.seen_hosts.add(row[0])
                print(f"[*] 已加载 {len(self.seen_hosts)} 个已存在的记录用于去重")
            except Exception as e:
                self.log_error(f"读取已有文件错误: {str(e)}")

        # 准备CSV文件
        columns = ["host", "ip", "title", "port", "protocol"]
        total_results = 0

        with open(output_file, "a", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            if not self.seen_hosts:
                writer.writerow(columns)

            # 使用线程池处理查询
            with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as executor:
                future_to_query = {executor.submit(self.query_fofa_api, query): query for query in queries}
                
                for future in concurrent.futures.as_completed(future_to_query):
                    query = future_to_query[future]
                    try:
                        results = future.result()
                        if not results:
                            print(f"[!] 查询无结果: {query}")
                            continue

                        new_entries = 0
                        for row in results:
                            if len(row) >= 5:  # 确保有足够字段
                                host = row[0]
                                if host not in self.seen_hosts:
                                    writer.writerow(row[:5])  # 只写入前5个字段
                                    self.seen_hosts.add(host)
                                    new_entries += 1

                        total_results += new_entries
                        print(f"[√] 查询: {query[:50]}... -> 新增: {new_entries} 总计: {total_results}")
                        
                        # 随机延迟
                        time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))
                        
                    except Exception as e:
                        self.log_error(f"处理查询失败: {query} -> {str(e)}")

        # 性能统计
        elapsed_time = time.time() - start_time
        print("\n[√] 所有查询处理完成!")
        print(f"=== 统计 ===")
        print(f"总查询数: {len(queries)}")
        print(f"总结果数: {total_results}")
        print(f"总耗时: {elapsed_time:.2f}秒")
        print(f"结果文件: {output_file}")

        # 检查错误
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as log:
                error_count = len(log.readlines())
            if error_count > 0:
                print(f"[!] 发现 {error_count} 个错误，请检查 {LOG_FILE}")

if __name__ == "__main__":
    scanner = FofaScanner()
    scanner.run()