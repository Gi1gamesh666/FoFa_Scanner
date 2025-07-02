import requests
import csv
import base64
import datetime
import os
import json
import time
import concurrent.futures
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 常量定义
BASE_URL = "https://fofa.info/api/v1/search/all"
FOFA_EMAIL = "fofa20201111@163.com"  # 替换为您的 FOFA 邮箱
FOFA_KEY = "f3889374477bec3b1b2b570496deb69e"         # 替换为您的 API 密钥
QUERY_FILE = "fofa_queries.txt"        # FOFA 查询语句文件
LOG_FILE = "fofa_error_log.txt"         # 错误日志文件
MAX_RETRIES = 3                         # 最大重试次数
RETRY_DELAY = 2                         # 重试延迟（秒）
CONCURRENT_WORKERS = 5                  # 并发线程数
REQUEST_TIMEOUT = 30                    # 请求超时（秒）

# 生成带时间戳的输出文件名
def get_output_filename():
    now = datetime.datetime.now()
    return f"fofa_results_{now.strftime('%Y%m%d_%H%M%S')}.csv"

# 配置重试策略
retry_strategy = Retry(
    total=MAX_RETRIES,
    backoff_factor=RETRY_DELAY,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session = requests.Session()
session.mount("https://", adapter)

# 从文件中读取 FOFA 查询语句
def read_queries():
    if not os.path.exists(QUERY_FILE):
        print(f"[!] 查询文件不存在: {QUERY_FILE}")
        return []
    
    try:
        with open(QUERY_FILE, "r", encoding="utf-8") as f:
            queries = [line.strip() for line in f if line.strip()]
        return queries
    except Exception as e:
        log_error(f"读取查询文件错误: {str(e)}")
        return []

# 记录错误到日志文件
def log_error(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        log.write(f"[{timestamp}] {message}\n")
    print(f"[!] 错误: {message}")

# 查询 FOFA API
def query_fofa_api(query):
    if not query:
        return None
        
    encoded_query = base64.b64encode(query.encode("utf-8")).decode("utf-8")
    
    params = {
        "email": FOFA_EMAIL,
        "key": FOFA_KEY,
        "qbase64": encoded_query,
        "fields": "host,ip,title,port,protocol",
        "size": 10000,  # 每次请求最大结果数
        "page": 1
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    try:
        response = session.get(
            BASE_URL, 
            params=params, 
            headers=headers, 
            timeout=REQUEST_TIMEOUT
        )
        
        if response.status_code == 200:
            return response.json().get("results", [])
        else:
            error_msg = f"API 响应错误: {response.status_code} - {response.text}"
            log_error(f"{query} -> {error_msg}")
            return None
    
    except requests.exceptions.RequestException as e:
        log_error(f"{query} -> 请求失败: {str(e)}")
        return None
    except json.JSONDecodeError:
        log_error(f"{query} -> JSON 解析失败")
        return None

# 写入结果到 CSV 文件
def write_to_csv(results, csv_writer, seen_hosts):
    if not results:
        return 0
    
    new_entries = 0
    for result in results:
        # 确保结果有 5 个字段
        if len(result) != 5:
            continue
            
        host, ip, title, port, protocol = result
        
        # 去重检查
        if host in seen_hosts:
            continue
            
        try:
            # 处理可能的 None 值
            host = host or ""
            ip = ip or ""
            title = title or ""
            port = str(port or "")
            protocol = protocol or ""
            
            csv_writer.writerow([host, ip, title, port, protocol])
            seen_hosts.add(host)
            new_entries += 1
        except Exception as e:
            log_error(f"写入数据错误: {str(e)}")
    
    return new_entries

# 主程序
def main():
    start_time = time.time()
    
    # 生成带时间戳的输出文件名
    output_file = get_output_filename()
    print(f"[*] 输出文件: {output_file}")
    
    # 读取查询语句
    queries = read_queries()
    if not queries:
        print("[!] 没有可用的查询语句")
        return
    
    print(f"[*] 找到 {len(queries)} 个查询语句")
    
    # 创建 CSV 文件并写入表头
    columns = ["host", "ip", "title", "port", "protocol"]
    
    # 读取已存在的host用于去重
    seen_hosts = set()
    if os.path.exists(output_file):
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)  # 跳过标题行
                for row in reader:
                    if row and len(row) > 0:
                        seen_hosts.add(row[0])
            print(f"[*] 已加载 {len(seen_hosts)} 个已存在的记录用于去重")
        except Exception as e:
            log_error(f"读取已有文件错误: {str(e)}")
    
    # 打开输出文件
    with open(output_file, "a", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        
        # 如果是新文件，写入表头
        if not seen_hosts:
            writer.writerow(columns)
        
        total_results = 0
        processed_queries = 0
        
        print("[*] 开始查询FOFA API...")
        
        # 使用线程池并发查询
        with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as executor:
            future_to_query = {executor.submit(query_fofa_api, query): query for query in queries}
            
            for future in concurrent.futures.as_completed(future_to_query):
                query = future_to_query[future]
                processed_queries += 1
                
                try:
                    results = future.result()
                    if not results:
                        print(f"[!] 查询失败: {query}")
                        continue
                    
                    new_entries = write_to_csv(results, writer, seen_hosts)
                    total_results += new_entries
                    print(f"[√] 查询成功: {query} -> 结果: {len(results)} | 新增: {new_entries} | 总计: {total_results}")
                    
                except Exception as e:
                    log_error(f"处理查询失败: {query} -> {str(e)}")
                
                # 显示进度
                progress = processed_queries / len(queries) * 100
                print(f"进度: {processed_queries}/{len(queries)} ({progress:.1f}%)", end="\r")
    
    print("\n[√] 所有查询处理完成!")
    
    # 性能统计
    elapsed_time = time.time() - start_time
    queries_per_second = len(queries) / elapsed_time if elapsed_time > 0 else 0
    
    print(f"=== 性能统计 ===")
    print(f"总查询数: {len(queries)}")
    print(f"总结果数: {total_results} (去重后)")
    print(f"总耗时: {elapsed_time:.2f} 秒")
    print(f"查询速度: {queries_per_second:.2f} 个查询/秒")
    print(f"结果文件: {output_file}")
    
    # 检查错误日志
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as log:
            error_count = len(log.readlines())
        if error_count > 0:
            print(f"[!] 发现 {error_count} 个错误，请检查 {LOG_FILE}")

if __name__ == "__main__":
    main()