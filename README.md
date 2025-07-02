# FoFa_Scanner

一个高效的 FOFA API 批量查询脚本，支持多线程并发和结果去重。

## 功能特点

- 🚀 多线程并发查询
- 🔍 从文件批量读取查询语句
- 🧹 自动结果去重
- ⏱️ 智能速率控制
- 📊 生成带时间戳的CSV结果文件
- 📝 详细的错误日志记录

## 快速开始

### 安装依赖

```bash
pip install requests
```

### 配置脚本

编辑 `fofa_scanner.py` 修改以下参数：

```Python
FOFA_EMAIL = "your_email@example.com"  # FOFA账号邮箱
FOFA_KEY = "your_api_key"             # FOFA API密钥
```

### 准备查询

创建 `fofa_queries.txt` 文件，每行一个查询语法：

```Markdown
title="管理系统"
ip="192.168.1.0/24"
domain="example.com"
```

### 执行查询

```Bash
python fofa_scanner.py
```

## 输出文件

### 结果文件

`results/fofa_results_[时间戳].csv` 包含以下字段：

```Markdown
host, ip, title, port, protocol
```

### 日志文件

`fofa_error_log.txt` 记录所有错误信息

## 配置参数

| 参数               | 描述             | 默认值 | 建议范围 |
| ------------------ | ---------------- | ------ | -------- |
| CONCURRENT_WORKERS | 并发线程数       | 3      | 1月5日   |
| MIN_DELAY          | 最小请求间隔(秒) | 1.5    | 1月3日   |
| MAX_DELAY          | 最大请求间隔(秒) | 3      | 2月5日   |
| REQUEST_TIMEOUT    | 请求超时时间(秒) | 30     | 15-60    |
| MAX_RETRIES        | 失败重试次数     | 3      | 2月5日   |

## 常见问题

### 如何增加返回字段？

修改脚本中的 `fields` 参数：

```Python
params = {
    # ..."fields": "host,ip,title,port,protocol,domain,server",
    # ...
}
```

### 遇到429错误怎么办？

1. 增加请求间隔时间
2. 减少并发线程数
3. 检查API调用配额

## 注意事项

1. 遵守FOFA API使用条款
2. 禁止用于非法用途
3. 商业账号注意查询配额
4. 重要操作建议先小批量测试
