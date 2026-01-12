import os
import re
import logging
import mimetypes
import asyncio
from aiohttp import web
from pyrogram import Client, filters, enums

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
PORT = int(os.environ.get("PORT", 8080))

# IMPORTANT: Set this in Koyeb Env Vars to your actual App URL
# Example: https://my-app.koyeb.app
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080").strip("/")

# Initialize Client
app = Client(
    "koyeb_server",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

routes = web.RouteTableDef()

# --- HELPER FUNCTIONS ---

def parse_link(link):
    """
    Extracts Chat ID and Message ID.
    Supports standard TG links and custom 'bot' links.
    """
    # Pattern 1: Standard Private Channel (t.me/c/123456789/10)
    match = re.search(r"t\.me/c/(\d+)/(\d+)", link)
    if match:
        chat = int("-100" + match.group(1))
        msg_id = int(match.group(2))
        return chat, msg_id

    # Pattern 2: Public Username (t.me/channel/10)
    match = re.search(r"t\.me/([^/]+)/(\d+)", link)
    if match:
        chat = match.group(1) # Username
        msg_id = int(match.group(2))
        return chat, msg_id

    # Pattern 3: Direct Bot Chat (Custom format for this bot)
    # used when users send files directly to the bot
    match = re.search(r"t\.me/b/(\d+)/(\d+)", link)
    if match:
        chat = int(match.group(1)) # User ID (Positive Integer)
        msg_id = int(match.group(2))
        return chat, msg_id

    return None, None

async def get_media_info(link):
    chat_id, msg_id = parse_link(link)
    if not chat_id: return None, None
    try:
        msg = await app.get_messages(chat_id, msg_id)
        media = getattr(msg, "document", None) or \
                getattr(msg, "video", None) or \
                getattr(msg, "audio", None) or \
                getattr(msg, "photo", None)
        return msg, media
    except Exception as e:
        print(f"Error fetching: {e}")
        return None, None

def get_mime_type(file_name):
    mime_type, _ = mimetypes.guess_type(file_name)
    if not mime_type:
        ext = file_name.split('.')[-1].lower()
        if ext in ["mkv", "mp4", "webm", "avi", "mov"]:
            return f"video/{ext if ext != 'mkv' else 'x-matroska'}"
        return "application/octet-stream"
    return mime_type

# --- BOT COMMAND HANDLERS ---

@app.on_message(filters.command("start"))
async def start_handler(client, message):
    await message.reply_text(
        "👋 **Hello!**\n\n"
        "Send me a file or forward any file here, and I will generate a **Direct Download** and **Stream** link for you!",
        quote=True
    )

@app.on_message(filters.document | filters.video | filters.audio | filters.photo)
async def file_handler(client, message):
    """
    Triggered when user sends a file to the bot
    """
    # Create a link pointing to this specific message
    # Since it's a DM, we use a custom format "t.me/b/USERID/MSGID"
    # This helps our parser distinguish between Channel IDs (-100...) and User IDs (Positive)
    
    chat_id = message.chat.id
    msg_id = message.id
    
    # We construct a fake link that our webserver knows how to parse
    tg_link = f"https://t.me/b/{chat_id}/{msg_id}"
    safe_link = web.utils.quote(tg_link)
    
    stream_url = f"{BASE_URL}/watch/{safe_link}"
    download_url = f"{BASE_URL}/stream/{safe_link}?download=true"
    
    text = (
        f"✅ **Link Generated!**\n\n"
        f"📂 **File:** `{message.document.file_name if message.document else 'File'}`\n\n"
        f"📺 **Stream:** [Click to Watch]({stream_url})\n"
        f"📥 **Download:** [Click to Download]({download_url})\n\n"
        f"⚠️ *Note: This link works as long as this bot is running.*"
    )
    
    await message.reply_text(
        text,
        quote=True,
        disable_web_page_preview=True
    )

# --- WEB SERVER ROUTES ---

@routes.get("/")
async def home(request):
    return web.Response(text="Bot is running. Send a file to the bot on Telegram.", content_type='text/plain')

@routes.get("/watch/{link}")
async def watch_player(request):
    link = request.match_info['link']
    stream_url = f"/stream/{link}"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Stream</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ margin: 0; background: #000; display: flex; justify-content: center; align-items: center; height: 100vh; }}
            video {{ width: 100%; max-width: 1000px; height: auto; outline: none; }}
        </style>
    </head>
    <body>
        <video controls autoplay>
            <source src="{stream_url}">
            Your browser does not support video playback.
        </video>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

@routes.get("/stream/{link}")
async def stream_handler(request):
    link = request.match_info['link']
    force_download = request.query.get("download")
    
    msg, media = await get_media_info(link)
    if not media:
        return web.Response(text="404: File not found or Bot can't access it.", status=404)

    file_name = getattr(media, "file_name", "video.mp4")
    file_size = getattr(media, "file_size", 0)
    mime_type = get_mime_type(file_name)

    # Range Handling
    range_header = request.headers.get("Range")
    start = 0
    end = file_size - 1
    status_code = 200

    if range_header:
        range_match = re.search(r'bytes=(\d+)-(\d*)', range_header)
        if range_match:
            start = int(range_match.group(1))
            if range_match.group(2):
                end = int(range_match.group(2))
            status_code = 206

    content_length = end - start + 1
    
    headers = {
        "Content-Type": mime_type,
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Disposition": f'{"attachment" if force_download else "inline"}; filename="{file_name}"'
    }

    if status_code == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"

    response = web.StreamResponse(status=status_code, headers=headers)
    await response.prepare(request)

    try:
        bytes_sent = 0
        async for chunk in app.stream_media(msg, offset=start):
            chunk_size = len(chunk)
            if bytes_sent + chunk_size > content_length:
                await response.write(chunk[:content_length - bytes_sent])
                break
            await response.write(chunk)
            bytes_sent += chunk_size
            if bytes_sent >= content_length:
                break
    except:
        pass

    return response

# --- RUNNER ---

async def main():
    # Start Bot
    await app.start()
    print("Bot Started!")

    # Start Web Server
    app_runner = web.AppRunner(web.Application(client_max_size=1024**3))
    app_runner.app.add_routes(routes)
    await app_runner.setup()
    site = web.TCPSite(app_runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Server running on Port {PORT}")
    
    # Idle
    await asyncio.Event().wait()

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
