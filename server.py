import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Optional, Union, Any
from mcp.server.mcpserver import MCPServer
from twikit import Client
from twikit.tweet import Tweet
import twikit.client.gql

# Patch Twitter/X GraphQL dynamic query IDs to prevent 404 errors from API updates
twikit.client.gql.Endpoint.CREATE_RETWEET = 'https://x.com/i/api/graphql/mbRO74GrOvSfRcJnlMapnQ/CreateRetweet'
twikit.client.gql.Endpoint.DELETE_RETWEET = 'https://x.com/i/api/graphql/ZyZigVsNiFO6v1dEks1eWg/DeleteRetweet'
twikit.client.gql.Endpoint.SEARCH_TIMELINE = 'https://x.com/i/api/graphql/3fEctOs2-FvTB7_mvm1hrQ/SearchTimeline'
twikit.client.gql.Endpoint.CREATE_TWEET = 'https://x.com/i/api/graphql/l4hk8uVGvR-a8kzQ4nOhPA/CreateTweet'

mcp = MCPServer("x-twikit")


def _format_error(exc: Any) -> str:
    """Safely format exception to non-empty human-readable string."""
    if not exc:
        return "未知异常"
    msg = str(exc).strip()
    if not msg:
        msg = getattr(exc, "message", None) or repr(exc)
    return str(msg)


def _format_res(
    success: bool,
    tool: str,
    message: str,
    data: Any = None,
    error: Optional[str] = None
) -> str:
    """Format unified JSON structure for all MCP tools.

    Guarantees standard fields for reliable AI parsing:
    - status: 'success' | 'failed'
    - tool: tool name string
    - message: human-readable summary
    - data: structured data object/list (if available)
    - error: error explanation (only when status is 'failed')
    """
    res = {
        "status": "success" if success else "failed",
        "tool": tool,
        "message": message,
    }
    if data is not None:
        res["data"] = data
    if error is not None:
        err_str = str(error).strip()
        if not err_str:
            err_str = message
        res["error"] = err_str
    elif not success:
        res["error"] = message
    return json.dumps(res, ensure_ascii=False, indent=2)


def _resolve_cookies() -> dict[str, str]:
    """Resolve Twitter authentication cookies (auth_token & ct0).

    Resolution priority:
    1. Environment variables: TWITTER_AUTH_TOKEN and TWITTER_CT0
    2. Path specified in TWITTER_COOKIES_PATH environment variable
    3. Default local file: ./cookies.json
    4. Sibling directory cookies.json
    5. Fallback default tokens
    """
    env_auth = os.environ.get("TWITTER_AUTH_TOKEN", "").strip()
    env_ct0 = os.environ.get("TWITTER_CT0", "").strip()
    if env_auth and env_ct0:
        return {"auth_token": env_auth, "ct0": env_ct0}

    cookie_file = os.environ.get("TWITTER_COOKIES_PATH", "").strip()
    candidate_paths = []
    if cookie_file:
        candidate_paths.append(Path(cookie_file))

    candidate_paths.append(Path.cwd() / "cookies.json")
    candidate_paths.append(Path(__file__).resolve().parent / "cookies.json")

    for path in candidate_paths:
        if path.exists() and path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if isinstance(data, dict):
                    auth_token = data.get("auth_token", "")
                    ct0 = data.get("ct0", "")
                    if auth_token and ct0:
                        return {"auth_token": auth_token, "ct0": ct0}

                if isinstance(data, list):
                    cookie_dict = {}
                    for item in data:
                        name = item.get("name")
                        val = item.get("value")
                        if name in ("auth_token", "ct0") and val:
                            cookie_dict[name] = val
                    if "auth_token" in cookie_dict and "ct0" in cookie_dict:
                        return cookie_dict
            except Exception as e:
                print(f"[Warning] Failed to read cookie file at {path}: {e}", file=sys.stderr)

    return {}


_client_instance: Optional[Client] = None


def reset_client() -> None:
    """Clear cached Client session (e.g. after auth error or cookie refresh)."""
    global _client_instance
    _client_instance = None


def get_client() -> Client:
    """Initialize and return an authenticated Twikit Client (singleton session)."""
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    cookies = _resolve_cookies()
    if not cookies or not cookies.get("auth_token") or not cookies.get("ct0"):
        raise RuntimeError(
            "Twitter cookies are not configured! Please provide TWITTER_AUTH_TOKEN and TWITTER_CT0 "
            "as environment variables, or create a 'cookies.json' file with {\"auth_token\": \"...\", \"ct0\": \"...\"}."
        )

    client = Client("en-US")
    client.set_cookies(cookies)
    _client_instance = client
    return _client_instance


async def _resolve_user_id(client: Client, identifier: str) -> tuple[str, str]:
    """Resolve screen_name or numeric ID to (user_id, screen_name)."""
    clean_id = (identifier or "").strip().lstrip("@")
    if not clean_id:
        raise ValueError("Username or User ID cannot be empty.")
    if clean_id.isdigit():
        return clean_id, clean_id
    user = await client.get_user_by_screen_name(clean_id)
    if not user:
        raise ValueError(f"User @{clean_id} not found.")
    return str(user.id), user.screen_name


async def _get_my_user_id(client: Client) -> str:
    """Safely obtain the current authenticated user's ID without triggering 404 on settings.json."""
    if hasattr(client, "_cached_my_id") and client._cached_my_id:
        return client._cached_my_id

    # Strategy 1: Find common participant across conversations in DM inbox
    try:
        import twikit.client.v11 as v11
        dm_res, _ = await client.v11.base.get(
            v11.Endpoint.DM_INBOX,
            headers=client.v11.base._base_headers
        )
        if isinstance(dm_res, dict):
            inbox = dm_res.get("inbox_initial_state", {})
            convs = inbox.get("conversations", {})
            part_sets = [set(str(p.get("user_id", "")) for p in item.get("participants", [])) for item in convs.values()]
            if part_sets:
                common = set.intersection(*part_sets)
                if common:
                    uid = str(list(common)[0])
                    client._cached_my_id = uid
                    return uid
    except Exception:
        pass

    # Strategy 2: Attempt client.v11.settings()
    try:
        res, _ = await client.v11.settings()
        sn = res.get("screen_name")
        if sn:
            uid, _ = await _resolve_user_id(client, sn)
            client._cached_my_id = str(uid)
            return str(uid)
    except Exception:
        pass

    # Strategy 3: Standard client.user_id()
    uid = str(await client.user_id())
    client._cached_my_id = uid
    return uid


