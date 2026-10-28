# 🐦 Twitter (X) MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-brightgreen.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Compatible-purple.svg)](https://modelcontextprotocol.io)

English | [中文说明](#中文说明)

A lightweight, powerful, and **100% free** Model Context Protocol (MCP) server for **X (Twitter)**, powered by [twikit](https://github.com/d60/twikit).

Empower your AI assistants (**Claude Desktop, Cursor, Cline, Open WebUI, D-Home, etc.**) to interact with X in real-time — **without paying $100+/month** for the official Twitter API.

---

## ✨ Features

- ✍️ **Post & Reply**: Post tweets and thread replies.
- 💬 **Comment & Reply Thread Reader**: Read all comments under any tweet with custom GraphQL thread parsing (bypasses twikit's cursor pagination limitations).
- 📨 **Direct Messages (DMs)**: Read conversation histories and send direct messages.
- 🔍 **Search & Discover**: Search recent tweets with keywords, hashtags, or query filters.
- 👤 **Profiles & Timelines**: Inspect user bios, follower counts, and recent user tweets.
- 💖 **Social Actions**: Like (favorite), Retweet, and Delete your tweets.
- 🛡️ **Zero API Fees**: Uses web session cookies (`auth_token` and `ct0`).

---

## 🛠️ Tool Catalog

| Tool Name | Description | Key Parameters |
| :--- | :--- | :--- |
| `post_tweet` | Post a new tweet | `text` |
| `reply_tweet` | Reply to a tweet or comment | `tweet_id`, `text` |
| `get_tweet_replies` | Read all comments/replies under a tweet | `tweet_id`, `count` (default: 10) |
| `read_direct_messages` | Read DM conversation history with a user | `username`, `count` (default: 10) |
| `send_direct_message` | Send or reply to a DM | `username`, `text`, `reply_to_message_id` |
| `search_tweets` | Search tweets by keyword or query | `query`, `count` (default: 10) |
| `get_tweet_by_id` | Get full details & metrics of a tweet | `tweet_id` |
| `get_user_info` | Get user bio, follower stats, etc. | `username` |
| `get_user_tweets` | Fetch recent tweets posted by a user | `username`, `count` (default: 5) |
| `favorite_tweet` | Like a tweet | `tweet_id` |
| `retweet` | Retweet / repost a tweet | `tweet_id` |
| `delete_tweet` | Delete a tweet posted by yourself | `tweet_id` |

---

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/yxiy171866-boop/x-twikit-mcp.git
cd x-twikit-mcp
pip install -r requirements.txt
```

### 2. Get Your Twitter Cookies (in 30 seconds)

You only need **two cookie values**: `auth_token` and `ct0`.

1. Open [x.com](https://x.com) in your browser and log into your account.
2. Press `F12` (or Right-Click -> **Inspect**) to open Developer Tools.
3. Go to the **Application** tab (in Chrome/Edge) or **Storage** tab (in Firefox).
4. Expand **Cookies** on the left and select `https://x.com`.
5. Find and copy the values for:
   - `auth_token`
   - `ct0`

#### Configure your cookies:

**Option A (Recommended): Environment Variables**
```bash
export TWITTER_AUTH_TOKEN="your_auth_token_here"
export TWITTER_CT0="your_ct0_here"
```

**Option B: `cookies.json` file**
Copy `cookies.json.example` to `cookies.json` in the project root:
```json
{
  "auth_token": "your_auth_token_here",
  "ct0": "your_ct0_here"
}
```

---

## 🔌 Client Configuration

### Claude Desktop

Add this to your Claude Desktop configuration file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "twitter": {
      "command": "python3",
      "args": ["/ABSOLUTE/PATH/TO/twitter-mcp-server/server.py"],
      "env": {
        "TWITTER_AUTH_TOKEN": "your_auth_token_here",
        "TWITTER_CT0": "your_ct0_here"
      }
    }
  }
}
```

### Cursor

Add to your project's `.cursor/mcp.json` or Global Cursor Settings:

```json
{
  "mcpServers": {
    "twitter": {
      "command": "python3",
      "args": ["/ABSOLUTE/PATH/TO/twitter-mcp-server/server.py"],
      "env": {
        "TWITTER_AUTH_TOKEN": "your_auth_token_here",
        "TWITTER_CT0": "your_ct0_here"
      }
    }
  }
}
```

---

## 🔒 Security & Privacy

- **Your credentials stay local**: Cookies are only used locally on your machine to communicate directly with X's servers. No proxies, no external telemetry, no remote logging.
- **`.gitignore` protection**: `cookies.json` is automatically ignored to prevent accidental leaks.
- **Account recommendation**: For production autonomous bots, we recommend using a dedicated secondary account or a verified phone-linked account to avoid strict rate-limiting.

---

<br>

<h2 id="中文说明">📖 中文说明</h2>

这是一个专为大语言模型打造的 **X (Twitter) MCP 插件服务**。基于 Python 与 `twikit` 逆向 Web 接口，**无需申请 X 官方昂贵的高门槛 API（官方基础套餐每月需 \$100）**，仅凭普通账号的网页 Session Cookie 即可让 Claude、Cursor、Cline 等 AI 助手完全掌控推特能力！

### 核心亮点
- **功能齐全**：支持发推、回复评论、查看帖子下全部评论、读写私信、搜索推文、抓取主页与点赞。
- **专项 Bug 绕过**：针对 twikit 原版在读取推文评论（`tweet_detail`）时游标分页丢失的问题，内置定制化 GraphQL 解析，能完整读取推文下的所有回复与评论。
- **免密部署**：支持环境变量注入与本地 `cookies.json`，支持浏览器插件导出的 Cookie 格式。
- **优雅风控处理**：内建 344（发推频次限额）、226（防机械拦截）等友好错误提醒。

### 快速获取 Cookies
1. 电脑浏览器打开并登录 [x.com](https://x.com)。
2. 按 `F12` 键打开开发者工具 -> 切换到 **Application（应用）** 标签页。
3. 在左侧展开 **Cookies** -> 点击 `https://x.com`。
4. 在表格中找到并复制 `auth_token` 与 `ct0` 两个字段的值。
5. 在项目根目录复制 `cookies.json.example` 为 `cookies.json` 填入即可。

---

## 📄 License

This project is open-source under the [MIT License](LICENSE).

