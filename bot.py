
import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(F.text == "/start")
async def start(message: Message):
    await message.answer(
        "Привет! 🖤 Отправь мне кружочек, "
        "и я сделаю чёрный фон для твоего видео."
    )


@dp.message(F.video_note | F.video)
async def process_video(message: Message):
    status = await message.answer("⏳ Делаю чёрный фон...")

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
                "crop=640:640,setsar=1,format=rgba,"
                "geq=r='r(X,Y)':g='g(X,Y)':"
                "b='b(X,Y)':"
                "a='if(lte(pow(X-W/2,2)+pow(Y-H/2,2),"
                "pow(min(W,H)/2,2)),255,0)'[circle];"
                "color=c=black:s=1080x1920:r=30[bg];"
                "[bg][circle]overlay=(W-w)/2:(H-h)/2:"
                "shortest=1,format=yuv420p[outv]"
            )

            command = [
                "ffmpeg", "-y", "-i", str(src),
                "-filter_complex", filters,
                "-map", "[outv]", "-map", "0:a?",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-crf", "22", "-c:a", "aac",
                "-shortest", "-movflags", "+faststart",
                str(dst)
            ]

            result = subprocess.run(
                command, capture_output=True, text=True
            )

            if result.returncode != 0:
                raise RuntimeError(result.stderr[-1500:])

            await message.answer_video(
                FSInputFile(dst),
                caption="Готово! 🖤"
            )

            await status.delete()

    except Exception as error:
        print(error)
        await status.edit_text(
            "Не удалось обработать видео. Попробуй ещё раз."
        )


async def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN не задан")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