async def _expand_tco_links(text: str) -> str:
    """Expand short t.co links in text to full target URLs."""
    import re, httpx
    if not text or "t.co/" not in text:
        return text or ""
    urls = re.findall(r"https?://t\.co/[a-zA-Z0-9]+", text)
    if not urls:
        return text
    expanded_map = {}
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=5.0) as http_client:
            for u in set(urls):
                try:
                    r = await http_client.head(u)
                    target = str(r.url)
                    if target != u:
                        expanded_map[u] = target
                except Exception:
                    try:
                        r = await http_client.get(u)
                        target = str(r.url)
                        if target != u:
                            expanded_map[u] = target
                    except Exception:
                        pass
    except Exception:
        pass

    for short_u, full_u in expanded_map.items():
        text = text.replace(short_u, f"{short_u} ({full_u})")
    return text


def _format_timestamp(ts: Any) -> str:
    """Format millisecond or second timestamp to Asia/Shanghai human-readable datetime string."""
    import datetime
    if not ts:
        return ""
    try:
        ts_num = float(ts)
        if ts_num > 1e11:  # Milliseconds
            ts_num = ts_num / 1000.0
        tz = datetime.timezone(datetime.timedelta(hours=8))
        dt = datetime.datetime.fromtimestamp(ts_num, tz)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)


async def _upload_media_files(client: Client, media_paths: Optional[Union[list, str]]) -> list[str]:
    """Upload media files and return list of media IDs."""
    if not media_paths:
        return []
    if isinstance(media_paths, str):
        paths = [p.strip() for p in media_paths.split(",") if p.strip()]
    else:
        paths = [str(p).strip() for p in media_paths if str(p).strip()]

    media_ids = []
    for p_str in paths:
        path = Path(p_str)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Media file not found: {p_str}")
        media_id = await client.upload_media(str(path.resolve()), wait_for_completion=True)
        media_ids.append(str(media_id))
    return media_ids


def _get_priority_config_path() -> Path:
    """Return the file path for priority accounts watchlist."""
    base_dir = Path(__file__).resolve().parent
    return base_dir / "priority_accounts.json"


# -------------------------------------------------------------
# 1. Tweet Creation & Social Actions
# -------------------------------------------------------------

@mcp.tool()
async def post_tweet(text: str, media_paths: Optional[Union[list[str], str]] = None) -> str:
    """Post a new tweet to X (Twitter), with optional images/media attachments.

    Parameters:
    - text: Content of the tweet to post. You can mention users by including @username in the text (e.g. '@Shellyiii7777 早安！').
    - media_paths: Optional list of local file paths (or comma-separated string) for images/media to attach.
    """
    text = (text or "").strip()
    if not text and not media_paths:
        return _format_res(False, "post_tweet", "发推失败：推文内容与媒体附件不能同时为空", error="Empty tweet text and media")
    try:
        await asyncio.sleep(1.0)
        client = get_client()
        media_ids = await _upload_media_files(client, media_paths) if media_paths else None
        tweet = await client.create_tweet(text=text, media_ids=media_ids)
        tweet_id = getattr(tweet, "id", None) or "posted"
        url = f"https://x.com/i/status/{tweet_id}"
        return _format_res(
            True, "post_tweet", f"推文发布成功！推文链接: {url}",
            data={"tweet_id": str(tweet_id), "url": url, "text": text, "media_count": len(media_ids or [])}
        )
    except Exception as exc:
        err_msg = _format_error(exc)
        if "344" in err_msg:
            err_msg = "触发了 X 账号发推频次上限（错误码 344），请等待冷却数小时后再试。"
        elif "226" in err_msg:
            err_msg = "触发了 X 自动化安全拦截（错误码 226），请调整文案避免重复。"
        return _format_res(False, "post_tweet", f"发推失败: {err_msg}", error=err_msg)


@mcp.tool()
async def reply_tweet(tweet_id: str, text: str, media_paths: Optional[Union[list[str], str]] = None) -> str:
    """Reply to an existing tweet or comment on X (Twitter), with optional media.

    Parameters:
    - tweet_id: The ID of the tweet or comment to reply to.
    - text: Content of your reply.
    - media_paths: Optional list of local file paths (or comma-separated string) for images to attach.
    """
    tweet_id = str(tweet_id or "").strip()
    text = (text or "").strip()
    if not tweet_id:
        return _format_res(False, "reply_tweet", "回复失败：tweet_id 不能为空", error="Empty tweet_id")
    if not text and not media_paths:
        return _format_res(False, "reply_tweet", "回复失败：回复内容与媒体附件不能同时为空", error="Empty text and media")
    try:
        await asyncio.sleep(1.0)
        client = get_client()
        media_ids = await _upload_media_files(client, media_paths) if media_paths else None
        reply = await client.create_tweet(text=text, reply_to=tweet_id, media_ids=media_ids)
        reply_id = getattr(reply, "id", None) or "posted"
        url = f"https://x.com/i/status/{reply_id}"
        return _format_res(
            True, "reply_tweet", f"回复成功！回复推文链接: {url}",
            data={"reply_id": str(reply_id), "target_tweet_id": tweet_id, "url": url, "text": text}
        )
    except Exception as exc:
        err_msg = _format_error(exc)
        if "344" in err_msg:
            err_msg = "触发了 X 回复频次限制（错误码 344），请稍后再试。"
        return _format_res(False, "reply_tweet", f"回复失败: {err_msg}", error=err_msg)


@mcp.tool()
async def quote_tweet(tweet_id: str, text: str, media_paths: Optional[Union[list[str], str]] = None) -> str:
    """Quote tweet (retweet with your own commentary) an existing tweet.

    Parameters:
    - tweet_id: The ID of the tweet to quote.
    - text: Your commentary text for the quote tweet.
    - media_paths: Optional list of local file paths for images to attach.
    """
    tweet_id = str(tweet_id or "").strip()
    text = (text or "").strip()
    if not tweet_id:
        return _format_res(False, "quote_tweet", "引用推文失败：tweet_id 不能为空", error="Empty tweet_id")
    try:
        client = get_client()
        media_ids = await _upload_media_files(client, media_paths) if media_paths else None
        target_url = f"https://x.com/i/status/{tweet_id}"
        quote = await client.create_tweet(text=text, attachment_url=target_url, media_ids=media_ids)
        quote_id = getattr(quote, "id", None) or "posted"
        url = f"https://x.com/i/status/{quote_id}"
        return _format_res(
            True, "quote_tweet", f"引用推文成功！新推文链接: {url}",
            data={"quote_tweet_id": str(quote_id), "quoted_tweet_id": tweet_id, "url": url, "text": text}
        )
    except Exception as exc:
        return _format_res(False, "quote_tweet", f"引用推文失败: {exc}", error=str(exc))


