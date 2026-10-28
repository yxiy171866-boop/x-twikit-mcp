import os
import sys
import json
from pathlib import Path
from typing import Optional
from mcp.server.mcpserver import MCPServer
from twikit import Client

mcp = MCPServer("twitter-twikit")


def _resolve_cookies() -> dict[str, str]:
    """Resolve Twitter authentication cookies (auth_token & ct0).

    Resolution priority:
    1. Environment variables: TWITTER_AUTH_TOKEN and TWITTER_CT0
    2. Path specified in TWITTER_COOKIES_PATH environment variable
    3. Default local file: ./cookies.json
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
                
                # Support dictionary format: {"auth_token": "...", "ct0": "..."}
                if isinstance(data, dict):
                    auth_token = data.get("auth_token", "")
                    ct0 = data.get("ct0", "")
                    if auth_token and ct0:
                        return {"auth_token": auth_token, "ct0": ct0}
                
                # Support list format exported by browser extensions (e.g. EditThisCookie)
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


def get_client() -> Client:
    """Initialize and return an authenticated Twikit Client."""
    cookies = _resolve_cookies()
    if not cookies or not cookies.get("auth_token") or not cookies.get("ct0"):
        raise RuntimeError(
            "Twitter cookies are not configured! Please provide TWITTER_AUTH_TOKEN and TWITTER_CT0 "
            "as environment variables, or create a 'cookies.json' file with {\"auth_token\": \"...\", \"ct0\": \"...\"}."
        )
    
    client = Client("en-US")
    client.set_cookies(cookies)
    return client


@mcp.tool()
async def post_tweet(text: str) -> str:
    """Post a new tweet to X (Twitter).
    
    Parameters:
    - text: Content of the tweet to post.
    """
    text = (text or "").strip()
    if not text:
        return "Error: Tweet text cannot be empty."
    try:
        client = get_client()
        tweet = await client.create_tweet(text=text)
        tweet_id = getattr(tweet, "id", None) or "posted"
        return f"Tweet posted successfully!\nURL: https://x.com/i/status/{tweet_id}"
    except Exception as exc:
        err_msg = str(exc)
        if "344" in err_msg:
            return "Twitter post error (344): Daily tweet limit reached for this account. Please wait a few hours or until tomorrow."
        if "226" in err_msg:
            return "Twitter post error (226): Blocked by automated spam detection. Try slightly varying the text."
        return f"Twitter post error: {exc}"


@mcp.tool()
async def reply_tweet(tweet_id: str, text: str) -> str:
    """Reply to an existing tweet or comment on X (Twitter).
    
    Parameters:
    - tweet_id: The ID of the tweet or comment to reply to.
    - text: Content of your reply.
    """
    tweet_id = str(tweet_id or "").strip()
    text = (text or "").strip()
    if not tweet_id or not text:
        return "Error: tweet_id and text cannot be empty."
    try:
        client = get_client()
        reply = await client.create_tweet(text=text, reply_to=tweet_id)
        reply_id = getattr(reply, "id", None) or "posted"
        return f"Reply posted successfully!\nURL: https://x.com/i/status/{reply_id}"
    except Exception as exc:
        err_msg = str(exc)
        if "344" in err_msg:
            return "Twitter reply error (344): Daily reply limit reached. Please wait a few hours."
        return f"Twitter reply error: {exc}"


@mcp.tool()
async def get_tweet_replies(tweet_id: str, count: int = 10) -> str:
    """Retrieve all replies and comments under a specific tweet.
    
    Bypasses standard GraphQL cursor limitations to parse full reply threads.
    
    Parameters:
    - tweet_id: ID of the tweet whose replies you want to view.
    - count: Maximum number of replies to return (default: 10, max: 50).
    """
    tweet_id = str(tweet_id or "").strip()
    if not tweet_id:
        return "Error: tweet_id cannot be empty."

    try:
        client = get_client()
        count = max(1, min(int(count or 10), 50))
        
        # Direct GraphQL call to fetch full thread
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

        from twikit.tweet import Tweet
        lines = []

        for entry in entries:
            content = entry.get("content", {})
            entry_type = content.get("entryType")

            # Single tweet entry
            if entry_type == "TimelineTimelineItem":
                item_content = content.get("itemContent", {})
                tweet_results = item_content.get("tweet_results", {}).get("result")
                if tweet_results:
                    try:
                        t = Tweet(client, tweet_results, None)
                        if str(t.id) != str(tweet_id):
                            u = getattr(t, "user", None)
                            screen_name = getattr(u, "screen_name", "unknown") if u else "unknown"
                            name = getattr(u, "name", "") if u else ""
                            lines.append(
                                f"Reply ID: {t.id} | User: @{screen_name} ({name})\n"
                                f"Content: {t.text}\n"
                                f"[Reply command: reply_tweet(tweet_id='{t.id}', text='...')]"
                            )
                            if len(lines) >= count:
                                break
                    except Exception:
                        pass

            # Thread / module of multiple replies
            elif entry_type == "TimelineTimelineModule":
                items = content.get("items", [])
                for sub_item in items:
                    item_content = sub_item.get("item", {}).get("itemContent", {})
                    tweet_results = item_content.get("tweet_results", {}).get("result")
                    if tweet_results:
                        try:
                            t = Tweet(client, tweet_results, None)
                            if str(t.id) != str(tweet_id):
                                u = getattr(t, "user", None)
                                screen_name = getattr(u, "screen_name", "unknown") if u else "unknown"
                                name = getattr(u, "name", "") if u else ""
                                lines.append(
                                    f"Reply ID: {t.id} | User: @{screen_name} ({name})\n"
                                    f"Content: {t.text}\n"
                                    f"[Reply command: reply_tweet(tweet_id='{t.id}', text='...')]"
                                )
                                if len(lines) >= count:
                                    break
                        except Exception:
                            pass
            if len(lines) >= count:
                break

        if not lines:
            return f"No comments or replies found for tweet ID: {tweet_id}."

        return f"Comments & replies for tweet {tweet_id} ({len(lines)} found):\n\n" + "\n\n---\n\n".join(lines)
    except Exception as exc:
        return f"Failed to get tweet replies: {exc}"


@mcp.tool()
async def search_tweets(query: str, count: int = 10) -> str:
    """Search for recent tweets on X (Twitter).
    
    Parameters:
    - query: Search query (keywords, hashtags, from:username, etc.).
    - count: Number of results to return (default: 10, max: 20).
    """
    query = (query or "").strip()
    if not query:
        return "Error: Query cannot be empty."
    try:
        client = get_client()
        count = max(1, min(int(count), 20))
        results = await client.search_tweet(query, "Latest", count=count)
        lines = []
        for t in list(results)[:count]:
            user = getattr(t, "user", None)
            screen_name = getattr(user, "screen_name", "unknown") if user else "unknown"
            t_id = getattr(t, "id", "")
            t_text = getattr(t, "text", "")
            lines.append(f"@{screen_name} (ID: {t_id}):\n{t_text}\n[Tip: Use get_tweet_replies(tweet_id='{t_id}') to inspect comments]")
        return "\n\n---\n\n".join(lines) if lines else "No tweets found."
    except Exception as exc:
        return f"Twitter search error: {exc}"


@mcp.tool()
async def get_tweet_by_id(tweet_id: str) -> str:
    """Get details of a specific tweet by its tweet ID.
    
    Parameters:
    - tweet_id: The unique ID of the tweet.
    """
    tweet_id = str(tweet_id or "").strip()
    if not tweet_id:
        return "Error: tweet_id cannot be empty."
    try:
        client = get_client()
        try:
            tweet = await client.get_tweet_by_id(tweet_id)
            if tweet:
                user = getattr(tweet, "user", None)
                screen_name = getattr(user, "screen_name", "unknown") if user else "unknown"
                created_at = getattr(tweet, "created_at", "")
                fav_count = getattr(tweet, "favorite_count", 0)
                retweet_count = getattr(tweet, "retweet_count", 0)
                reply_count = getattr(tweet, "reply_count", 0)
                bookmark_count = getattr(tweet, "bookmark_count", 0)
                views_count = getattr(tweet, "view_count", None) or getattr(tweet, "views", "0")
                return (
                    f"Tweet ID: {tweet.id}\n"
                    f"Author: @{screen_name}\n"
                    f"Created At: {created_at}\n"
                    f"Stats: Likes: {fav_count} | Bookmarks: {bookmark_count} | Retweets: {retweet_count} | Replies: {reply_count} | Views: {views_count}\n\n"
                    f"Text:\n{tweet.text}\n\n"
                    f"URL: https://x.com/i/status/{tweet.id}"
                )
        except Exception:
            pass

        # Fallback to direct GraphQL tweet detail
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
                        created_at = legacy.get("created_at") or ""
                        fav_count = legacy.get("favorite_count", 0)
                        retweet_count = legacy.get("retweet_count", 0)
                        reply_count = legacy.get("reply_count", 0)
                        bookmark_count = legacy.get("bookmark_count", 0)
                        views_obj = tweet_results.get("views", {})
                        views_count = views_obj.get("count", "0") if isinstance(views_obj, dict) else "0"
                        full_text = legacy.get("full_text") or ""
                        return (
                            f"Tweet ID: {tweet_id}\n"
                            f"Author: @{screen_name}\n"
                            f"Created At: {created_at}\n"
                            f"Stats: Likes: {fav_count} | Bookmarks: {bookmark_count} | Retweets: {retweet_count} | Replies: {reply_count} | Views: {views_count}\n\n"
                            f"Text:\n{full_text}\n\n"
                            f"URL: https://x.com/i/status/{tweet_id}"
                        )

        return f"Tweet not found: {tweet_id}"
    except Exception as exc:
        return f"Error retrieving tweet {tweet_id}: {exc}"


@mcp.tool()
async def get_user_info(username: str) -> str:
    """Get profile information for a specified X (Twitter) user.
    
    Parameters:
    - username: Screen name of the user (e.g. 'elonmusk', '@' is optional).
    """
    username = (username or "").strip().lstrip("@")
    if not username:
        return "Error: username cannot be empty."
    try:
        client = get_client()
        user = await client.get_user_by_screen_name(username)
        if not user:
            return f"User not found: @{username}"
        return (
            f"User Profile: @{user.screen_name} ({user.name})\n"
            f"ID: {user.id}\n"
            f"Bio: {user.description}\n"
            f"Followers: {user.followers_count} | Following: {user.following_count}\n"
            f"Tweets: {user.statuses_count}\n"
            f"Profile URL: https://x.com/{user.screen_name}"
        )
    except Exception as exc:
        return f"Error getting user info for @{username}: {exc}"


@mcp.tool()
async def get_user_tweets(username: str, count: int = 5) -> str:
    """Get the latest tweets posted by a specific user.
    
    Parameters:
    - username: Screen name of the user.
    - count: Number of tweets to fetch (default: 5, max: 20).
    """
    username = (username or "").strip().lstrip("@")
    if not username:
        return "Error: username cannot be empty."
    try:
        client = get_client()
        count = max(1, min(int(count), 20))
        user = await client.get_user_by_screen_name(username)
        if not user:
            return f"User not found: @{username}"
        tweets = await user.get_tweets("Tweets", count=count)
        lines = []
        for t in list(tweets)[:count]:
            lines.append(f"[Tweet ID: {t.id} | {t.created_at}]\n{t.text}")
        return "\n\n---\n\n".join(lines) if lines else f"No tweets found for @{username}."
    except Exception as exc:
        return f"Error fetching tweets for @{username}: {exc}"


@mcp.tool()
async def read_direct_messages(username: str, count: int = 10) -> str:
    """Read direct messages (DM) conversation history with a specific X (Twitter) user.
    
    Parameters:
    - username: Username/handle of the conversation partner (e.g. 'elonmusk' or user ID).
    - count: Maximum number of recent messages to retrieve (default: 10, max: 30).
    """
    raw_user = (username or "").strip().lstrip("@")
    if not raw_user:
        return "Error: username cannot be empty."
    try:
        client = get_client()
        my_id = str(await client.user_id())

        if raw_user.isdigit():
            target_user_id = raw_user
            target_screen_name = raw_user
        else:
            user_obj = await client.get_user_by_screen_name(raw_user)
            if not user_obj:
                return f"User not found: @{raw_user}"
            target_user_id = str(user_obj.id)
            target_screen_name = user_obj.screen_name

        count = max(1, min(int(count), 30))
        history = await client.get_dm_history(target_user_id)
        if not history:
            return f"No direct messages found with @{target_screen_name}."

        lines = []
        for msg in list(history)[:count]:
            sender_id = str(getattr(msg, "sender_id", ""))
            is_me = (sender_id == my_id)
            sender_label = "Me" if is_me else f"@{target_screen_name}"
            msg_id = getattr(msg, "id", "")
            msg_text = getattr(msg, "text", "")
            lines.append(f"[{sender_label}] (Message ID: {msg_id}):\n{msg_text}")

        lines.reverse()
        return f"Direct message history with @{target_screen_name} ({len(lines)} messages):\n\n" + "\n\n---\n\n".join(lines)
    except Exception as exc:
        return f"Error reading direct messages: {exc}"


@mcp.tool()
async def send_direct_message(username: str, text: str, reply_to_message_id: Optional[str] = None) -> str:
    """Send or reply to a direct message (DM) on X (Twitter).
    
    Parameters:
    - username: The recipient's username/handle or numeric user ID.
    - text: Message content to send.
    - reply_to_message_id: Optional ID of the message to reply to.
    """
    raw_user = (username or "").strip().lstrip("@")
    text = (text or "").strip()
    if not raw_user:
        return "Error: Recipient username cannot be empty."
    if not text:
        return "Error: Message text cannot be empty."

    try:
        client = get_client()
        if raw_user.isdigit():
            target_user_id = raw_user
            target_screen_name = raw_user
        else:
            user_obj = await client.get_user_by_screen_name(raw_user)
            if not user_obj:
                return f"Failed: User @{raw_user} not found."
            target_user_id = str(user_obj.id)
            target_screen_name = user_obj.screen_name

        reply_id = str(reply_to_message_id).strip() if reply_to_message_id else None
        sent_msg = await client.send_dm(target_user_id, text, reply_to=reply_id)
        sent_id = getattr(sent_msg, "id", "sent")
        return f"Direct message sent successfully to @{target_screen_name}!\nMessage ID: {sent_id}"
    except Exception as exc:
        err_msg = str(exc)
        if "344" in err_msg or "limit" in err_msg.lower():
            return "Failed to send DM: Daily DM limit reached on X. Please try again later."
        return f"Failed to send DM: {exc}"


@mcp.tool()
async def favorite_tweet(tweet_id: str) -> str:
    """Like / favorite a tweet by its ID.
    
    Parameters:
    - tweet_id: ID of the tweet to like.
    """
    tweet_id = str(tweet_id or "").strip()
    if not tweet_id:
        return "Error: tweet_id cannot be empty."
    try:
        client = get_client()
        await client.favorite_tweet(tweet_id)
        return f"Tweet {tweet_id} liked successfully."
    except Exception as exc:
        return f"Twitter favorite error: {exc}"


@mcp.tool()
async def retweet(tweet_id: str) -> str:
    """Retweet / repost a tweet by its ID.
    
    Parameters:
    - tweet_id: ID of the tweet to retweet.
    """
    tweet_id = str(tweet_id or "").strip()
    if not tweet_id:
        return "Error: tweet_id cannot be empty."
    try:
        client = get_client()
        await client.retweet(tweet_id)
        return f"Tweet {tweet_id} retweeted successfully."
    except Exception as exc:
        return f"Twitter retweet error: {exc}"


@mcp.tool()
async def delete_tweet(tweet_id: str) -> str:
    """Delete a tweet posted by yourself by its ID.
    
    Parameters:
    - tweet_id: ID of the tweet to delete.
    """
    tweet_id = str(tweet_id or "").strip()
    if not tweet_id:
        return "Error: tweet_id cannot be empty."
    try:
        client = get_client()
        await client.delete_tweet(tweet_id)
        return f"Tweet {tweet_id} deleted successfully."
    except Exception as exc:
        return f"Twitter delete error: {exc}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
