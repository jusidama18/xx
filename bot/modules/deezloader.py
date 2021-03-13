import os
import re
import shutil
from pathlib import Path
import deezloader  # pylint: disable=W0406
from deezloader.exceptions import NoDataApi

from userge import userge, Message, pool
from userge.plugins.misc.upload import doc_upload, audio_upload

Clogger = userge.getCLogger(__name__)
ARL_TOKEN = os.environ.get("ARL_TOKEN", None)
TEMP_PATH = 'deezdown_temp/'
rex = r"(http:|https:)\/\/(open.spotify|www.deezer).com\/(track|album|playlist)\/[A-Z0-9a-z]{3,}"
ARL_HELP = """**Oops, Time to Help Yourself**
[Here Help Yourself](https://www.google.com/search?q=how+to+get+deezer+arl+token)

After getting Arl token Config `ARL_TOKEN` var in heroku"""


@userge.on_cmd("deezload", about={
    'header': "DeezLoader for Userge",
    'description': "Download Lagu/Albums/Playlists lewat "
                   "Spotify atau Deezer. "
                   "\n<b>NOTE:</b> Kualitas Music itu hanya bonus",
    'flags': {'-sdl': "Download lewat link spotify",
              '-ddl': "Download lewat link deezer",
              '-dsong': "Download sebuah lagu dengan mengetik judul/artis",
              '-zip': "Zip in yang pengen kamu mirror"},
    'Pilihan': "Kualitas tersedia <code>FLAC | MP3_320 | MP3_256 | MP3_128</code>",
    'Penggunaan': "{tr}deezload [flag] [link | quality (standar MP3_320)]",
    'Misal': "{tr}deezload -ddl https://www.deezer.com/track/142750222 \n"
                "{tr}deezload -ddl https://www.deezer.com/track/3824710 FLAC \n"
                "{tr}deezload -ddl https://www.deezer.com/album/1240787 FLAC \n"
                "{tr}deezload -ddl -zip https://www.deezer.com/album/1240787 \n"
                "{tr}deezload -dsong Ed Sheeran-Shape of You"})
async def deezload(message: Message):
    if not os.path.exists(TEMP_PATH):
        os.makedirs(TEMP_PATH)
    if not message.flags:
        await message.edit("Hello🙂, This Plugin requires a proper flag to be passed.")
        return
    await message.edit("Bentar lagi cek token")
    if ARL_TOKEN is None:
        await message.edit(ARL_HELP, disable_web_page_preview=True)
        return
    try:
        loader = deezloader.Login(ARL_TOKEN)
    except Exception as er:
        await message.edit(er)
        await Clogger.log(f"#ERROR\n\n{er}")
        return

    flags = list(message.flags)
    if '-zip' not in flags:
        to_zip = False
    else:
        to_zip = True
    d_quality = "MP3_320"
    if not message.filtered_input_str:
        await message.edit("Hadehhh link nya mana mastahh`")
        return
    input_ = message.filtered_input_str
    if '-dsong' not in flags:
        try:
            input_link, quality = input_.split()
        except ValueError:
            if len(input_.split()) == 1:
                input_link = input_
                quality = d_quality
            else:
                await message.edit("Syntax gagal 🙂")
                return
        if not re.search(rex, input_link):
            await message.edit("Link nya ga support nih :(.")
            return
    elif '-dsong' in flags:
        try:
            artist, song, quality = input_.split('-')
        except ValueError:
            if len(input_.split("-")) == 2:
                artist, song = input_.split('-')
                quality = d_quality
            else:
                await message.edit("Hmm")
                return
    try:
        if '-sdl' in flags:
            if 'track/' in input_link:
                await proper_trackdl(input_link, quality, message, loader, TEMP_PATH)
            elif 'album/' or 'playlist/' in input_link:
                await batch_dl(input_link, quality, message, loader, TEMP_PATH, to_zip)
        elif '-ddl' in flags:
            if 'track/' in input_link:
                await proper_trackdl(input_link, quality, message, loader, TEMP_PATH)
            elif 'album/' or 'playlist/' in input_link:
                await batch_dl(input_link, quality, message, loader, TEMP_PATH, to_zip)
    except NoDataApi as nd:
        await message.edit("Data nya ngk ada om :(")
        await Clogger.log(f"#ERROR\n\n{nd}")
    except Exception as e_r:
        await Clogger.log(f"#ERROR\n\n{e_r}")

    if '-dsong' in flags:
        await message.edit(f"Bentar lagi nyari {song}")
        try:
            track = await pool.run_in_thread(loader.download_name)(
                artist=artist.strip(),
                song=song.strip(),
                output=TEMP_PATH,
                quality=quality.strip(),
                recursive_quality=True,
                recursive_download=True,
                not_interface=True
            )
            await message.edit("Lagu yang kamu cari ada, bentar lg upload 📤", del_in=5)
            await audio_upload(message, Path(track), True)
        except Exception as e_r:
            await message.edit("Lagu nya gk ada :(🚫")
            await Clogger.log(f"#ERROR\n\n{e_r}")

    await message.delete()
    shutil.rmtree(TEMP_PATH, ignore_errors=True)