@mcp.tool()
async def delete_tweet(tweet_id: str) -> str:
    """Delete a tweet posted by yourself by its ID.

    Parameters:
    - tweet_id: ID of the tweet to delete.
    """
    tweet_id = str(tweet_id or "").strip()
    if not tweet_id:
        return _format_res(False, "delete_tweet", "删除推文失败：tweet_id 不能为空", error="Empty tweet_id")
    try:
        client = get_client()
        await client.delete_tweet(tweet_id)
        return _format_res(True, "delete_tweet", f"推文 {tweet_id} 已成功删除", data={"deleted_tweet_id": tweet_id})
    except Exception as exc:
        return _format_res(False, "delete_tweet", f"删除推文失败: {exc}", error=str(exc))


@mcp.tool()
async def favorite_tweet(tweet_id: str) -> str:
    """Like / favorite a tweet by its ID.

    Parameters:
    - tweet_id: ID of the tweet to like.
    """
    tweet_id = str(tweet_id or "").strip()
    if not tweet_id:
        return _format_res(False, "favorite_tweet", "点赞失败：tweet_id 不能为空", error="Empty tweet_id")
    try:
        await asyncio.sleep(0.5)
        client = get_client()
        await client.favorite_tweet(tweet_id)
        return _format_res(True, "favorite_tweet", f"点赞成功！推文 ID: {tweet_id}", data={"tweet_id": tweet_id, "liked": True})
    except Exception as exc:
        err_msg = _format_error(exc)
        return _format_res(False, "favorite_tweet", f"点赞失败: {err_msg}", error=err_msg)


@mcp.tool()
async def unfavorite_tweet(tweet_id: str) -> str:
    """Unlike / remove favorite from a tweet by its ID.

    Parameters:
    - tweet_id: ID of the tweet to unlike.
    """
    tweet_id = str(tweet_id or "").strip()
    if not tweet_id:
        return _format_res(False, "unfavorite_tweet", "取消点赞失败：tweet_id 不能为空", error="Empty tweet_id")
    try:
        client = get_client()
        await client.unfavorite_tweet(tweet_id)
        return _format_res(True, "unfavorite_tweet", f"已取消对推文 {tweet_id} 的点赞", data={"tweet_id": tweet_id, "liked": False})
    except Exception as exc:
        err_msg = _format_error(exc)
        return _format_res(False, "unfavorite_tweet", f"取消点赞失败: {err_msg}", error=err_msg)


@mcp.tool()
async def retweet(tweet_id: str) -> str:
    """Retweet / repost a tweet by its ID.

    Parameters:
    - tweet_id: ID of the tweet to retweet.
    """
    tweet_id = str(tweet_id or "").strip()
    if not tweet_id:
        return _format_res(False, "retweet", "转推失败：tweet_id 不能为空", error="Empty tweet_id")
    try:
        await asyncio.sleep(0.5)
        client = get_client()
        data, response = await client.gql.retweet(tweet_id)
        if isinstance(data, dict):
            errors = data.get("errors") or []
            if errors:
                err_msg = errors[0].get("message") or str(errors[0])
                return _format_res(False, "retweet", f"转推失败: {err_msg}", error=err_msg)
            res_data = data.get("data", {}).get("create_retweet", {})
            if not res_data:
                return _format_res(False, "retweet", "转推失败：推文不存在或已被删除", error="No retweet result returned")
        return _format_res(True, "retweet", f"转推成功！推文 ID: {tweet_id}", data={"tweet_id": tweet_id, "retweeted": True})
    except Exception as exc:
        err_msg = _format_error(exc)
        return _format_res(False, "retweet", f"转推失败: {err_msg}", error=err_msg)


@mcp.tool()
async def unretweet(tweet_id: str) -> str:
    """Delete a retweet / undo repost by the original tweet ID.

    Parameters:
    - tweet_id: Original ID of the tweet you retweeted.
    """
    tweet_id = str(tweet_id or "").strip()
    if not tweet_id:
        return _format_res(False, "unretweet", "取消转推失败：tweet_id 不能为空", error="Empty tweet_id")
    try:
        client = get_client()
        data, response = await client.gql.delete_retweet(tweet_id)
        if isinstance(data, dict):
            errors = data.get("errors") or []
            if errors:
                err_msg = errors[0].get("message") or str(errors[0])
                return _format_res(False, "unretweet", f"取消转推失败: {err_msg}", error=err_msg)
        return _format_res(True, "unretweet", f"已取消转推推文 {tweet_id}", data={"tweet_id": tweet_id, "retweeted": False})
    except Exception as exc:
        return _format_res(False, "unretweet", f"取消转推失败: {exc}", error=str(exc))


@mcp.tool()
async def bookmark_tweet(tweet_id: str) -> str:
    """Bookmark / save a tweet by its ID.

    Parameters:
    - tweet_id: ID of the tweet to save to bookmarks.
    """
    tweet_id = str(tweet_id or "").strip()
    if not tweet_id:
        return _format_res(False, "bookmark_tweet", "收藏失败：tweet_id 不能为空", error="Empty tweet_id")
    try:
        client = get_client()
        await client.bookmark_tweet(tweet_id)
        return _format_res(True, "bookmark_tweet", f"推文 {tweet_id} 已成功加入书签收藏", data={"tweet_id": tweet_id, "bookmarked": True})
    except Exception as exc:
        return _format_res(False, "bookmark_tweet", f"收藏失败: {exc}", error=str(exc))


@mcp.tool()
async def unbookmark_tweet(tweet_id: str) -> str:
    """Remove a tweet from bookmarks by its ID.

    Parameters:
    - tweet_id: ID of the tweet to remove from bookmarks.
    """
    tweet_id = str(tweet_id or "").strip()
    if not tweet_id:
        return _format_res(False, "unbookmark_tweet", "移除书签失败：tweet_id 不能为空", error="Empty tweet_id")
    try:
        client = get_client()
        await client.delete_bookmark(tweet_id)
        return _format_res(True, "unbookmark_tweet", f"推文 {tweet_id} 已成功从书签中移除", data={"tweet_id": tweet_id, "bookmarked": False})
    except Exception as exc:
        return _format_res(False, "unbookmark_tweet", f"移除书签失败: {exc}", error=str(exc))


@mcp.tool()
async def get_bookmarks(count: int = 10) -> str:
    """Get the list of tweets saved in your bookmarks.

    Parameters:
    - count: Number of bookmarked tweets to retrieve (default: 10, max: 40).
    """
    try:
        client = get_client()
        count = max(1, min(int(count or 10), 40))
        bookmarks = await client.get_bookmarks(count=count)
        items = []
        for t in list(bookmarks)[:count]:
            user = getattr(t, "user", None)
            screen_name = getattr(user, "screen_name", "unknown") if user else "unknown"
            items.append({
                "tweet_id": str(getattr(t, "id", "")),
                "author": screen_name,
                "created_at": getattr(t, "created_at", ""),
                "text": getattr(t, "text", ""),
                "url": f"https://x.com/i/status/{getattr(t, 'id', '')}"
            })
        return _format_res(
            True, "get_bookmarks", f"成功获取 {len(items)} 条书签推文",
            data={"total": len(items), "bookmarks": items}
        )
    except Exception as exc:
        return _format_res(False, "get_bookmarks", f"获取书签失败: {exc}", error=str(exc))


