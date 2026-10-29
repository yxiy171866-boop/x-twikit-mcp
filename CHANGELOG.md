# 更新日志 (Changelog)

所有针对本项目的重要变动均记录在此文件中。

## [v1.2.1] - 2026-10-29

### 优化与增强
- **私信收件箱全量感知**：`read_direct_messages` 参数 `username` 变为可选。当未指定用户名时，自动拉取私信收件箱（DM Inbox）概览，列出未读私信数、最近会话列表及未读标记。
- **通知中心整合私信统计**：`get_notifications` 在返回的 `summary` 中新增 `dms` 字段，一键同时感知点赞、粉丝、评论/回复与未读私信。

## [v1.2.0] - 2026-10-29

### 新增功能
- **状态感知（通知中心）**：新增 `get_notifications` 工具，支持获取通知概览与列表，包含点赞、新关注者、评论回复、转推统计及对应推文与用户 ID。
- **实时趋势与热门话题**：新增 `get_trends` 工具，支持获取平台热点话题、分类趋势（trending/for-you 等）及推文数与链接。
- **特定关注账号名单（VIP 关注）**：新增 `set_priority_accounts`、`get_priority_accounts` 及 `get_priority_timeline` 三个工具，支持持久化管理重点关注账号并一键聚合抓取其最新推文动态。
- **社交关系管理**：新增关注 `follow_user`、取关 `unfollow_user`、获取粉丝列表 `get_user_followers`、获取正在关注列表 `get_user_following`。
- **书签管理**：新增添加书签 `bookmark_tweet`、移除书签 `unbookmark_tweet`、获取书签列表 `get_bookmarks`。
- **推文引用与分享**：新增引用推文 `quote_tweet`、查询推文引用 `get_tweet_quotes`、通过私信分享推文 `share_tweet_via_dm`。
- **取消互动操作**：新增取消点赞 `unfavorite_tweet` 与取消转推 `unretweet`。
- **多媒体发推支持**：`post_tweet` 与 `reply_tweet` 支持传入本地图片或媒体文件路径列表（`media_paths`），自动上传并附带至推文。
- **高级推文搜索过滤**：`search_tweets` 支持指定发帖人（`from_user`）、时间范围（`since_date` / `until_date`）及最低互动量指标（`min_faves` / `min_retweets` / `min_replies`）。

### 体验与规范优化
- **统一工具响应格式**：所有 29 个工具统一返回结构化 JSON（包含 `status`, `tool`, `message`, `data`, `error` 字段），便于 AI 客户端解析与状态判断。
- **严格失败判定**：当工具执行出现异常或网络问题时，一律返回 `status: "failed"` 与对应错误信息，杜绝误报成功。
- **完整推文指标解析**：`get_tweet_by_id` 数据统计新增收藏数（Bookmarks）与浏览量（Views）。

---

## [v1.1.0] - 2026-10-28

### 新增功能
- **单条推文详情查询**：新增 `get_tweet_by_id` 工具，支持解析推文详情与互动统计。
- **用户主页信息获取**：新增 `get_user_info` 工具，支持获取用户简介、粉丝数与关注数。
- **用户主页推文读取**：新增 `get_user_tweets` 工具，支持直接按用户名获取最新推文，绕过全局搜索索引延迟。

### 优化与修复
- 优化推文评论解析器对 GraphQL 数据层级的兼容性。
- 完善推特官方错误码提示（344 发推频次上限、226 自动化限制）。

---

## [v1.0.0] - 2026-10-28

- 初始版本发布，提供基于 twikit 的 X (Twitter) Model Context Protocol (MCP) 服务，支持 10 个基础工具（发推、回复、读评论、私信、搜索、点赞、转推、删推等）。

