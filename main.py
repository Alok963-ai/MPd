#!/usr/bin/env python3
"""
Telegram Bot to download multiple mpd and m3u8 URLs supplied in a txt file, with no file size limits.

Usage:
- Send a text file containing URLs (one per line) of mpd or m3u8 streams.
- The bot will download each listed stream sequentially.
- Each downloaded video will be sent back to you regardless of file size.
- Owner-only access enforced.

Requirements:
- python-telegram-bot: pip install python-telegram-bot --upgrade
- ffmpeg installed and in system PATH

Note:
- Telegram bots normally have a 50MB file send limit, but this bot will attempt to send large files anyway.
- Large or many files may take time or fail due to Telegram upload restrictions.
"""

import os
import subprocess
import tempfile
from functools import wraps

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Configuration: set your bot token and owner ID here
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
OWNER_ID = 7833842279  # Change to your Telegram user ID (int)

def owner_only(func):
    """Decorator to allow only owner to use the bot."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if user is None or user.id != OWNER_ID:
            if update.message:
                await update.message.reply_text("❌ Unauthorized. You are not allowed to use this bot.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

@owner_only
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message with instructions, styled simply and clearly."""
    # Emulating minimal and elegant messaging with spacing and clarity
    welcome_message = (
        "📥 *Welcome to the Batch Video Downloader Bot!*\n\n"
        "Send me a *TXT* file containing a list of *mpd* or *m3u8* URLs (one per line),\n"
        "and I will download each video stream and send it back to you.\n\n"
        "⚠️ Note: There are _no_ file size limits on downloads. "
        "However, Telegram has upload limits that may prevent very large files from being delivered.\n\n"
        "_Only the owner can use this bot._"
    )
    await update.message.reply_markdown_v2(welcome_message)

@owner_only
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive a text file and process each URL found inside."""
    document = update.message.document
    if not document:
        await update.message.reply_text("⚠️ No document detected. Please send a TXT file with URLs.")
        return

    if not document.file_name.lower().endswith('.txt'):
        await update.message.reply_text("⚠️ Please send a file with .txt extension containing URLs.")
        return

    bot = context.bot
    file = await bot.get_file(document.file_id)
    with tempfile.TemporaryDirectory() as tmpdir:
        txt_fp = os.path.join(tmpdir, "urls.txt")
        await file.download_to_drive(txt_fp)

        # Read and parse URLs
        with open(txt_fp, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Filter valid mpd/m3u8 URLs
        urls = [line.strip() for line in lines if line.strip().lower().endswith(('.mpd', '.m3u8'))]

        if not urls:
            await update.message.reply_text(
                "❌ No valid mpd or m3u8 URLs found in the file.\n"
                "Please check the file and try again."
            )
            return

        await update.message.reply_text(f"🔎 Found *{len(urls)}* valid URLs. Starting downloads...", parse_mode='Markdown')

        # Sequentially process each URL
        for index, url in enumerate(urls, start=1):
            progress_msg = await update.message.reply_text(f"⏳ Downloading ({index}/{len(urls)}):\n{url}")
            video_path = os.path.join(tmpdir, f"video_{index}.mp4")

            ffmpeg_cmd = [
                "ffmpeg",
                "-hide_banner", "-loglevel", "error",
                "-i", url,
                "-c:v", "libx264",
                "-c:a", "aac",
                "-preset", "veryfast",
                "-y",
                video_path,
            ]

            try:
                await bot.send_chat_action(chat_id=OWNER_ID, action=ChatAction.UPLOAD_VIDEO)
                subprocess.run(ffmpeg_cmd, check=True)
            except subprocess.CalledProcessError:
                await update.message.reply_text(f"❌ Failed to download or convert URL:\n{url}")
                await progress_msg.delete()
                continue

            # Attempt to send the video file regardless of size
            try:
                with open(video_path, "rb") as video_file:
                    await bot.send_video(
                        chat_id=OWNER_ID,
                        video=video_file,
                        caption=f"🎬 Video {index} of {len(urls)}",
                        supports_streaming=True,
                    )
            except Exception as e:
                await update.message.reply_text(f"❌ Failed to send video {index}.\nError: {e}")
            await progress_msg.delete()

        await update.message.reply_text("✅ All downloads processed.")

@owner_only
async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ Please send a TXT file with mpd/m3u8 URLs or /start to begin."
    )

async def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message))

    print("Bot started and polling...")
    await application.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

