
import asyncio
import os
import secrets
import subprocess
import tempfile
from pathlib import Path

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, Update, FSInputFile

TOKEN = os.environ["BOT_TOKEN"]
HOST = os.environ["RENDER_EXTERNAL_HOSTNAME"]
SECRET = os.getenv("WEBHOOK_SECRET") or secrets.token_urlsafe(32)

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(F.text == "/start")
async def start(message: Message):
    await message.answer(
        "Привет! 🖤 Отправь кружочек, "
        "и я сделаю чёрный фон!"
    )


@dp.message(F.video_note | F.video)
async def process_video(message: Message):
    status = await message.answer("⏳ Обрабатываю видео...")

    file_id = (
        message.video_note.file_id
        if message.video_note
        else message.video.file_id
    )

    try:
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "input.mp4"
            dst = Path(tmp) / "output.mp4"

            await bot.download(file_id, destination=src)

            filters = (
                "[0:v]scale=640:640:"
                "force_original_aspect_ratio=increase,"
                "crop=640:640,format=rgba,"
                "geq=r='r(X,Y)':g='g(X,Y)':"
                "b='b(X,Y)':"
                "a='if(lte(pow(X-W/2,2)+pow(Y-H/2,2),"
                "pow(min(W,H)/2,2)),255,0)'[circle];"
                "color=c=black:s=1080x1920:r=30[bg];"
                "[bg][circle]overlay=(W-w)/2:(H-h)/2:"
                "shortest=1,format=yuv420p[outv]"
            )

            result = subprocess.run(
                [
                    "ffmpeg", "-y", "-i", str(src),
                    "-filter_complex", filters,
                    "-map", "[outv]", "-map", "0:a?",
                    "-c:v", "libx264", "-preset", "ultrafast",
                    "-crf", "23", "-c:a", "aac",
                    "-shortest", "-movflags", "+faststart",
                    str(dst)
                ],
                capture_output=True,
                text=True,
                timeout=180
            )

            if result.returncode != 0:
                raise RuntimeError(result.stderr[-1000:])

            await message.answer_video(
                FSInputFile(dst),
                caption="Готово! 🖤"
            )

        await status.delete()

    except Exception as e:
        print("ERROR:", e)
        await status.edit_text("Ошибка обработки. Попробуй другое видео.")


async def webhook(request):
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != SECRET:
        raise web.HTTPForbidden()

    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot, update)
    return web.Response(text="OK")


async def health(request):
    return web.Response(text="Bot is running")


async def on_startup(app):
    await bot.set_webhook(
        f"https://{HOST}/webhook",
        secret_token=SECRET,
        drop_pending_updates=True
    )
    print("Webhook started!")


async def on_cleanup(app):
    await bot.delete_webhook()
    await bot.session.close()


app = web.Application()
app.router.add_post("/webhook", webhook)
app.router.add_get("/", health)
app.on_startup.append(on_startup)
app.on_cleanup.append(on_cleanup)


if __name__ == "__main__":
    web.run_app(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
