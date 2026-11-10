# 更新日志 (Changelog)

所有针对本项目的重要变动均记录在此文件中。

## [v1.2.5] - 2026-11-10

### 兼容性与易用性增强
- **推文链接/URL 自动正则解析支持**：所有推文相关工具（`get_tweet_by_id`, `get_tweet_replies`, `get_tweet_quotes`, `reply_tweet`, `quote_tweet`, `delete_tweet`, `favorite_tweet`, `retweet`, `bookmark_tweet`, `share_tweet_via_dm` 等）全面支持直接传入推文 URL（如 `https://x.com/username/status/123456789...` 或带参数的移动端分享链接），自动提取纯数字 ID，无需客户端或 AI 手动剥离。
- **GraphQL 用户信息提取规范升级 (core 字段兼容)**：适配 Twitter 最新 GraphQL 结构变动（作者信息从 `legacy` 移入 `core.user_results.result.core`），重构 `_extract_user_info`，解决搜索推文、推文详情及回复解析中 `author` 偶发返回 `unknown` 或 `null` 的问题。
- **用户特定搜索兜底与时间线回退检索**：针对 Twitter `SearchTimeline` 端点在特定关键词或频次下返回 404 或空列表的问题，在 `search_tweets` 中新增对 `from_user` 或 `from:username` 语法的主页时间线智能回退检索，保障用户推文检索的高可用性。
- **长推文 (Note Tweets) 全文提取兼容**：`get_tweet_by_id` 增加对 `note_tweet_results` 长文推文格式的深度解析，确保长推文不被截断，返回完整全文。

## [v1.2.4] - 2026-11-09

### 兼容性与稳定性修复
- **修复 Twitter Webpack Chunk 拆分导致的 KEY_BYTE indices 提取失败**：适配 X 官方前端 JavaScript 打包规则更新，在 `server.py` 内置运行时热补丁（两步解析映射），彻底解决原版 `twikit` 报错 `Couldn't get KEY_BYTE indices` 导致所有请求无法发出的问题。
- **修复用户资料解析 KeyError 崩溃**：针对 X 接口有时不返回 `entities.description.urls`、`pinned_tweet_ids_str` 或 `description` 的情况，在 `server.py` 内置 `User.__init__` 安全兜底补丁，避免解析用户资料时触发 `KeyError`。
- **依赖源更新为社区维护分支**：在 `requirements.txt` 中将依赖明确指向修复分支 `git+https://github.com/unclecode/twikit.git`，并在 `README.md` 中完善环境安装与依赖版本说明。

## [v1.2.3] - 2026-10-31

### 性能与防风控优化
- **全局 Client 会话单例持久复用**：将每次工具调用的新建 Client 重构为进程内单例缓存（`get_client`），彻底消除每次调用重复握手 `x.com` 与拉取 1.2MB 前端动态 JS 的开销，大幅降低延迟并防止高频调用被 Twitter 反爬风控拦截（如错误码 344）。
- **完善异常格式化与错误吞没修复**：新增 `_format_error` 辅助函数，解决部分 Twikit 内置异常转字符串为空（如 `ReadTimeout` 或部分 `TwitterException` 导致提示信息空白）的问题，并在失败返回中强制兜底错误信息。
- **连续写入动作安全缓冲**：在发推、回复、转推和点赞操作前加入平滑安全微延迟，有效避免短时间内迸发写入请求触发速率限制。

## [v1.2.2] - 2026-10-31

### 修复与优化
- **修复 Twitter 动态端点 404 导致转推失败的问题**：适配 Twitter/X 最新 GraphQL Query ID（涵盖 `CreateRetweet`, `DeleteRetweet`, `SearchTimeline`, `CreateTweet`），解决因官方哈希轮换导致的转推 404 报错。
- **优化转推与取消转推的错误校验**：直接调用底层 GraphQL 接口并深度解析 Twitter 返回的业务级错误（如推文不存在、已被删除等），提供精准的错误反馈与状态返回。
- **发推文档提示补充**：在 `post_tweet` 提示中增加 `@username` 提及用法的说明。

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

