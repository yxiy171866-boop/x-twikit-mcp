# X (Twitter) MCP 服务

本项目是基于 [twikit](https://github.com/d60/twikit) 实现的 Model Context Protocol (MCP) 服务，专门为 AI 助手、大语言模型及各类 AI Agent 提供与 X (Twitter) 交互的能力。通过本服务，AI 能够自主调用工具完成发推、回复评论、读取推文回复、收发私信等操作。

通过配置账号的浏览器 Cookie（`auth_token` 与 `ct0`），服务即可为 AI 提供 12 项社交平台交互工具。

---

## 功能列表

服务目前为 AI 助手提供以下 12 个 MCP 工具：

| 工具名称 | 功能描述 | 参数 |
| :--- | :--- | :--- |
| `post_tweet` | 发布新推文 | `text`（推文内容） |
| `reply_tweet` | 回复指定推文或评论 | `tweet_id`（目标推文 ID）, `text`（回复内容） |
| `get_tweet_replies` | 获取指定推文下方的评论与回复列表 | `tweet_id`（推文 ID）, `count`（获取数量，默认 10） |
| `read_direct_messages` | 获取与指定用户的私信聊天记录 | `username`（对方用户名）, `count`（获取条数，默认 10） |
| `send_direct_message` | 向指定用户发送私信或回复消息 | `username`（目标用户名）, `text`（消息内容）, `reply_to_message_id`（可选） |
| `search_tweets` | 根据关键词或查询语法搜索推文 | `query`（搜索词）, `count`（获取数量，默认 10） |
| `get_tweet_by_id` | 获取指定推文的详细信息及互动数据 | `tweet_id`（推文 ID） |
| `get_user_info` | 获取指定用户的个人资料及粉丝等统计信息 | `username`（用户名） |
| `get_user_tweets` | 获取指定用户最近发布的推文列表 | `username`（用户名）, `count`（获取数量，默认 5） |
| `favorite_tweet` | 点赞指定推文 | `tweet_id`（推文 ID） |
| `retweet` | 转推指定推文 | `tweet_id`（推文 ID） |
| `delete_tweet` | 删除自己发布的推文 | `tweet_id`（推文 ID） |

---

## 安装与部署

### 1. 克隆仓库与安装依赖

环境要求：Python 3.10 及以上。

```bash
git clone https://github.com/yxiy171866-boop/x-twikit-mcp.git
cd x-twikit-mcp
pip install -r requirements.txt
```

### 2. 获取与配置 Cookie

运行服务需要两个 Cookie 字段：`auth_token` 与 `ct0`。

1. 在浏览器中打开并登录 [x.com](https://x.com)。
2. 按 `F12` 打开浏览器开发者工具。
3. 进入 **Application**（Chrome/Edge）或 **存储 (Storage)**（Firefox）标签页。
4. 展开左侧的 **Cookies**，选择 `https://x.com`。
5. 在列表中找到并复制以下两项的值：
   - `auth_token`
   - `ct0`

#### 配置方式（二选一）

- **方式一：通过环境变量配置（推荐）**
  ```bash
  export TWITTER_AUTH_TOKEN="你的 auth_token"
  export TWITTER_CT0="你的 ct0"
  ```

- **方式二：通过配置文件配置**
  复制根目录下的 `cookies.json.example` 为 `cookies.json`：
  ```json
  {
    "auth_token": "你的 auth_token",
    "ct0": "你的 ct0"
  }
  ```
  服务会优先读取环境变量，未设置时读取当前目录下的 `cookies.json`。

---

## 客户端配置示例

### Claude Desktop

在 Claude Desktop 配置文件中添加服务配置：
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "twitter": {
      "command": "python3",
      "args": ["/绝对路径/x-twikit-mcp/server.py"],
      "env": {
        "TWITTER_AUTH_TOKEN": "你的 auth_token",
        "TWITTER_CT0": "你的 ct0"
      }
    }
  }
}
```

### Cursor

在项目目录的 `.cursor/mcp.json` 或全局 Cursor 设置中添加：

```json
{
  "mcpServers": {
    "twitter": {
      "command": "python3",
      "args": ["/绝对路径/x-twikit-mcp/server.py"],
      "env": {
        "TWITTER_AUTH_TOKEN": "你的 auth_token",
        "TWITTER_CT0": "你的 ct0"
      }
    }
  }
}
```

### 通用第三方客户端与 Agent 平台（如 Cherry Studio、Chatbox 等）

多数支持 MCP 协议的可视化客户端或自建 Agent 平台，通常提供“一键粘贴 JSON”或“表单填写”两种添加方式：

#### 方式一：一键粘贴 JSON
在客户端的 JSON 配置框中粘贴以下内容：
```json
{
  "command": "python3",
  "args": ["/绝对路径/x-twikit-mcp/server.py"],
  "env": {
    "TWITTER_AUTH_TOKEN": "你的 auth_token",
    "TWITTER_CT0": "你的 ct0"
  }
}
```
注：若客户端要求完整配置对象，请使用包含 `mcpServers` 顶层键的格式（同上方 Claude Desktop 示例）。

#### 方式二：表单填写
若客户端为表单填写界面，各字段填写对应关系如下：
- **服务名称 / 标识符**：`twitter`（或自定义名称）
- **传输协议 (Transport)**：`stdio`
- **启动命令 (Command)**：`python3`
- **启动参数 (Arguments)**：`/绝对路径/x-twikit-mcp/server.py`
- **环境变量 (Environment)**：
  ```json
  {
    "TWITTER_AUTH_TOKEN": "你的 auth_token",
    "TWITTER_CT0": "你的 ct0"
  }
  ```

---

## 技术实现说明

- 底层通信基于 `twikit` 库调用 X 的 Web GraphQL 接口。
- 针对推文详情中的回复列表读取，内置了层级解析逻辑，用于提取会话线索（Thread）中的各级回复内容。
- 本地认证凭据仅在本地客户端与 X 官方服务器通信时使用，不会上传至第三方服务器。

---

## 常见问题与使用限制

### 1. 网络与代理设置
若处于无法直连 X (Twitter) 的网络环境中，客户端调用可能出现 `ConnectTimeout` 或 `ConnectError`。
可以在客户端配置的环境变量（`env`）中补充代理地址：
```json
"env": {
  "TWITTER_AUTH_TOKEN": "你的 auth_token",
  "TWITTER_CT0": "你的 ct0",
  "HTTP_PROXY": "http://127.0.0.1:7890",
  "HTTPS_PROXY": "http://127.0.0.1:7890"
}
```

### 2. 官方风控与错误码排查
当调用频率过高或触发平台规则时，接口可能返回以下错误码：

| 错误码 / 报错 | 原因说明 | 处理方式 |
| :--- | :--- | :--- |
| `344` (Rate limit) | 发推或回复频率过快，触发当前时间段限额 | 暂停 15 至 30 分钟后再发起请求 |
| `226` (Automated request) | 请求被判定为疑似自动化行为 | 在浏览器中正常访问推特做一次手动互动，或使用注册时间较长的账号 |
| `187` (Status is a duplicate) | 发送了与上一条完全相同的推文内容 | 调整推文内容后再发布 |
| `186` (Tweet needs to be shorter) | 推文字数超出单条上限（普通账号约 280 字符 / 140 个汉字） | 缩减推文内容长度 |
| `88` (Rate limit exceeded) | 搜索或数据读取接口达到频次上限 | 等待约 15 分钟频次重置 |

### 3. 业务场景与环境限制
- **私信权限限制**：若目标用户关闭了陌生人私信接收权限（例如设置为仅允许互关好友或认证用户私信），发送私信会调用失败。
- **接口变更与依赖更新**：底层依赖的 `twikit` 库基于网页端 GraphQL 接口实现。若平台调整接口结构，可运行 `pip install -U twikit` 更新底层库。
- **Python 运行环境路径**：若系统中安装了多个 Python 版本，导致客户端运行时提示 `ModuleNotFoundError: No module named 'twikit'`，请将配置文件中的 `"command": "python3"` 替换为安装了对应依赖的 Python 解释器绝对路径。

---

## 开源协议

本项目采用 [MIT License](LICENSE) 授权。