# -------------------------------------------------------------
# 2. Reading Tweets, Threads, Quotes & User Profiles
# -------------------------------------------------------------

@mcp.tool()
async def get_tweet_by_id(tweet_id: str) -> str:
    """Get comprehensive details and live metrics of a specific tweet by its ID.

    Returns stats including Likes, Bookmarks, Retweets, Replies, and Views.

    Parameters:
    - tweet_id: The unique ID of the tweet.
    """
    tweet_id = str(tweet_id or "").strip()
    if not tweet_id:
        return _format_res(False, "get_tweet_by_id", "查询失败：tweet_id 不能为空", error="Empty tweet_id")
    try:
        client = get_client()
        # Direct GraphQL detail parser
        gql_res = await client.gql.tweet_detail(tweet_id, None)
        data = gql_res[0] if isinstance(gql_res, tuple) else gql_res
        instructions = (
            data.get("data", {})
            .get("threaded_conversation_with_injections_v2", {})
            .get("instructions", [])
        )
        for inst in instructions:
            for entry in inst.get("entries", []):
                item_content = entry.get("content", {}).get("itemContent", {})
                tweet_results = item_content.get("tweet_results", {}).get("result", {})
                if tweet_results:
                    rest_id = tweet_results.get("rest_id") or tweet_results.get("id")
                    if str(rest_id) == str(tweet_id):
                        legacy = tweet_results.get("legacy", {})
                        core_user = tweet_results.get("core", {}).get("user_results", {}).get("result", {}).get("legacy", {})
                        screen_name = core_user.get("screen_name") or "unknown"
                        name = core_user.get("name") or ""
                        created_at = legacy.get("created_at") or ""
                        fav_count = legacy.get("favorite_count", 0)
                        retweet_count = legacy.get("retweet_count", 0)
                        reply_count = legacy.get("reply_count", 0)
                        bookmark_count = legacy.get("bookmark_count", 0)
                        views_obj = tweet_results.get("views", {})
                        views_count = views_obj.get("count", "0") if isinstance(views_obj, dict) else "0"
                        full_text = legacy.get("full_text") or ""
                        url = f"https://x.com/i/status/{tweet_id}"

                        stats = {
                            "likes": fav_count,
                            "bookmarks": bookmark_count,
                            "retweets": retweet_count,
                            "replies": reply_count,
                            "views": views_count,
                        }
                        return _format_res(
                            True, "get_tweet_by_id", f"成功获取推文 {tweet_id} 详情",
                            data={
                                "tweet_id": tweet_id,
                                "author": screen_name,
                                "author_name": name,
                                "created_at": created_at,
                                "text": full_text,
                                "stats": stats,
                                "url": url
                            }
                        )

        return _format_res(False, "get_tweet_by_id", f"未找到推文 {tweet_id}", error="Tweet not found")
    except Exception as exc:
        return _format_res(False, "get_tweet_by_id", f"获取推文失败: {exc}", error=str(exc))


@mcp.tool()
async def get_tweet_replies(tweet_id: str, count: int = 10) -> str:
    """Retrieve all replies and comments under a specific tweet thread.

    Custom GraphQL thread parser bypasses pagination cursor limitations.

    Parameters:
    - tweet_id: ID of the tweet whose replies you want to view.
    - count: Maximum number of replies to return (default: 10, max: 50).
    """
    tweet_id = str(tweet_id or "").strip()
    if not tweet_id:
        return _format_res(False, "get_tweet_replies", "查询失败：tweet_id 不能为空", error="Empty tweet_id")

    try:
        client = get_client()
        count = max(1, min(int(count or 10), 50))
        gql_res = await client.gql.tweet_detail(tweet_id, None)
        data = gql_res[0] if isinstance(gql_res, tuple) else gql_res
        instructions = (
            data.get("data", {})
            .get("threaded_conversation_with_injections_v2", {})
            .get("instructions", [])
        )

        entries = []
        for inst in instructions:
            if inst.get("type") == "TimelineAddEntries":
                entries.extend(inst.get("entries", []))

        replies = []

        def _parse_tweet_res(res_obj):
            if not res_obj:
                return None
            try:
                t = Tweet(client, res_obj, None)
                if str(t.id) != str(tweet_id):
                    u = getattr(t, "user", None)
                    return {
                        "reply_id": str(t.id),
                        "author": getattr(u, "screen_name", "unknown") if u else "unknown",
                        "author_name": getattr(u, "name", "") if u else "",
                        "text": t.text,
                        "created_at": getattr(t, "created_at", ""),
                        "url": f"https://x.com/i/status/{t.id}"
                    }
            except Exception:
                pass
            return None

        for entry in entries:
            content = entry.get("content", {})
            entry_type = content.get("entryType")
            if entry_type == "TimelineTimelineItem":
                item_content = content.get("itemContent", {})
                tr = item_content.get("tweet_results", {}).get("result")
                parsed = _parse_tweet_res(tr)
                if parsed:
                    replies.append(parsed)
                    if len(replies) >= count:
                        break
            elif entry_type == "TimelineTimelineModule":
                items = content.get("items", [])
                for sub_item in items:
                    item_content = sub_item.get("item", {}).get("itemContent", {})
                    tr = item_content.get("tweet_results", {}).get("result")
                    parsed = _parse_tweet_res(tr)
                    if parsed:
                        replies.append(parsed)
                        if len(replies) >= count:
                            break
            if len(replies) >= count:
                break

        return _format_res(
            True, "get_tweet_replies", f"推文 {tweet_id} 获取到 {len(replies)} 条评论回复",
            data={"tweet_id": tweet_id, "total": len(replies), "replies": replies}
        )
    except Exception as exc:
        return _format_res(False, "get_tweet_replies", f"获取评论失败: {exc}", error=str(exc))


@mcp.tool()
async def get_tweet_quotes(tweet_id: str, count: int = 10) -> str:
    """Retrieve quote tweets that quoted a specific tweet.

    Parameters:
    - tweet_id: ID of the target tweet to find quotes for.
    - count: Number of quote tweets to fetch (default: 10, max: 20).
    """
    tweet_id = str(tweet_id or "").strip()
    if not tweet_id:
        return _format_res(False, "get_tweet_quotes", "查询失败：tweet_id 不能为空", error="Empty tweet_id")
    try:
        client = get_client()
        count = max(1, min(int(count or 10), 20))
        query = f"https://x.com/i/status/{tweet_id}"
        quotes = []
        try:
            results = await client.search_tweet(query, "Latest", count=count)
            for t in list(results)[:count]:
                u = getattr(t, "user", None)
                quotes.append({
                    "quote_tweet_id": str(t.id),
                    "author": getattr(u, "screen_name", "unknown") if u else "unknown",
                    "author_name": getattr(u, "name", "") if u else "",
                    "text": getattr(t, "text", ""),
                    "created_at": getattr(t, "created_at", ""),
                    "url": f"https://x.com/i/status/{t.id}"
                })
        except Exception as e:
            if "404" not in str(e):
                raise e

        return _format_res(
            True, "get_tweet_quotes", f"成功检索到 {len(quotes)} 条引用转发",
            data={"tweet_id": tweet_id, "total": len(quotes), "quotes": quotes}
        )
    except Exception as exc:
        return _format_res(False, "get_tweet_quotes", f"检索引用推文失败: {exc}", error=str(exc))


