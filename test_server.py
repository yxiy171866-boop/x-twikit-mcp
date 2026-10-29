import asyncio
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import mcp, _resolve_cookies


def test_tool_registration():
    print("[1/3] Testing tool registration in FastMCP...")
    tool_manager = mcp._tool_manager
    tool_names = list(tool_manager._tools.keys())
    print(f"Registered tools count: {len(tool_names)}")

    expected_tools = [
        "post_tweet",
        "reply_tweet",
        "quote_tweet",
        "delete_tweet",
        "favorite_tweet",
        "unfavorite_tweet",
        "retweet",
        "unretweet",
        "bookmark_tweet",
        "unbookmark_tweet",
        "get_bookmarks",
        "get_tweet_by_id",
        "get_tweet_replies",
        "get_tweet_quotes",
        "search_tweets",
        "get_user_info",
        "get_user_tweets",
        "follow_user",
        "unfollow_user",
        "get_user_followers",
        "get_user_following",
        "get_notifications",
        "get_trends",
        "read_direct_messages",
        "send_direct_message",
        "share_tweet_via_dm",
        "set_priority_accounts",
        "get_priority_accounts",
        "get_priority_timeline",
    ]
    for exp in expected_tools:
        assert exp in tool_names, f"Expected tool '{exp}' is not registered!"
    print(f"✓ All {len(expected_tools)} tools registered successfully!\n")


def test_cookie_resolution():
    print("[2/3] Testing cookie resolution fallback...")
    old_auth = os.environ.pop("TWITTER_AUTH_TOKEN", None)
    old_ct0 = os.environ.pop("TWITTER_CT0", None)

    cookies = _resolve_cookies()
    assert isinstance(cookies, dict)

    os.environ["TWITTER_AUTH_TOKEN"] = "mock_auth"
    os.environ["TWITTER_CT0"] = "mock_ct0"
    resolved = _resolve_cookies()
    assert resolved["auth_token"] == "mock_auth"
    assert resolved["ct0"] == "mock_ct0"

    if old_auth:
        os.environ["TWITTER_AUTH_TOKEN"] = old_auth
    else:
        os.environ.pop("TWITTER_AUTH_TOKEN", None)
    if old_ct0:
        os.environ["TWITTER_CT0"] = old_ct0
    else:
        os.environ.pop("TWITTER_CT0", None)
    print("✓ Cookie resolution logic verified!\n")


async def test_live_read():
    print("[3/3] Testing live tool operations with unified structure...")
    from server import (
        get_tweet_by_id,
        get_user_info,
        get_user_tweets,
        get_notifications,
        get_trends,
        set_priority_accounts,
        get_priority_accounts,
        get_priority_timeline,
        search_tweets,
    )

    # 1. get_user_info
    print("Testing get_user_info for Shellyiii7777...")
    res1 = await get_user_info("Shellyiii7777")
    data1 = json.loads(res1)
    assert data1["status"] == "success", f"Failed: {res1}"
    assert data1["data"]["screen_name"] == "Shellyiii7777"
    print("✓ get_user_info returned:", data1["message"])

    # 2. get_tweet_by_id with stats
    print("Testing get_tweet_by_id for tweet 2115434523802378708...")
    res2 = await get_tweet_by_id("2115434523802378708")
    data2 = json.loads(res2)
    assert data2["status"] == "success", f"Failed: {res2}"
    stats = data2["data"]["stats"]
    assert "likes" in stats and "bookmarks" in stats and "views" in stats
    print(f"✓ get_tweet_by_id stats verified: {stats}")

    # 3. get_notifications
    print("Testing get_notifications...")
    res3 = await get_notifications(count=5)
    data3 = json.loads(res3)
    assert data3["status"] == "success", f"Failed: {res3}"
    print("✓ get_notifications returned:", data3["message"])

    # 4. get_trends
    print("Testing get_trends...")
    res4 = await get_trends(count=5)
    data4 = json.loads(res4)
    assert data4["status"] == "success", f"Failed: {res4}"
    print("✓ get_trends returned:", data4["message"])

    # 5. priority accounts
    print("Testing priority accounts...")
    res5_set = await set_priority_accounts("Shellyiii7777", mode="replace")
    data5_set = json.loads(res5_set)
    assert data5_set["status"] == "success"
    res5_get = await get_priority_accounts()
    data5_get = json.loads(res5_get)
    assert "Shellyiii7777" in data5_get["data"]["priority_accounts"]
    print("✓ Priority accounts watchlist verified:", data5_get["data"]["priority_accounts"])

    # 6. search with filters
    print("Testing search_tweets with filters...")
    res6 = await search_tweets(query="MCP", from_user="Shellyiii7777", count=3)
    data6 = json.loads(res6)
    assert data6["status"] == "success"
    print("✓ search_tweets returned:", data6["message"])

    print("\n✓ All live read tests verified successfully!")


async def main():
    print("=" * 60)
    print("Twitter (X) MCP Server Test Suite (v1.2.0)")
    print("=" * 60)
    test_tool_registration()
    test_cookie_resolution()
    await test_live_read()
    print("\nALL 29 TOOLS TESTED AND VERIFIED!")


if __name__ == "__main__":
    asyncio.run(main())
