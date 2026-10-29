# X (Twitter) MCP 服务

[![Version](https://img.shields.io/badge/version-v1.2.0-blue.svg)](CHANGELOG.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-brightgreen.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Compatible-purple.svg)](https://modelcontextprotocol.io)

本项目是基于 [twikit](https://github.com/d60/twikit) 实现的 Model Context Protocol (MCP) 服务，专门为 AI 助手、大语言模型及各类 AI Agent 提供与 X (Twitter) 交互的能力。通过本服务，AI 能够自主调用工具完成状态感知、发推（含图片）、读写评论、收发私信、关注互动、趋势发现以及重点账号追踪等全流程操作。

服务通过普通账号的浏览器 Cookie（`auth_token` 与 `ct0`）与 X 官方 Web 端通信。所有工具统一采用结构化 JSON 响应，确保状态判定与字段解析的稳定性。

---

## 功能列表

服务目前为 AI 助手提供以下 29 个 MCP 工具，按模块划分如下：

### 1. 推文发布与社交互动

| 工具名称 | 功能描述 | 参数 |
| :--- | :--- | :--- |
| `post_tweet` | 发布新推文（支持带本地图片/媒体） | `text`（推文文字）, `media_paths`（可选，图片文件路径或路径列表） |
| `reply_tweet` | 回复指定推文或评论（支持带图片） | `tweet_id`（目标推文 ID）, `text`（回复文字）, `media_paths`（可选） |
| `quote_tweet` | 引用转发推文（Quote Tweet） | `tweet_id`（目标推文 ID）, `text`（评论文字）, `media_paths`（可选） |
| `delete_tweet` | 删除自己发布的推文 | `tweet_id`（推文 ID） |
| `favorite_tweet` | 点赞指定推文 | `tweet_id`（推文 ID） |
| `unfavorite_tweet` | 取消对推文的点赞 | `tweet_id`（推文 ID） |
| `retweet` | 转发/转推指定推文 | `tweet_id`（推文 ID） |
| `unretweet` | 取消对推文的转推 | `tweet_id`（原推文 ID） |
| `bookmark_tweet` | 收藏指定推文到书签 | `tweet_id`（推文 ID） |
| `unbookmark_tweet` | 从书签中移除指定推文 | `tweet_id`（推文 ID） |
| `get_bookmarks` | 查看当前账号保存的书签推文列表 | `count`（获取数量，默认 10，最大 40） |

### 2. 推文与评论检索

| 工具名称 | 功能描述 | 参数 |
| :--- | :--- | :--- |
| `get_tweet_by_id` | 获取单条推文详情与全面统计（点赞、收藏、转推、回复、浏览量） | `tweet_id`（推文 ID） |
| `get_tweet_replies` | 获取指定推文下方的评论与回复列表（定制 GraphQL 线程解析） | `tweet_id`（推文 ID）, `count`（获取数量，默认 10，最大 50） |
| `get_tweet_quotes` | 获取引用转发该推文的推文列表 | `tweet_id`（推文 ID）, `count`（获取数量，默认 10，最大 20） |
| `search_tweets` | 高级推文搜索（支持关键词、作者、时间范围及互动量门槛） | `query`（关键词）, `count`（默认 10）, `from_user`（可选作者）, `since_date`（起始日期 YYYY-MM-DD）, `until_date`（截止日期）, `min_faves`（最低点赞数）, `min_retweets`（最低转推数）, `min_replies`（最低回复数） |

### 3. 用户资料与社交关系

| 工具名称 | 功能描述 | 参数 |
| :--- | :--- | :--- |
| `get_user_info` | 获取指定用户的个人资料及粉丝、关注数等统计 | `username`（用户名，可带或不带 @） |
| `get_user_tweets` | 获取指定用户最近发布的推文列表 | `username`（用户名）, `count`（获取数量，默认 5，最大 20） |
| `get_user_followers` | 获取指定用户的粉丝（关注者）列表 | `username`（用户名或用户 ID）, `count`（默认 20，最大 50） |
| `get_user_following` | 获取指定用户正在关注的用户列表 | `username`（用户名或用户 ID）, `count`（默认 20，最大 50） |
| `follow_user` | 关注指定用户 | `username`（用户名或用户 ID） |
| `unfollow_user` | 取消关注指定用户 | `username`（用户名或用户 ID） |

### 4. 状态感知与趋势发现

| 工具名称 | 功能描述 | 参数 |
| :--- | :--- | :--- |
| `get_notifications` | 感知全部状态（通知中心：汇总点赞、新粉丝、回复提及，含具体对象 ID） | `category`（分类：'All', 'Verified', 'Mentions'，默认 'All'）, `count`（默认 15，最大 40） |
| `get_trends` | 查看实时热门话题与趋势榜单 | `category`（分类：'trending', 'for-you', 'news', 'sports', 'entertainment'，默认 'trending'）, `count`（默认 20，最大 50） |

### 5. 私信交流与推文分享

| 工具名称 | 功能描述 | 参数 |
| :--- | :--- | :--- |
| `read_direct_messages` | 获取与指定用户的私信聊天记录，或查看私信收件箱概览 | `username`（可选，留空则获取私信收件箱概览及未读会话）, `count`（默认 10，最大 30） |
| `send_direct_message` | 向指定用户发送或回复私信 | `username`（目标用户名）, `text`（私信内容）, `reply_to_message_id`（可选） |
| `share_tweet_via_dm` | 通过私信将推文卡片分享给指定用户 | `username`（接收人用户名）, `tweet_id`（分享推文 ID）, `comment`（可选附带留言） |

### 6. 特定关注账号追踪 (VIP Watchlist)

| 工具名称 | 功能描述 | 参数 |
| :--- | :--- | :--- |
| `set_priority_accounts` | 设置特定优先关注账号名单 | `usernames`（用户名或逗号分隔列表）, `mode`（'add' 增加, 'remove' 移除, 'replace' 覆盖） |
| `get_priority_accounts` | 查看当前已设置的特定优先关注账号名单 | 无 |
| `get_priority_timeline` | 一键聚合抓取所有特定关注账号的最新推文动态 | `count_per_user`（每个账号抓取推文数，默认 3，最大 10） |

---

## 统一响应数据结构

所有工具的返回值均采用规范的 JSON 文本格式输出，便于大语言模型进行条件判断与进一步工具链编排：

```json
{
  "status": "success",
  "tool": "get_notifications",
  "message": "最新通知感知概览 (共 6 条)：点赞 3 条 | 新粉丝 1 人 | 回复 2 条",
  "data": {
    "total": 6,
    "summary": { "likes": 3, "follows": 1, "replies": 2 },
    "notifications": [
      {
        "id": "HVdLtUjaAAAAAAABSQ3bEYMUcp7plCkwmRQ",
        "type": "like",
        "message": "UserA liked your post",
        "from_user": { "screen_name": "UserA", "name": "Alice", "id": "123456" },
        "tweet": { "id": "2115110580302557481", "text": "Hello world" },
        "timestamp_ms": "1730100000000"
      }
    ]
  }
}
```

若操作遇到错误、网络超时或触发限额，返回格式严格标明失败状态，避免误报成功：

```json
{
  "status": "failed",
  "tool": "follow_user",
  "message": "关注用户失败: User @invalid_name not found.",
  "error": "User not found"
}
```

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

1. 在电脑浏览器中打开并登录 [x.com](https://x.com)。
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

#### 方式二：表单填写
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
- **依赖库更新**：底层依赖的 `twikit` 库基于网页端 GraphQL 接口实现。若平台调整接口结构，可运行 `pip install -U twikit` 更新底层库。
- **本地环境与路径**：若系统中安装了多个 Python 版本，导致提示 `ModuleNotFoundError: No module named 'twikit'`，请将配置文件中的 `"command": "python3"` 替换为安装了对应依赖的 Python 解释器绝对路径。

---

## 更新日志

详情可参考 [CHANGELOG.md](CHANGELOG.md)。
- **v1.2.0 (2026-10-29)**: 新增通知感知、热门趋势、重点关注账号名单（VIP Watchlist）、关注/取关、粉丝/关注列表读取、书签管理、引用推文、私信分享推文、图片多媒体发推、高级搜索过滤条件，统一 29 个工具的结构化 JSON 返回规范。
- **v1.1.0 (2026-10-28)**: 增加单条推文全指标详情查询（含收藏与浏览量）、用户主页资料与用户推文精准抓取，优化 GraphQL 回复线程解析。
- **v1.0.0 (2026-10-28)**: 首个公开版本发布，提供发推、回复、读评、私信与基础搜索能力。

---

## 开源协议

本项目采用 [MIT License](LICENSE) 授权。