@mcp.tool()
async def search_tweets(
    query: str,
    count: int = 10,
    from_user: Optional[str] = None,
    since_date: Optional[str] = None,
    until_date: Optional[str] = None,
    min_faves: Optional[int] = None,
    min_retweets: Optional[int] = None,
    min_replies: Optional[int] = None
) -> str:
    """Search for tweets on X (Twitter) with advanced filtering.

    Parameters:
    - query: Search keywords, hashtags, or phrases.
    - count: Number of results to return (default: 10, max: 20).
    - from_user: Optional username to filter tweets from a specific author (e.g. 'twitter_user').
    - since_date: Optional start date filter in YYYY-MM-DD format (e.g. '2026-10-01').
    - until_date: Optional end date filter in YYYY-MM-DD format.
    - min_faves: Optional minimum like count filter (e.g. 10).
    - min_retweets: Optional minimum retweet count filter.
    - min_replies: Optional minimum reply count filter.
    """
    raw_query = (query or "").strip()
    q_parts = [raw_query] if raw_query else []
    if from_user:
        q_parts.append(f"from:{from_user.strip().lstrip('@')}")
    if since_date:
        q_parts.append(f"since:{since_date.strip()}")
    if until_date:
        q_parts.append(f"until:{until_date.strip()}")
    if min_faves is not None and int(min_faves) > 0:
        q_parts.append(f"min_faves:{min_faves}")
    if min_retweets is not None and int(min_retweets) > 0:
        q_parts.append(f"min_retweets:{min_retweets}")
    if min_replies is not None and int(min_replies) > 0:
        q_parts.append(f"min_replies:{min_replies}")

    full_query = " ".join(q_parts).strip()
    if not full_query:
        return _format_res(False, "search_tweets", "搜索失败：搜索关键词和过滤条件不能全为空", error="Empty search query")

    try:
        client = get_client()
        count = max(1, min(int(count or 10), 20))
        tweets = []
        try:
            results = await client.search_tweet(full_query, "Latest", count=count)
            for t in list(results)[:count]:
                user = getattr(t, "user", None)
                tweets.append({
                    "tweet_id": str(getattr(t, "id", "")),
                    "author": getattr(user, "screen_name", "unknown") if user else "unknown",
                    "author_name": getattr(user, "name", "") if user else "",
                    "created_at": getattr(t, "created_at", ""),
                    "text": getattr(t, "text", ""),
                    "url": f"https://x.com/i/status/{getattr(t, 'id', '')}"
                })
        except Exception as e:
            if "404" not in str(e):
                raise e

        return _format_res(
            True, "search_tweets", f"搜索完成，找到 {len(tweets)} 条符合条件的推文",
            data={"query": full_query, "total": len(tweets), "tweets": tweets}
        )
    except Exception as exc:
        return _format_res(False, "search_tweets", f"搜索推文失败: {exc}", error=str(exc))


@mcp.tool()
async def get_user_info(username: str) -> str:
    """Get full profile details for a specific X (Twitter) user.

    Returns bio, follower count, following count, total tweets, ID, etc.

    Parameters:
    - username: Screen name of the user (e.g. 'jack', '@' optional).
    """
    username = (username or "").strip().lstrip("@")
    if not username:
        return _format_res(False, "get_user_info", "查询失败：username 不能为空", error="Empty username")
    try:
        client = get_client()
        user = await client.get_user_by_screen_name(username)
        if not user:
            return _format_res(False, "get_user_info", f"未找到用户 @{username}", error="User not found")
        profile = {
            "screen_name": user.screen_name,
            "name": user.name,
            "id": str(user.id),
            "bio": user.description,
            "followers_count": user.followers_count,
            "following_count": user.following_count,
            "tweets_count": user.statuses_count,
            "profile_url": f"https://x.com/{user.screen_name}"
        }
        return _format_res(True, "get_user_info", f"成功获取 @{user.screen_name} 个人主页资料", data=profile)
    except Exception as exc:
        return _format_res(False, "get_user_info", f"获取用户信息失败: {exc}", error=str(exc))


@mcp.tool()
async def get_user_tweets(username: str, count: int = 5) -> str:
    """Get recent tweets posted by a specific user from their profile timeline.

    Parameters:
    - username: Screen name of the user.
    - count: Number of tweets to fetch (default: 5, max: 20).
    """
    username = (username or "").strip().lstrip("@")
    if not username:
        return _format_res(False, "get_user_tweets", "查询失败：username 不能为空", error="Empty username")
    try:
        client = get_client()
        count = max(1, min(int(count or 5), 20))
        user = await client.get_user_by_screen_name(username)
        if not user:
            return _format_res(False, "get_user_tweets", f"未找到用户 @{username}", error="User not found")
        tweets_res = await user.get_tweets("Tweets", count=count)
        items = []
        for t in list(tweets_res)[:count]:
            items.append({
                "tweet_id": str(t.id),
                "author": username,
                "created_at": getattr(t, "created_at", ""),
                "text": t.text,
                "url": f"https://x.com/i/status/{t.id}"
            })
        return _format_res(
            True, "get_user_tweets", f"成功获取 @{username} 的 {len(items)} 条最新推文",
            data={"username": username, "total": len(items), "tweets": items}
        )
    except Exception as exc:
        return _format_res(False, "get_user_tweets", f"获取用户推文失败: {exc}", error=str(exc))


# -------------------------------------------------------------
# 3. Follow, Followers & Following Management
# -------------------------------------------------------------

@mcp.tool()
async def follow_user(username: str) -> str:
    """Follow a user on X (Twitter).

    Parameters:
    - username: Screen name or user ID of the person to follow.
    """
    try:
        client = get_client()
        user_id, screen_name = await _resolve_user_id(client, username)
        await client.follow_user(user_id)
        return _format_res(
            True, "follow_user", f"已成功关注用户 @{screen_name}",
            data={"user_id": user_id, "screen_name": screen_name, "following": True}
        )
    except Exception as exc:
        return _format_res(False, "follow_user", f"关注用户失败: {exc}", error=str(exc))


