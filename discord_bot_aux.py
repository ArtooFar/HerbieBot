import asyncio
import mimetypes
import re
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import discord
from discord import Message


EMOJIS = {
    "EMOJI_TOOL": discord.PartialEmoji(name="nova_ferramenta", id=1452857874295427314)
}

SUPPORTED_IMAGE_MIME_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
}
IMAGE_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
DISCORD_MEDIA_DIR = Path("./data/discord_media")


def _discord_emoji_parser(message : str):
    """Converte emojis do Discord em texto com URL."""
    emoji_pattern = re.compile(r"(<(\w*):(\w+):(\d+)>)")
    found_emojis = emoji_pattern.findall(message)
    for emoji in found_emojis:
        emoji_text = emoji[0]
        emoji_mode = emoji[1]
        emoji_name = emoji[2]
        emoji_id = emoji[3]

        if emoji_mode == 'a':
            message = message.replace(emoji_text,
                                          f"[EMOJI_NAME: {emoji_name}, EMOJI_URL: https://cdn.discordapp.com/emojis/{emoji_id}.gif]")
        else:
            message = message.replace(emoji_text,
                                          f"[EMOJI_NAME: {emoji_name}, EMOJI_URL: https://cdn.discordapp.com/emojis/{emoji_id}.png]")
    return message


def _extract_urls(text: str) -> list[str]:
    return [match.group(0).rstrip(")].,!?:;\"'") for match in IMAGE_URL_PATTERN.finditer(text or "")]


def _infer_mime_from_filename(filename: str) -> str | None:
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type and mime_type.lower() in SUPPORTED_IMAGE_MIME_TYPES:
        return mime_type.lower()
    return None


def _build_dest_path(dest_dir: Path, stem: str, mime_type: str) -> Path:
    suffix = SUPPORTED_IMAGE_MIME_TYPES[mime_type]
    safe_stem = re.sub(r"[^a-zA-Z0-9_.-]+", "_", stem).strip("._") or "imagem"
    return dest_dir / f"{safe_stem}{suffix}"


def _download_image_from_url(url: str, dest_dir: Path, stem: str) -> Path | None:
    request = Request(url, headers={"User-Agent": "HERBIE-Discord/1.0"})
    with urlopen(request, timeout=12) as response:
        content_type = str(response.headers.get_content_type() or "").lower()
        if content_type not in SUPPORTED_IMAGE_MIME_TYPES:
            path_mime = _infer_mime_from_filename(urlparse(url).path)
            if not path_mime:
                return None
            content_type = path_mime
        data = response.read(20 * 1024 * 1024 + 1)
        if len(data) > 20 * 1024 * 1024:
            raise RuntimeError("Imagem por link excede 20 MB.")
        dest_path = _build_dest_path(dest_dir, stem, content_type)
        dest_path.write_bytes(data)
        return dest_path


def user_input_formatter(message: Message, client_user_id) -> str:
    """Formata a mensagem para o prompt do bot.

    Params:
        message: mensagem recebida.
        client_user_id: id do bot para limpar menções.
    """
    br_time = message.created_at.astimezone(ZoneInfo("America/Sao_Paulo"))

    if message.guild is None:
        origem = "Origem: DM (mensagem privada)"
    else:
        origem = (
            f"Origem: Servidor '{message.guild.name}', "
            f"Canal #{message.channel.name} (id={message.channel.id})"
        )

    clean_message = message.content.replace(f'<@{client_user_id}>', '').strip()
    emoji_parsed_message = _discord_emoji_parser(clean_message)
    image_link_count = len(_extract_urls(clean_message))
    attachment_count = len(message.attachments)
    texto = (
        f"{origem}\n"
        f"Usuário: {message.author.name}\n"
        f"Mensagem: {emoji_parsed_message}\n"
        f"Enviado em: {br_time.strftime('%d/%m/%Y %H:%M:%S')}\n"
        f"Imagens por link detectadas: {image_link_count}\n"
    )

    if (attachment_count | len(message.stickers)) > 0:
        texto += "Attachments:\n"
    for attachment in message.attachments:
        texto += (
            f"filename = {attachment.filename}, content_type = {attachment.content_type}, "
            f"url = {attachment.url}\n"
        )
    for sticker in message.stickers:
        texto += f"sticker = {sticker.name}, url = {sticker.url}\n"

    return texto


async def collect_image_file_paths(message: Message, max_images: int = 4) -> list[Path]:
    dest_dir = DISCORD_MEDIA_DIR / f"msg_{message.id}"
    dest_dir.mkdir(parents=True, exist_ok=True)

    collected: list[Path] = []
    seen_urls: set[str] = set()

    for index, attachment in enumerate(message.attachments):
        content_type = str(attachment.content_type or "").lower()
        if content_type not in SUPPORTED_IMAGE_MIME_TYPES:
            inferred = _infer_mime_from_filename(attachment.filename)
            if not inferred:
                continue
            content_type = inferred

        dest_path = _build_dest_path(dest_dir, f"attachment_{index}_{attachment.filename}", content_type)
        await attachment.save(dest_path)
        collected.append(dest_path)
        seen_urls.add(str(attachment.url))
        if len(collected) >= max_images:
            return collected

    urls = _extract_urls(message.content)
    for index, url in enumerate(urls):
        if url in seen_urls:
            continue
        try:
            path = await asyncio.to_thread(_download_image_from_url, url, dest_dir, f"link_{index}")
        except Exception:
            path = None
        if path is None:
            continue
        collected.append(path)
        if len(collected) >= max_images:
            break

    return collected


def generate_on_tools_start(message):
    """Gera callback para reagir quando ferramentas iniciam."""
    async def _do():
        try:
            await message.add_reaction(EMOJIS["EMOJI_TOOL"])
        except Exception:
            pass

    def on_tools_start():
        asyncio.create_task(_do())

    return on_tools_start


async def typing_loop(channel: discord.abc.Messageable, stop_event: asyncio.Event):
    """Mantém o indicador de digitando enquanto ativo."""
    try:
        while not stop_event.is_set():
            async with channel.typing():
                for _ in range(7):
                    if stop_event.is_set():
                        return
                    await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
