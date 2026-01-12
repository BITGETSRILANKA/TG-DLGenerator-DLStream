# 🚀 Telegram Direct Link Generator & Streamer

A high-speed Python web application that converts Telegram file links into **Direct Download URLs** and **Streamable Video Links**. 

Designed to be lightweight, fast, and easily deployable on **Koyeb**, **Render**, or any VPS.

## ✨ Features

- 📥 **Direct Download Links:** Generates permanent links compatible with IDM and browsers.
- 📺 **Browser Streaming:** Watch videos directly in the browser with a built-in player.
- ⏩ **Seek Support:** Supports HTTP Range Requests (scrub forward/backward in videos).
- ⚡ **High Performance:** Uses `Pyrogram` + `TgCrypto` for maximum download speeds.
- ☁️ **No Storage Required:** Streams data directly from Telegram to the user (Middleman/Proxy method).
- 🔒 **Private & Public Channels:** Works with any channel (Bot must be Admin).

---

## 🛠️ Prerequisites

Before deploying, ensure you have the following:

1.  **Telegram API ID & Hash:** Get them from [my.telegram.org](https://my.telegram.org).
2.  **Bot Token:** Get it from [@BotFather](https://t.me/BotFather).
3.  **Koyeb Account:** [Sign up here](https://www.koyeb.com).

---

## 🚀 Deploy on Koyeb (Recommended)

The easiest way to host this application.

1.  **Fork this Repository** (Click the 'Fork' button top right).
2.  Login to **[Koyeb](https://www.koyeb.com)**.
3.  Click **Create App** and select **GitHub**.
4.  Choose the repository you just forked.
5.  In the **Environment Variables** section, add the following:

| Variable | Value | Description |
| :--- | :--- | :--- |
| `API_ID` | `123456` | Your Telegram API ID |
| `API_HASH` | `dxxx...` | Your Telegram API Hash |
| `BOT_TOKEN` | `123:ABC...` | Your Bot Token from BotFather |
| `PORT` | `8000` | The port to listen on (Default: 8000) |

6.  Click **Deploy**.
7.  Wait for the build to finish. Your site will be live at `https://your-app-name.koyeb.app`.

---

## 💻 Local Development

If you want to run this on your local PC or VPS.

1.  **Clone the Repo:**
    ```bash
    git clone https://github.com/your-username/your-repo-name.git
    cd your-repo-name
    ```

2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set Environment Variables:**
    (Linux/Mac)
    ```bash
    export API_ID=123456
    export API_HASH="your_hash"
    export BOT_TOKEN="your_bot_token"
    export PORT=8080
    ```
    (Windows PowerShell)
    ```powershell
    $env:API_ID="123456"
    $env:API_HASH="your_hash"
    $env:BOT_TOKEN="your_bot_token"
    $env:PORT="8080"
    ```

4.  **Run the App:**
    ```bash
    python main.py
    ```

---

## 📖 How to Use

1.  Add your Bot (`@YourBotName`) to your Telegram Channel as an **Admin**.
2.  Upload a file (Video/Document) to that channel.
3.  Right-click the post and select **Copy Post Link**.
    *   *Example:* `https://t.me/my_channel/10`
4.  Open your website URL.
5.  Paste the link and click **Generate**.
6.  Choose **Download** to save or **Watch** to stream inline.

---

## ⚠️ Limitations & Notes

*   **Bandwidth:** The server acts as a proxy. 1GB download = 1GB Incoming + 1GB Outgoing bandwidth on the server.
*   **Speed:** Speed depends on the server's connection to Telegram Data Centers.
*   **Large Files:** Works best with files under 2GB (Standard Bot API limit). For larger files (4GB), you need to implement a Userbot session string (not included in this base version).

---

## 📜 License

This project is licensed under the MIT License.
