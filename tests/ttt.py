import telethon
import asyncio


c = telethon.TelegramClient("session", 21474300, "bfeee4698835929fffe8aa68f51c515e")


async def main():
    await c.connect()
    await c.run_until_disconnected()

asyncio.run(main())