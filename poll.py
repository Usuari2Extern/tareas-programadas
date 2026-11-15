import asyncio
import json
import os
import pathlib

import httpx
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
TG_SESSION = os.environ["TG_SESSION"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
NOTIFY_CHAT_ID = os.environ["NOTIFY_CHAT_ID"]
GROUP = os.environ["GROUP"]
TARGET_USER = os.environ["TARGET_USER"]
TOPIC_ID = os.environ.get("TOPIC_ID") or None  # opcional

STATE_FILE = pathlib.Path("state/last_id.json")


def parse(value: str):
    try:
        return int(value)
    except ValueError:
        return value


def topic_of(msg) -> int:
    rt = msg.reply_to
    if rt and getattr(rt, "forum_topic", False):
        return rt.reply_to_top_id or rt.reply_to_msg_id
    return 1


def load_last_id():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())["last_id"]
    return None


def save_last_id(value: int) -> None:
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps({"last_id": value}))


async def send_alert(text: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=15) as http:
        r = await http.post(url, json={"chat_id": NOTIFY_CHAT_ID, "text": text})
        r.raise_for_status()


async def main() -> None:
    async with TelegramClient(StringSession(TG_SESSION), API_ID, API_HASH) as client:
        await client.get_dialogs()  # para que Telethon conozca los IDs numéricos
        group = await client.get_entity(parse(GROUP))
        target = await client.get_entity(parse(TARGET_USER))
        group_name = getattr(group, "title", str(GROUP))

        latest = await client.get_messages(group, limit=1)
        latest_id = latest[0].id if latest else 0

        last_id = load_last_id()
        if last_id is None:
            # Primera ejecución: solo marca el punto de partida, sin avisar
            save_last_id(latest_id)
            print("Primera ejecución: punto de partida guardado.")
            return

        nuevos = []
        async for m in client.iter_messages(
            group, min_id=last_id, max_id=latest_id + 1, from_user=target, limit=50
        ):
            if TOPIC_ID and topic_of(m) != int(TOPIC_ID):
                continue
            nuevos.append(m)

        for m in reversed(nuevos):  # del más antiguo al más reciente
            texto = m.raw_text or "[mensaje sin texto: foto, sticker, etc.]"
            if len(texto) > 300:
                texto = texto[:300] + "…"
            await send_alert(f"📩 {group_name}\n{texto}")

        save_last_id(latest_id)
        # No se imprime el contenido de los mensajes: los logs pueden ser públicos
        print(f"Avisos enviados: {len(nuevos)}")


if __name__ == "__main__":
    asyncio.run(main())