@mcp.tool()
async def unfollow_user(username: str) -> str:
    """Unfollow a user on X (Twitter).

    Parameters:
    - username: Screen name or user ID of the person to unfollow.
    """
    try:
        client = get_client()
        user_id, screen_name = await _resolve_user_id(client, username)
        await client.unfollow_user(user_id)
        return _format_res(
            True, "unfollow_user", f"已取消关注用户 @{screen_name}",
            data={"user_id": user_id, "screen_name": screen_name, "following": False}
        )
    except Exception as exc:
        return _format_res(False, "unfollow_user", f"取消关注失败: {exc}", error=str(exc))


@mcp.tool()
async def get_user_followers(username: str, count: int = 20) -> str:
    """Get the followers list (users who follow this account) for a specific user.

    Parameters:
    - username: Screen name or numeric user ID of the user.
    - count: Number of followers to fetch (default: 20, max: 50).
    """
    try:
        client = get_client()
        count = max(1, min(int(count or 20), 50))
        user_id, screen_name = await _resolve_user_id(client, username)
        followers = await client.get_user_followers(user_id, count=count)
        items = []
        for u in list(followers)[:count]:
            items.append({
                "screen_name": u.screen_name,
                "name": u.name,
                "id": str(u.id),
                "bio": getattr(u, "description", ""),
                "followers_count": getattr(u, "followers_count", 0),
                "following_count": getattr(u, "following_count", 0)
            })
        return _format_res(
            True, "get_user_followers", f"成功获取 @{screen_name} 的 {len(items)} 位关注者（粉丝）",
            data={"target_user": screen_name, "total": len(items), "followers": items}
        )
    except Exception as exc:
        return _format_res(False, "get_user_followers", f"获取粉丝列表失败: {exc}", error=str(exc))


@mcp.tool()
async def get_user_following(username: str, count: int = 20) -> str:
    """Get the following list (users who this account follows) for a specific user.

    Parameters:
    - username: Screen name or numeric user ID of the user.
    - count: Number of followed users to fetch (default: 20, max: 50).
    """
    try:
        client = get_client()
        count = max(1, min(int(count or 20), 50))
        user_id, screen_name = await _resolve_user_id(client, username)
        following = await client.get_user_following(user_id, count=count)
        items = []
        for u in list(following)[:count]:
            items.append({
                "screen_name": u.screen_name,
                "name": u.name,
                "id": str(u.id),
                "bio": getattr(u, "description", ""),
                "followers_count": getattr(u, "followers_count", 0),
                "following_count": getattr(u, "following_count", 0)
            })
        return _format_res(
            True, "get_user_following", f"成功获取 @{screen_name} 正在关注的 {len(items)} 位用户",
            data={"target_user": screen_name, "total": len(items), "following": items}
        )
    except Exception as exc:
        return _format_res(False, "get_user_following", f"获取关注列表失败: {exc}", error=str(exc))


# -------------------------------------------------------------
# 4. Status Perception (Notifications) & Trends
# -------------------------------------------------------------

@mcp.tool()
async def get_notifications(category: str = "All", count: int = 15) -> str:
    """Perceive account status & notifications (likes, new followers, mentions, replies).

    Provides detailed notification items with actionable IDs (tweet_id, user_id)
    allowing the AI to inspect or interact further.

    Parameters:
    - category: Notification category: 'All' (default), 'Verified', or 'Mentions'.
    - count: Number of notifications to fetch (default: 15, max: 40).
    """
    cat = (category or "All").capitalize()
    if cat not in ("All", "Verified", "Mentions"):
        cat = "All"
    try:
        client = get_client()
        count = max(1, min(int(count or 15), 40))
        notifs = await client.get_notifications(cat, count=count)
        items = []
        summary = {"likes": 0, "follows": 0, "replies": 0, "retweets": 0, "dms": 0, "other": 0}

        for n in list(notifs)[:count]:
            msg = getattr(n, "message", "") or ""
            msg_lower = msg.lower()
            notif_type = "other"
            if "liked" in msg_lower:
                notif_type = "like"
                summary["likes"] += 1
            elif "followed" in msg_lower:
                notif_type = "follow"
                summary["follows"] += 1
            elif "replied" in msg_lower or "reply" in msg_lower:
                notif_type = "reply"
                summary["replies"] += 1
            elif "retweeted" in msg_lower or "reposted" in msg_lower:
                notif_type = "retweet"
                summary["retweets"] += 1
            else:
                summary["other"] += 1

            u = getattr(n, "from_user", None)
            from_user_dict = None
            if u:
                from_user_dict = {
                    "screen_name": getattr(u, "screen_name", None),
                    "name": getattr(u, "name", None),
                    "id": str(getattr(u, "id", "")),
                }

            t = getattr(n, "tweet", None)
            tweet_dict = None
            if t:
                tweet_dict = {
                    "id": str(getattr(t, "id", "")),
                    "text": getattr(t, "text", ""),
                }

            items.append({
                "id": getattr(n, "id", None),
                "type": notif_type,
                "message": msg,
                "from_user": from_user_dict,
                "tweet": tweet_dict,
                "timestamp_ms": getattr(n, "timestamp_ms", None),
            })

        # 检查未读私信 (DM Inbox)
        try:
            import twikit.client.v11 as v11
            dm_res, _ = await client.v11.base.get(
                v11.Endpoint.DM_INBOX,
                headers=client.v11.base._base_headers
            )
            inbox_state = dm_res.get("inbox_initial_state", {}) if isinstance(dm_res, dict) else {}
            conversations = inbox_state.get("conversations", {})
            unread_dms = 0
            for cdata in conversations.values():
                last_read = int(cdata.get("last_read_event_id") or 0)
                max_entry = int(cdata.get("max_entry_id") or 0)
                if max_entry > last_read:
                    unread_dms += 1
            summary["dms"] = unread_dms
        except Exception:
            pass

        summary_text = (
            f"最新通知感知概览 (共 {len(items)} 条)："
            f"点赞 {summary['likes']} 条 | 新粉丝 {summary['follows']} 人 | 回复 {summary['replies']} 条 | 私信 {summary['dms']} 条 | 转发 {summary['retweets']} 条"
        )
        return _format_res(
            True, "get_notifications", summary_text,
            data={"category": cat, "total": len(items), "summary": summary, "notifications": items}
        )
    except Exception as exc:
        return _format_res(False, "get_notifications", f"获取通知失败: {exc}", error=str(exc))


