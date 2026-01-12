import os
import re
import logging
import mimetypes
import math
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

def get_mime_type(file_name):
    """ improved mime type guessing """
    mime_type, _ = mimetypes.guess_type(file_name)
    if not mime_type:
        ext = file_name.split('.')[-1].lower()
        if ext in ["mkv", "mp4", "webm", "avi", "mov"]:
            return f"video/{ext if ext != 'mkv' else 'x-matroska'}"
        return "application/octet-stream"
    return mime_type

@routes.get("/")
async def home(request):
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>TG Streamer Fixed</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { background: #0f0f0f; color: #eee; font-family: sans-serif; padding: 20px; text-align: center;}
            input { padding: 12px; width: 80%; border-radius: 8px; border: 1px solid #444; background: #222; color: white; }
            button { padding: 12px 24px; border-radius: 8px; border: none; background: #0088cc; color: white; cursor: pointer; margin-top: 10px; }
            .card { background: #1e1e1e; padding: 20px; border-radius: 12px; margin-top: 30px; display: none; }
            a { color: #4db8ff; text-decoration: none; display: block; margin-bottom: 10px; word-break: break-all; }
        </style>
    </head>
    <body>
        <h1>Telegram Direct Stream</h1>
        <form onsubmit="generate(event)">
            <input type="text" id="link" placeholder="https://t.me/channel/123" required>
            <br>
            <button type="submit">Generate Links</button>
        </form>
        
        <div id="result" class="card">
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
                document.getElementById('fname').innerText = "Links Ready";
            }
        </script>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

@routes.get("/watch/{link}")
async def watch_player(request):
    link = request.match_info['link']
    stream_url = f"/stream/{link}"
    
    html = f"""
    <!DOCTYPE html>
    <body style="margin:0; background:black; display:flex; justify-content:center; align-items:center; height:100vh;">
        <video controls autoplay width="100%" height="100%">
            <source src="{stream_url}">
        </video>
    </body>
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
    mime_type = get_mime_type(file_name)

    # --- RANGE REQUEST HANDLING (The Fix) ---
    range_header = request.headers.get("Range")
    
    start = 0
    end = file_size - 1
    status_code = 200

    if range_header:
        # Browser requested a specific part
        range_match = re.search(r'bytes=(\d+)-(\d*)', range_header)
        if range_match:
            start = int(range_match.group(1))
            if range_match.group(2):
                end = int(range_match.group(2))
            status_code = 206 # Partial Content

    content_length = end - start + 1
    
    headers = {
        "Content-Type": mime_type,
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
    }

    if status_code == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"

    if force_download:
        headers["Content-Disposition"] = f'attachment; filename="{file_name}"'
    else:
        headers["Content-Disposition"] = f'inline; filename="{file_name}"'

    response = web.StreamResponse(status=status_code, headers=headers)
    await response.prepare(request)

    # --- PRECISE STREAMING LOGIC ---
    # We must stream EXACTLY 'content_length' bytes, no more, no less.
    
    try:
        # Tell Pyrogram to start fetching from 'start'
        # We handle the 'end' manually to stop the generator
        bytes_sent = 0
        async for chunk in app.stream_media(msg, offset=start):
            chunk_size = len(chunk)
            
            # If sending this whole chunk would exceed the requested range, trim it
            if bytes_sent + chunk_size > content_length:
                remaining_needed = content_length - bytes_sent
                await response.write(chunk[:remaining_needed])
                break
            
            await response.write(chunk)
            bytes_sent += chunk_size
            
            # Stop if we have sent enough data
            if bytes_sent >= content_length:
                break
                
    except Exception as e:
        print(f"Stream Error: {e}")
        # Connection likely closed by browser (normal during seeking)
        pass

    return response

async def main():
    await app.start()
    # Increase client_max_size to handle large headers if needed
    app_runner = web.AppRunner(web.Application(client_max_size=1024**3))
    app_runner.app.add_routes(routes)
    await app_runner.setup()
    site = web.TCPSite(app_runner, "0.0.0.0", PORT)
    await site.start()
    import asyncio
    await asyncio.Event().wait()

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
