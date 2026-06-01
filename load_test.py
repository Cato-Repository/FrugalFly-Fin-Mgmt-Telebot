"""
Full conversation simulation: NUM_USERS concurrent users going through the complete bot flow.
Each user sends all 13 conversation steps sequentially.
All users run in parallel, staggered slightly for realism.

Note: "Chat not found" errors in Render logs are expected — fake user IDs can't receive
Telegram messages. What matters: all webhook POSTs return 200 and server doesn't crash.

Usage: python load_test.py
"""

import asyncio
import time

import httpx

WEBHOOK_URL  = "https://frugalfly-fin-mgmt-telebot-1.onrender.com/webhook"
HEALTH_URL   = "https://frugalfly-fin-mgmt-telebot-1.onrender.com/"
NUM_USERS    = 50
STEP_DELAY   = 0.5   # seconds between each step per user
USER_STAGGER = 0.1   # seconds between each user starting (avoids thundering herd)

STEPS = [
    ("message",  "/start",              "start"),
    ("callback", "SGD",                 "currency"),
    ("message",  "Tokyo",               "destination"),
    ("message",  "7",                   "duration"),
    ("message",  "1500",                "budget"),
    ("message",  "500",                 "food"),
    ("message",  "300",                 "transport"),
    ("message",  "400",                 "hotel"),
    ("message",  "100",                 "activities"),
    ("message",  "100",                 "other"),        # triggers LLM call
    ("callback", "q1_yes",              "feedback_q1"),
    ("callback", "q2_yes",              "feedback_q2"),
    ("message",  "More currency options","feature_req"),
]


def make_message(user_id: int, update_id: int, text: str) -> dict:
    is_cmd = text.startswith("/")
    payload = {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "from":  {"id": user_id, "is_bot": False, "first_name": f"User{user_id}", "username": f"user{user_id}"},
            "chat":  {"id": user_id, "type": "private"},
            "date":  int(time.time()),
            "text":  text,
        },
    }
    if is_cmd:
        payload["message"]["entities"] = [{"offset": 0, "length": len(text), "type": "bot_command"}]
    return payload


def make_callback(user_id: int, update_id: int, data: str) -> dict:
    return {
        "update_id": update_id,
        "callback_query": {
            "id":    str(update_id),
            "from":  {"id": user_id, "is_bot": False, "first_name": f"User{user_id}", "username": f"user{user_id}"},
            "message": {
                "message_id": update_id - 1,
                "from": {"id": 999999999, "is_bot": True, "first_name": "FrugalFly"},
                "chat": {"id": user_id, "type": "private"},
                "date": int(time.time()),
                "text": "...",
            },
            "chat_instance": str(user_id),
            "data": data,
        },
    }


async def simulate_user(
    client: httpx.AsyncClient,
    user_index: int,
    print_lock: asyncio.Lock,
) -> dict:
    user_id = 70000 + user_index
    step_results = []
    base_update_id = user_id * 100

    # Stagger user start time
    await asyncio.sleep(user_index * USER_STAGGER)

    for i, (kind, value, label) in enumerate(STEPS):
        update_id = base_update_id + i
        payload = make_message(user_id, update_id, value) if kind == "message" else make_callback(user_id, update_id, value)

        t0 = time.monotonic()
        try:
            r = await client.post(WEBHOOK_URL, json=payload, timeout=15.0)
            ms = round((time.monotonic() - t0) * 1000)
            ok = r.status_code == 200
            step_results.append({"label": label, "status": r.status_code, "ms": ms, "ok": ok})
        except Exception as e:
            ms = round((time.monotonic() - t0) * 1000)
            step_results.append({"label": label, "status": "ERR", "ms": ms, "ok": False, "error": str(e)})

        await asyncio.sleep(STEP_DELAY)

    passed = sum(1 for s in step_results if s["ok"])
    all_ok = passed == len(step_results)

    async with print_lock:
        icon = "✅" if all_ok else "⚠️ "
        print(f"  {icon} User {user_index + 1:>3}  {passed}/{len(step_results)} steps OK")

    return {"user": user_index + 1, "steps": step_results, "passed": passed}


async def main():
    async with httpx.AsyncClient() as client:

        # Health check
        print("Checking service is up... ", end="", flush=True)
        try:
            r = await client.get(HEALTH_URL, timeout=10.0)
            if r.status_code != 200:
                print("❌ DOWN — aborting.")
                return
        except Exception as e:
            print(f"❌ Unreachable: {e}")
            return
        print("✅\n")

        est_s = len(STEPS) * STEP_DELAY + NUM_USERS * USER_STAGGER
        print(f"Simulating {NUM_USERS} concurrent users × {len(STEPS)} steps each.")
        print(f"Step delay: {STEP_DELAY}s | User stagger: {USER_STAGGER}s")
        print(f"Estimated wall time: ~{est_s:.0f}s\n")
        print("─" * 40)

        lock = asyncio.Lock()
        tasks = [simulate_user(client, i, lock) for i in range(NUM_USERS)]
        t0 = time.monotonic()
        all_results = await asyncio.gather(*tasks)
        wall_s = time.monotonic() - t0

    # Per-step breakdown
    print("\n─── Step breakdown ─────────────────────────────")
    print(f"{'Step':<18} {'200 OK':>8}    {'Avg ms':>8}    {'Min':>6}    {'Max':>6}")
    print("─" * 55)
    for _, _, label in STEPS:
        step_data = [s for r in all_results for s in r["steps"] if s["label"] == label]
        ok     = sum(1 for s in step_data if s["ok"])
        times  = [s["ms"] for s in step_data]
        avg_ms = sum(times) // len(times) if times else 0
        print(f"{label:<18} {ok:>5}/{NUM_USERS:<3}    {avg_ms:>6} ms    {min(times):>4} ms    {max(times):>4} ms")

    # Overall summary
    total_steps = NUM_USERS * len(STEPS)
    total_ok    = sum(r["passed"] for r in all_results)
    total_failed = total_steps - total_ok
    print("\n─── Summary ────────────────────────────────────")
    print(f"Total requests:  {total_steps}")
    print(f"✅ Passed:       {total_ok}")
    print(f"❌ Failed:       {total_failed}")
    print(f"Wall time:       {wall_s:.1f}s")
    print("─" * 50)
    print("\n⚠️  'Chat not found' errors in Render logs = expected (fake IDs).")
    print("   Key signal: all webhook POSTs returned 200 & server stayed alive.")


if __name__ == "__main__":
    asyncio.run(main())