@mcp.tool()
async def get_trends(category: str = "trending", count: int = 20) -> str:
    """View trending topics and hot hashtags on X (Twitter).

    Parameters:
    - category: 'trending' (default), 'for-you', 'news', 'sports', or 'entertainment'.
    - count: Number of trending topics to fetch (default: 20, max: 50).
    """
    category = (category or "trending").lower()
    if category not in ("trending", "for-you", "news", "sports", "entertainment"):
        category = "trending"
    try:
        client = get_client()
        count = max(1, min(int(count or 20), 50))
        resp, _ = await client.v11.guide(category, count, {"candidate_source": "trends"})
        trends = []
        for inst in resp.get("timeline", {}).get("instructions", []):
            for e in inst.get("addEntries", {}).get("entries", []):
                if e.get("entryId") == "trends" or str(e.get("entryId", "")).startswith("Guide"):
                    items = e.get("content", {}).get("timelineModule", {}).get("items", [])
                    for it in items:
                        t = it.get("item", {}).get("content", {}).get("trend", {})
                        if t and t.get("name"):
                            trends.append({
                                "name": t.get("name"),
                                "meta": t.get("trendMetadata", {}).get("metaDescription"),
                                "url": t.get("url", {}).get("url")
                            })
                            if len(trends) >= count:
                                break
        return _format_res(
            True, "get_trends", f"成功获取 {len(trends)} 条热门趋势话题",
            data={"category": category, "total": len(trends), "trends": trends}
        )
    except Exception as exc:
        return _format_res(False, "get_trends", f"获取趋势失败: {exc}", error=str(exc))


@mcp.tool()
async def get_mentions(count: int = 15) -> str:
    """Check tweets and notifications where you were mentioned or tagged (@you).

    Use this tool to see who mentioned/tagged you in tweets or replies.

    Parameters:
    - count: Number of mentions to fetch (default: 15, max: 40).
    """
    try:
        client = get_client()
        count = max(1, min(int(count or 15), 40))
        notifs = await client.get_notifications("Mentions", count=count)
        items = []

        for n in list(notifs)[:count]:
            msg = getattr(n, "message", "") or ""
            u = getattr(n, "from_user", None)
            from_user_dict = None
            if u:
                from_user_dict = {
                    "screen_name": getattr(u, "screen_name", None),
                    "name": getattr(u, "name", None),
                    "id": str(getattr(u, "id", "")),
                }

            t = getattr(n, "tweet", None)
            tweet_dict = None
            if t:
                raw_text = getattr(t, "text", "")
                expanded_text = await _expand_tco_links(raw_text)
                tweet_dict = {
                    "id": str(getattr(t, "id", "")),
                    "text": expanded_text,
                    "url": f"https://x.com/i/status/{getattr(t, 'id', '')}",
                    "created_at": getattr(t, "created_at", ""),
                }

            items.append({
                "notification_id": getattr(n, "id", ""),
                "message": msg,
                "time": _format_timestamp(getattr(n, "timestamp_ms", None)),
                "from_user": from_user_dict,
                "tweet": tweet_dict,
            })

        summary_text = f"成功获取 {len(items)} 条被提及 (@Mentions) 记录"
        return _format_res(
            True, "get_mentions", summary_text,
            data={"total": len(items), "mentions": items}
        )
    except Exception as exc:
        return _format_res(False, "get_mentions", f"获取被提及记录失败: {exc}", error=str(exc))


# -------------------------------------------------------------
# 5. Direct Messages (DMs) & Tweet Sharing
# -------------------------------------------------------------

@mcp.tool()
async def read_direct_messages(username: Optional[str] = None, count: int = 10) -> str:
    """Read direct messages (DM) conversation history with a specific user or inspect DM inbox.
    Automatically parses message creation times and expands short t.co links.

    Parameters:
    - username: Optional username/handle of conversation partner or user ID. If omitted or empty, inspects DM inbox and returns recent conversation threads & unread status.
    - count: Maximum number of recent messages to retrieve (default: 10, max: 30).
    """
    try:
        client = get_client()
        count = max(1, min(int(count or 10), 30))
        my_id = await _get_my_user_id(client)

        if not username:
            import twikit.client.v11 as v11
            dm_res, _ = await client.v11.base.get(
                v11.Endpoint.DM_INBOX,
                headers=client.v11.base._base_headers
            )
            inbox_state = dm_res.get("inbox_initial_state", {}) if isinstance(dm_res, dict) else {}
            conversations = inbox_state.get("conversations", {})
            users = inbox_state.get("users", {})
            entries = inbox_state.get("entries", [])
            unread_count = 0
            conv_list = []
            for cid, cdata in list(conversations.items())[:count]:
                last_read = int(cdata.get("last_read_event_id") or 0)
                max_entry = int(cdata.get("max_entry_id") or 0)
                is_unread = max_entry > last_read
                if is_unread:
                    unread_count += 1
                partners = []
                for p in cdata.get("participants", []):
                    pid = str(p.get("user_id", ""))
                    if pid and pid != my_id and pid in users:
                        partners.append(users[pid].get("screen_name", pid))
                conv_list.append({
                    "conversation_id": cid,
                    "partners": partners,
                    "is_unread": is_unread,
                    "last_read_event_id": str(last_read),
                    "max_entry_id": str(max_entry),
                })
            recent_msgs = []
            for e in entries[:count]:
                m = e.get("message", {})
                m_data = m.get("message_data", {})
                sender_id = str(m_data.get("sender_id", ""))
                is_me = (sender_id == my_id)
                raw_text = m_data.get("text", "")
                expanded_text = await _expand_tco_links(raw_text)
                msg_time = _format_timestamp(m.get("time") or m_data.get("time"))
                recent_msgs.append({
                    "message_id": m.get("id", ""),
                    "sender_id": sender_id,
                    "is_me": is_me,
                    "time": msg_time,
                    "text": expanded_text,
                })
            return _format_res(
                True, "read_direct_messages",
                f"成功获取私信收件箱概览：未读私信 {unread_count} 条，最近会话 {len(conv_list)} 个",
                data={"unread_count": unread_count, "conversations": conv_list, "recent_messages": recent_msgs}
            )

        target_user_id, target_screen_name = await _resolve_user_id(client, username)

        history = await client.get_dm_history(target_user_id)
        messages = []
        for msg in list(history or [])[:count]:
            sender_id = str(getattr(msg, "sender_id", ""))
            is_me = (sender_id == my_id)
            raw_text = getattr(msg, "text", "")
            expanded_text = await _expand_tco_links(raw_text)
            msg_time = _format_timestamp(getattr(msg, "time", None))
            messages.append({
                "message_id": getattr(msg, "id", ""),
                "sender_id": sender_id,
                "is_me": is_me,
                "sender_label": "Me" if is_me else f"@{target_screen_name}",
                "time": msg_time,
                "text": expanded_text
            })
        messages.reverse()
        return _format_res(
            True, "read_direct_messages", f"成功获取与 @{target_screen_name} 的 {len(messages)} 条私信记录",
            data={"partner": target_screen_name, "total": len(messages), "messages": messages}
        )
    except Exception as exc:
        return _format_res(False, "read_direct_messages", f"读取私信失败: {exc}", error=str(exc))