async def proper_trackdl(link, qual, msg, client, dir_):
    if 'spotify' in link:
        await msg.edit("Bentar lagi download")
        track = await pool.run_in_thread(client.download_trackspo)(
            link,
            output=dir_,
            quality=qual,
            recursive_quality=True,
            recursive_download=True,
            not_interface=True
        )
        await msg.edit("Download Berhasil.", del_in=5)
        await audio_upload(msg, Path(track), True)
    elif 'deezer' in link:
        await msg.edit("Download Started. Wait Plox.")
        track = await pool.run_in_thread(client.download_trackdee)(
            link,
            output=dir_,
            quality=qual,
            recursive_quality=True,
            recursive_download=True,
            not_interface=True
        )
        await msg.edit("Download Berhasil", del_in=5)
        await audio_upload(msg, Path(track), True)


async def batch_dl(link, qual, msg, client, dir_, allow_zip):
    if 'spotify' in link:
        if 'album/' in link:
            await msg.edit("Bentar lagi download Album kamu🤧")
            if allow_zip:
                _, zip_ = await pool.run_in_thread(client.download_albumspo)(
                    link,
                    output=dir_,
                    quality=qual,
                    recursive_quality=True,
                    recursive_download=True,
                    not_interface=True,
                    zips=True
                )
                await msg.edit("Kirim file yg kamu pengen jadi zip🗜")
                await doc_upload(msg, Path(zip_), True)
            else:
                album_list = await pool.run_in_thread(client.download_albumspo)(
                    link,
                    output=dir_,
                    quality=qual,
                    recursive_quality=True,
                    recursive_download=True,
                    not_interface=True,
                    zips=False)
                await msg.edit("Unggah Track kamu📤", del_in=5)
                for track in album_list:
                    await audio_upload(msg, Path(track), True)
        if 'playlist/' in link:
            await msg.edit("Bentar lagi download playlist kamu 🎶")
            if allow_zip:
                _, zip_ = await pool.run_in_thread(client.download_playlistspo)(
                    link,
                    output=dir_,
                    quality=qual,
                    recursive_quality=True,
                    recursive_download=True,
                    not_interface=True,
                    zips=True
                )
                await msg.edit("Kirim jadi zip 🗜", del_in=5)
                await doc_upload(msg, Path(zip_), True)
            else:
                album_list = await pool.run_in_thread(client.download_playlistspo)(
                    link,
                    output=dir_,
                    quality=qual,
                    recursive_quality=True,
                    recursive_download=True,
                    not_interface=True,
                    zips=False
                )
                await msg.edit("Mengirim Trak📤", del_in=5)
                for track in album_list:
                    await audio_upload(msg, Path(track), True)

    if 'deezer' in link:
        if 'album/' in link:
            await msg.edit("Bentar lagi download album kamu🤧")
            if allow_zip:
                _, zip_ = await pool.run_in_thread(client.download_albumdee)(
                    link,
                    output=dir_,
                    quality=qual,
                    recursive_quality=True,
                    recursive_download=True,
                    not_interface=True,
                    zips=True
                )
                await msg.edit("Kirim jadi zip🗜", del_in=5)
                await doc_upload(msg, Path(zip_), True)
            else:
                album_list = await pool.run_in_thread(client.download_albumdee)(
                    link,
                    output=dir_,
                    quality=qual,
                    recursive_quality=True,
                    recursive_download=True,
                    not_interface=True,
                    zips=False
                )
                await msg.edit("Kirim track 📤", del_in=5)
                for track in album_list:
                    await audio_upload(msg, Path(track), True)
        elif 'playlist/' in link:
            await msg.edit("Bentar lagi download playlist kamu")
            if allow_zip:
                _, zip_ = await pool.run_in_thread(client.download_playlistdee)(
                    link,
                    output=dir_,
                    quality=qual,
                    recursive_quality=True,
                    recursive_download=True,
                    not_interface=True,
                    zips=True
                )
                await msg.edit("Kirim file jadi zip 🗜", del_in=5)
                await doc_upload(msg, Path(zip_), True)
            else:
                album_list = await pool.run_in_thread(client.download_playlistdee)(
                    link,
                    output=dir_,
                    quality=qual,
                    recursive_quality=True,
                    recursive_download=True,
                    not_interface=True,
                    zips=False
                )
                await msg.edit("Kirim track📤", del_in=5)
                for track in album_list:
                    await audio_upload(msg, Path(track), True)
