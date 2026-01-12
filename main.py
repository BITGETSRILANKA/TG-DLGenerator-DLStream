import os
import re
import math
import logging
import mimetypes
from aiohttp import web
from pyrogram import Client

# --- CONFIGURATION (Env Vars) ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
PORT = int(os.environ.get("PORT", 8080))

# Initialize Client
app = Client(
    "koyeb_server",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

routes = web.RouteTableDef()

def parse_link(link):
    """Extracts Chat ID and Message ID"""
    patterns = [
        r"t\.me/c/(\d+)/(\d+)",
        r"t\.me/([^/]+)/(\d+)"
    ]
    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            chat = match.group(1)
            msg_id = int(match.group(2))
            if chat.isdigit():
                chat = int(f"-100{chat}")
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
    except: return None, None

@routes.get("/")
async def home(request):
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>TG Streamer</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { background: #0f0f0f; color: #eee; font-family: system-ui, sans-serif; padding: 20px; text-align: center;}
            input { padding: 12px; width: 80%; max-width: 400px; border-radius: 8px; border: 1px solid #444; background: #222; color: white; outline: none; }
            button { padding: 12px 24px; border-radius: 8px; border: none; background: #0088cc; color: white; cursor: pointer; font-weight: bold; margin-top: 10px; }
            button:hover { background: #0077b5; }
            .card { background: #1e1e1e; padding: 20px; border-radius: 12px; margin-top: 30px; display: inline-block; text-align: left; max-width: 90%; }
            a { color: #4db8ff; text-decoration: none; word-break: break-all; display: block; margin-bottom: 10px; }
            h3 { margin-top: 0; }
        </style>
    </head>
    <body>
        <h1>Telegram Direct Stream</h1>
        <form onsubmit="generate(event)">
            <input type="text" id="link" placeholder="https://t.me/channel/123" required>
            <br>
            <button type="submit">Generate Links</button>
        </form>
        
        <div id="result" style="display:none;" class="card">
            <h3 id="fname">File Name</h3>
            <p>👇 <b>Direct Download:</b></p>
            <a id="dl_btn" href="#">Download Link</a>
            
            <p>📺 <b>Watch in Browser:</b></p>
            <a id="watch_btn" href="#">Stream Page</a>
        </div>

        <script>
            function generate(e) {
                e.preventDefault();
                const link = document.getElementById('link').value;
                const safeLink = encodeURIComponent(link);
                const domain = window.location.origin;

                document.getElementById('result').style.display = 'block';
                document.getElementById('fname').innerText = "Generating...";
                
                const dl = `${domain}/stream/${safeLink}?download=true`;
                const watch = `${domain}/watch/${safeLink}`;

                document.getElementById('dl_btn').href = dl;
                document.getElementById('dl_btn').innerText = dl;
                
                document.getElementById('watch_btn').href = watch;
                document.getElementById('watch_btn').innerText = watch;
                
                document.getElementById('fname').innerText = "Links Ready:";
            }
        </script>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

@routes.get("/watch/{link}")
async def watch_player(request):
    """Returns a page with a Video Player embedded"""
    link = request.match_info['link']
    decoded_link = link # Already safe via match_info
    stream_url = f"/stream/{link}"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Watching...</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ margin: 0; background: black; display: flex; justify-content: center; align-items: center; height: 100vh; }}
            video {{ width: 100%; max-width: 1000px; height: auto; max-height: 100vh; }}
        </style>
    </head>
    <body>
        <video controls autoplay>
            <source src="{stream_url}" type="video/mp4">
            Your browser does not support the video tag.
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
        return web.Response(text="404: Media not found", status=404)

    file_name = getattr(media, "file_name", "video.mp4")
    file_size = getattr(media, "file_size", 0)
    mime_type = getattr(media, "mime_type", mimetypes.guess_type(file_name)[0] or "video/mp4")

    # --- HANDLE RANGE REQUESTS (Seeking) ---
    range_header = request.headers.get("Range")
    
    if range_header:
        # Browser wants a specific part (seeking)
        from_bytes, until_bytes = range_header.replace("bytes=", "").split("-")
        from_bytes = int(from_bytes)
        until_bytes = int(until_bytes) if until_bytes else file_size - 1
        
        content_length = until_bytes - from_bytes + 1
        status = 206
        
        headers = {
            "Content-Type": mime_type,
            "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
            "Content-Length": str(content_length),
            "Accept-Ranges": "bytes",
        }
    else:
        # Full download
        from_bytes = 0
        until_bytes = file_size - 1
        content_length = file_size
        status = 200
        
        headers = {
            "Content-Type": mime_type,
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        }
        if force_download:
             headers["Content-Disposition"] = f'attachment; filename="{file_name}"'
        else:
             headers["Content-Disposition"] = f'inline; filename="{file_name}"'

    response = web.StreamResponse(status=status, headers=headers)
    await response.prepare(request)

    # Calculate offset and chunk limit for Pyrogram
    # We stream exactly what the browser asked for
    offset = from_bytes
    limit = content_length 

    try:
        async for chunk in app.stream_media(msg, offset=offset, limit=limit):
            await response.write(chunk)
    except Exception:
        pass # Handle client disconnection gracefully

    return response

async def main():
    await app.start()
    app_runner = web.AppRunner(web.Application(client_max_size=1024**3))
    app_runner.app.add_routes(routes)
    await app_runner.setup()
    site = web.TCPSite(app_runner, "0.0.0.0", PORT)
    await site.start()
    
    # Keep running
    import asyncio
    await asyncio.Event().wait()

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