@mcp.tool()
async def send_direct_message(username: str, text: str, reply_to_message_id: Optional[str] = None) -> str:
    """Send or reply to a direct message (DM) on X (Twitter).

    Parameters:
    - username: The recipient's username/handle or numeric user ID.
    - text: Message content to send.
    - reply_to_message_id: Optional ID of the specific message to reply to.
    """
    text = (text or "").strip()
    if not text:
        return _format_res(False, "send_direct_message", "发送失败：私信内容 text 不能为空", error="Empty message text")
    try:
        client = get_client()
        target_user_id, target_screen_name = await _resolve_user_id(client, username)
        my_id = await _get_my_user_id(client)
        reply_id = str(reply_to_message_id).strip() if reply_to_message_id else None

        # Directly call _send_dm with robust conversation ID to avoid client.user_id() 404
        conv_id = f"{target_user_id}-{my_id}"
        response = await client._send_dm(conv_id, text, None, reply_id)

        sent_id = "sent"
        entries = response.get("entries", []) if isinstance(response, dict) else []
        if entries and isinstance(entries[0], dict):
            sent_id = entries[0].get("message", {}).get("id", "sent")

        return _format_res(
            True, "send_direct_message", f"私信已成功发送给 @{target_screen_name}！",
            data={"recipient": target_screen_name, "message_id": str(sent_id), "text": text}
        )
    except Exception as exc:
        err_msg = str(exc)
        if "344" in err_msg or "limit" in err_msg.lower():
            err_msg = "发送私信失败：触发 X 平台频次或风控限制，请稍后重试。"
        return _format_res(False, "send_direct_message", f"发送私信失败: {err_msg}", error=str(exc))


@mcp.tool()
async def share_tweet_via_dm(username: str, tweet_id: str, comment: Optional[str] = None) -> str:
    """Share a tweet with a user via direct message (DM).

    Parameters:
    - username: The recipient's username or user ID.
    - tweet_id: The ID of the tweet to share.
    - comment: Optional personal message/commentary to accompany the shared post link.
    """
    tweet_id = str(tweet_id or "").strip()
    if not tweet_id:
        return _format_res(False, "share_tweet_via_dm", "分享失败：tweet_id 不能为空", error="Empty tweet_id")
    tweet_url = f"https://x.com/i/status/{tweet_id}"
    full_text = f"{comment.strip()}\n{tweet_url}" if comment and comment.strip() else tweet_url
    try:
        client = get_client()
        target_user_id, target_screen_name = await _resolve_user_id(client, username)
        my_id = await _get_my_user_id(client)
        conv_id = f"{target_user_id}-{my_id}"
        await client._send_dm(conv_id, full_text, None, None)
        return _format_res(
            True, "share_tweet_via_dm", f"推文已成功私信分享给 @{target_screen_name}！",
            data={"recipient": target_screen_name, "tweet_id": tweet_id, "url": tweet_url}
        )
    except Exception as exc:
        return _format_res(False, "share_tweet_via_dm", f"分享推文失败: {exc}", error=str(exc))


# -------------------------------------------------------------
# 6. Priority / VIP Watchlist Management
# -------------------------------------------------------------

@mcp.tool()
async def set_priority_accounts(usernames: Union[list[str], str], mode: str = "add") -> str:
    """Configure priority / VIP accounts watchlist.

    Allows AI to maintain a special list of partners or favorite accounts to check first.

    Parameters:
    - usernames: Account username(s) to add/remove/replace (can be list or comma-separated string).
    - mode: 'add' (add to existing list), 'remove' (remove from list), or 'replace' (overwrite list).
    """
    cfg_file = _get_priority_config_path()
    current_set = set()
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                current_set = set(json.load(f))
        except Exception:
            current_set = set()

    if isinstance(usernames, str):
        users = [u.strip().lstrip("@") for u in usernames.split(",") if u.strip()]
    else:
        users = [str(u).strip().lstrip("@") for u in usernames if str(u).strip()]

    mode = (mode or "add").lower()
    if mode == "replace":
        current_set = set(users)
    elif mode == "remove":
        current_set -= set(users)
    else:
        current_set.update(users)

    updated_list = sorted(list(current_set))
    try:
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(updated_list, f, ensure_ascii=False, indent=2)
        return _format_res(
            True, "set_priority_accounts", f"特定优先关注账号名单已更新（当前共 {len(updated_list)} 个账号）",
            data={"priority_accounts": updated_list, "mode": mode}
        )
    except Exception as exc:
        return _format_res(False, "set_priority_accounts", f"更新特定关注账号失败: {exc}", error=str(exc))


@mcp.tool()
async def get_priority_accounts() -> str:
    """View the currently configured priority / VIP accounts watchlist."""
    cfg_file = _get_priority_config_path()
    accounts = []
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                accounts = json.load(f)
        except Exception:
            accounts = []
    return _format_res(
        True, "get_priority_accounts", f"当前特定关注账号名单共 {len(accounts)} 个",
        data={"total": len(accounts), "priority_accounts": accounts}
    )


@mcp.tool()
async def get_priority_timeline(count_per_user: int = 3) -> str:
    """Check recent tweets specifically from your configured priority / VIP accounts.

    Aggregates and inspects updates from your partner and favorite accounts in one call.

    Parameters:
    - count_per_user: Number of latest tweets to fetch per priority account (default: 3, max: 10).
    """
    cfg_file = _get_priority_config_path()
    accounts = []
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                accounts = json.load(f)
        except Exception:
            accounts = []

    if not accounts:
        return _format_res(
            True, "get_priority_timeline", "未设置特定关注账号。可调用 set_priority_accounts(usernames=['...']) 添加关注。",
            data={"total": 0, "tweets": []}
        )

    try:
        client = get_client()
        count_per_user = max(1, min(int(count_per_user or 3), 10))
        all_tweets = []
        for user_handle in accounts:
            try:
                user = await client.get_user_by_screen_name(user_handle)
                if user:
                    t_res = await user.get_tweets("Tweets", count=count_per_user)
                    for t in list(t_res)[:count_per_user]:
                        all_tweets.append({
                            "tweet_id": str(t.id),
                            "author": user_handle,
                            "created_at": getattr(t, "created_at", ""),
                            "text": t.text,
                            "url": f"https://x.com/i/status/{t.id}"
                        })
            except Exception:
                pass

        return _format_res(
            True, "get_priority_timeline", f"成功抓取特定关注账号的最新推文，共 {len(all_tweets)} 条",
            data={"accounts": accounts, "total": len(all_tweets), "tweets": all_tweets}
        )
    except Exception as exc:
        return _format_res(False, "get_priority_timeline", f"获取特定关注账号推文失败: {exc}", error=str(exc))


if __name__ == "__main__":
    mcp.run(transport="stdio")
