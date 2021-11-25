import json
import asyncio
from datetime import datetime
from functools import partial
from telethon import TelegramClient
from telethon.events import NewMessage, CallbackQuery
from telethon.tl.custom import Message, Button
from functions import *
import logging

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s]%(name)s:%(message)s', level=logging.WARNING)

API_ID: int = int(os.environ.get("API_ID", None))
API_HASH: str = os.environ.get("API_HASH", None)
TOKEN: str = os.environ.get("BOT_TOKEN", None)

bot = TelegramClient('bot', API_ID, API_HASH).start(
    bot_token=TOKEN)

permited_users = {}
users_list = {}
empty_list = "Aún ningún archivo para combinar."
formats = ['text/plain', 'application/pdf']

@bot.on(NewMessage(pattern='/get'))
async def get_users(event):
    user_id = event.sender_id
    permited_users = {x.id: x.username for x in await bot.get_participants(user_id, aggressive=True) if not x.bot}

    with open('permitidos.json', 'w') as jsonfile:
        json.dump(permited_users, jsonfile, indent=4)

    await bot.send_message(user_id, json.dumps(permited_users, indent=4))


def filter_type(message: NewMessage):
    if message.file:
        return True


@bot.on(NewMessage(func=filter_type))
async def get_files(event):
    message = event.message
    print(event.sender_id)
    user_id = event.sender_id
    mime_type = message.file.mime_type
    print("file_add")
    if user_id in users_list:
        users_list[user_id][message.id] = mime_type

    else:
        users_list[user_id] = {message.id: mime_type}

    print(users_list)


def is_empty(user_id: str):
    return user_id not in users_list or not users_list[user_id]


@bot.on(NewMessage(pattern='/list'))
async def get_list(event):
    user_id = event.sender_id

    if is_empty(user_id):
        text_to_send = empty_list
    else:
        text_to_send = "**Lista de archivos a combinar por tipo:**\n\n"
        for message_id in users_list[user_id]:
            message = await bot.get_messages(user_id, limit=1, ids=message_id)
            text_to_send += f'**{message.file.name}** : {message.file.mime_type}\n'
        print(users_list[user_id])
    await event.reply(text_to_send)


@bot.on(NewMessage(pattern='/clear'))
async def clear_list(event):
    users_list[event.sender_id] = {}
    await event.reply('Lista limpiada')

@bot.on(NewMessage(pattern='\/compress\s*(\d*)'))
async def compress(event):
    user_id = event.sender_id
    dirpath = Path(f'{user_id}/files')
    size = event.pattern_match.group(1)
    progress_download = await event.respond("Descargando...")
    inicial = datetime.now()
    for message_id in [x for x in users_list[user_id]]:
        message: Message = await bot.get_messages(user_id, limit=1, ids=message_id)
        await download_file(message, progress_download, str(dirpath))
        users_list[user_id].pop(message_id)
    await progress_download.edit(
        f"Descargas finalizadas en {str((datetime.now() - inicial).total_seconds())} segundos, procediendo a comprimir.")

    parts_path = zip_files(dirpath, size)
    await event.respond("Compresión finalizada")
    progress_upload = await event.respond("Subiendo...")
    inicial = datetime.now()
    for file in parts_path.iterdir():
        await upload_file(user_id, file, progress_upload)
    shutil.rmtree(str(parts_path.absolute()))
    await progress_upload.edit(f"Subido en {str((datetime.now() - inicial).total_seconds())} segundos.")


@bot.on(NewMessage(pattern='/merge'))
async def merge_files(event):
    user_id = event.sender_id
    if is_empty(user_id):
        await event.reply(empty_list)
        return
    buttons = [Button.inline(x) for x in formats if x in users_list[user_id].values()]
    await event.reply('Elija el tipo de archivo a combinar:', buttons=buttons)


@bot.on(CallbackQuery)
async def handler(event):
    user_id = event.original_update.user_id
    async with bot.conversation(user_id) as conv:
        message = (await conv.send_message('Diga el nombre del archivo:'))
        name_file_final = (await conv.get_response()).raw_text
        await message.delete()
        conv.cancel()
    loop.create_task(merge(event, user_id, name_file_final))


async def merge(event, user_id, name_file_final):
    mime_type = event.data.decode('utf-8')
    print(mime_type)
    dirpath = f'{user_id}/{mime_type.replace("/","-")}'
    progress_download = await event.respond("Descargando...")
    inicial = datetime.now()
    for message_id in [x for x in users_list[user_id] if users_list[user_id][x] == mime_type]:
        message: Message = await bot.get_messages(user_id, limit=1, ids=message_id)
        await download_file(message, progress_download, dirpath)
        users_list[user_id].pop(message_id)

    await progress_download.edit(
        f"Descargas finalizadas en {str((datetime.now() - inicial).total_seconds())} segundos, procediendo a unir.")

    if mime_type == formats[1]:
        name_file_final = (name_file_final if name_file_final.endswith('.pdf') else name_file_final + '.pdf')
        merge_pdf(dirpath, name_file_final)

    elif mime_type == formats[0]:
        name_file_final = (name_file_final if name_file_final.endswith('.txt') else name_file_final + '.txt')
        merge_txt(dirpath, name_file_final)

    file = f'{user_id}/{name_file_final}'
    inicial = datetime.now()
    progress_upload = await event.respond("Subiendo...")
    await upload_file(user_id, file, progress_upload)
    os.remove(file)
    await progress_upload.edit(f"Subido en {str((datetime.now() - inicial).total_seconds())} segundos.")


async def download_file(message: Message, progress_message: Message, dirpath: str):
    filename = message.text if message.video and message.text else message.file.name
    print(filename)
    filepath = f'{dirpath}/{filename}'
    try:
        file = await message.download_media(file=filepath)
        if file:
            await progress_message.edit("Descarga exitosa")
    except Exception as exc:
        await message.edit(exc)


async def upload_file(user_id: str, file: str, progress_message: Message):
    try:
        await bot.send_file(user_id, file=file)
        await progress_message.edit("Subida exitosa")
    except Exception as exc:
        await progress_message.edit(exc)



async def progress_handler(event: Message, filename: str, message_to_send: str, received_bytes, total_bytes):
    try:
        await event.edit("{0} {1}\nProgreso: {2}%".format(message_to_send
                                                          , filename,
                                                          round(int(received_bytes) * 100 / int(total_bytes), 2))
                         )
    except asyncio.CancelledError as exc:
        raise exc
    except Exception as exc:
        print(exc)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_forever()
