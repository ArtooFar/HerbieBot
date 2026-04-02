import asyncio
import logging
import os
from pathlib import Path

import discord
import dotenv

dotenv.load_dotenv()

import discord_bot_aux as daux
from core.configs import safety_config_list
from core.internals.neo_core import GeminiAgentCore
from core.notifications.connectivity_monitor import mark_offline, mark_online
from core.notifications.discord_dm_notifier import DiscordDMNotifier
from core.notifications.google_notification_sync import GoogleNotificationSync
from core.notifications.notification_dispatcher import NotificationDispatcher
from core.notifications.notification_runtime import set_current_discord_message_context
from core.notifications.notification_store import NotificationStore
from core.output_handlers import bot_output_discord
from core.tools.init import build_tool_list

# Configuração de logging

discord_token = os.getenv("DISCORD_TOKEN")

handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

discord_send_queue = asyncio.Queue()
notification_stop_event = asyncio.Event()
notification_dispatcher_task: asyncio.Task | None = None
sender_worker_task: asyncio.Task | None = None

bot_chat = GeminiAgentCore(
    api_key=os.getenv("GEMINI_API_KEY"),
    model="gemini-2.5-flash",
    safety_setting_list=safety_config_list,
    system_prompt_path=Path("prompts/system_prompt.txt"),
    summary_prompt_path=Path("prompts/summary_prompt.txt"),
    extra_system_prompt_paths=[Path("prompts/discord_chat_system.txt")],
    summary_persistence_path=Path("data/conversation_summary.txt"),
)
bot_chat.register_tools(build_tool_list(bot_chat))


@client.event
async def on_ready():
    """Inicializa o bot e os workers de envio/notificação."""
    global notification_dispatcher_task, sender_worker_task

    print(f"We have logged in as {client.user}")
    mark_online(source="discord_ready", reason="Cliente Discord pronto")

    if sender_worker_task is None or sender_worker_task.done():
        sender_worker_task = client.loop.create_task(discord_sender_worker())

    if notification_dispatcher_task is None or notification_dispatcher_task.done():
        store = NotificationStore()
        notifier = DiscordDMNotifier(client=client, send_queue=discord_send_queue)
        syncer = GoogleNotificationSync(store=store)
        dispatcher = NotificationDispatcher(store=store, notifier=notifier, agent=bot_chat, syncer=syncer)
        notification_dispatcher_task = client.loop.create_task(
            dispatcher.run_forever(notification_stop_event)
        )


@client.event
async def on_disconnect():
    mark_offline(source="discord_disconnect", reason="Gateway do Discord desconectado")


@client.event
async def on_resumed():
    mark_online(source="discord_resumed", reason="Gateway do Discord reconectado")


@client.event
async def on_message(message):
    """Processa mensagens recebidas e aciona o chat."""
    if message.author == client.user:
        return

    if (client.user in message.mentions) or (message.guild is None):
        set_current_discord_message_context(message)

        bot_chat.output_handler = bot_output_discord.DiscordOutput(
            message=message,
            send_queue=discord_send_queue,
        )

        formatted_prompt = daux.user_input_formatter(
            message=message,
            client_user_id=client.user.id,
        )
        image_file_paths = await daux.collect_image_file_paths(message)
        if image_file_paths:
            bot_chat.output_handler.system_sendout(
                f"[SISTEMA] {len(image_file_paths)} imagem(ns) da mensagem foram anexadas ao contexto visual."
            )

        bot_chat.output_handler.system_sendout(formatted_prompt)

        bot_chat.on_toolcall_start = daux.generate_on_tools_start(message=message)

        async with asyncio.TaskGroup() as tg:
            stop_typing = asyncio.Event()
            tg.create_task(daux.typing_loop(message.channel, stop_typing))

            try:
                await bot_chat.chat(prompt=formatted_prompt, file_paths=image_file_paths)
            except Exception as e:
                bot_chat.output_handler.sendout(
                    f"[ERRO] Deu ruim processando sua mensagem: {type(e).__name__}: {e}"
                )
            finally:
                stop_typing.set()


async def discord_sender_worker():
    """Envia mensagens/arquivos da fila com controle de rate e ack opcional."""
    while True:
        payload = await discord_send_queue.get()
        try:
            if payload is None:
                return

            channel = payload["channel"]
            content = payload.get("content")
            file_path = payload.get("file_path")
            ack_future = payload.get("ack_future")

            try:
                if file_path:
                    result = await channel.send(
                        content=content or None,
                        file=discord.File(file_path),
                    )
                else:
                    result = await channel.send(content)

                if ack_future is not None and not ack_future.done():
                    ack_future.set_result(result)
            except Exception as exc:
                print(f"[WARN] Falha no sender do Discord: {type(exc).__name__}: {exc}")
                if ack_future is not None and not ack_future.done():
                    ack_future.set_exception(exc)
            finally:
                await asyncio.sleep(0.35)
        finally:
            discord_send_queue.task_done()


async def graceful_shutdown(client: discord.Client):
    """Finaliza o bot aguardando a fila e o dispatcher."""
    notification_stop_event.set()
    if notification_dispatcher_task is not None:
        await notification_dispatcher_task

    await discord_send_queue.join()
    discord_send_queue.put_nowait(None)
    await client.close()


client.run(discord_token, log_handler=handler, log_level=logging.DEBUG)
