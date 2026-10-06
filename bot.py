import os
import asyncio
import discord
from discord.ext import commands, tasks
from aiohttp import web

# --- BOT VE SUNUCU AYARLARI ---
TOKEN = os.environ.get("DISCORD_TOKEN")  # Render Environment Variable
CHANNEL_ID = 1555639349163331647        # Ses kanalının ID'si
ROLE_ID = 1555651923883855902            # Otomatik verilecek ROLÜN ID'si
KEYWORD = "/slowenya"                    # Profilde aranacak kelime

# --- INTENTS (Presence ve Members Zorunludur) ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.presences = True                # Profil durumlarını okumak için
intents.members = True                  # Üyeleri takip etmek için

bot = commands.Bot(command_prefix="!", intents=intents)

# --- RENDER KEEP-ALIVE (WEB SERVER) ---
async def handle_ping(request):
    return web.Response(text="Bot 7/24 Aktif!", status=200)

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    app.router.add_get('/ping', handle_ping)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render'ın atadığı PORT değişkenini oku, varsayılan 8080
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"[WEB SERVER] {port} portunda sorunsuz başlatıldı.")

# --- SESSİZLİK (SILENCE) SES KAYNAĞI ---
class SilenceAudio(discord.AudioSource):
    def read(self):
        return b'\xf8\xff\xfe'  # 20ms'lik sessiz Opus paketi

# --- SES KANALINA BAĞLANMA FONKSİYONU ---
async def join_voice_channel():
    await bot.wait_until_ready()
    channel = bot.get_channel(CHANNEL_ID)
    
    if not channel or not isinstance(channel, discord.VoiceChannel):
        print("Hata: Belirtilen ID'ye sahip geçerli bir ses kanalı bulunamadı.")
        return

    while not bot.is_closed():
        try:
            voice_client = discord.utils.get(bot.voice_clients, guild=channel.guild)
            
            # Bağlantı yoksa veya kopmuşsa
            if voice_client is None or not voice_client.is_connected():
                if voice_client is not None:
                    await voice_client.disconnect(force=True)
                
                vc = await channel.connect(reconnect=True, self_deaf=True)
                print(f"[{channel.guild.name}] - '{channel.name}' kanalına bağlandı.")
                
                if not vc.is_playing():
                    vc.play(SilenceAudio())
            
            # Bağlantı var ama sessiz paket durmuşsa tekrar başlat
            elif not voice_client.is_playing():
                voice_client.play(SilenceAudio())

        except Exception as e:
            print(f"Ses kanalına bağlanırken hata oluştu: {e}")
        
        await asyncio.sleep(15)

# --- DURUM / PROFIL KONTROL DÖNGÜSÜ ---
@tasks.loop(minutes=1)
async def check_statuses():
    await bot.wait_until_ready()
    for guild in bot.guilds:
        role = guild.get_role(ROLE_ID)
        if not role:
            continue
            
        for member in guild.members:
            if member.bot:
                continue
                
            has_keyword = False
            
            # Üyenin Özel Durumunu (Custom Status) Kontrol Et
            for activity in member.activities:
                if isinstance(activity, discord.CustomActivity):
                    if activity.name and KEYWORD.lower() in activity.name.lower():
                        has_keyword = True
                        break
                    if activity.state and KEYWORD.lower() in activity.state.lower():
                        has_keyword = True
                        break

            # Şartı sağlıyorsa ve rolü yoksa ver
            if has_keyword:
                if role not in member.roles:
                    try:
                        await member.add_roles(role)
                        print(f"[ROL VERİLDİ] {member.display_name} -> {role.name}")
                    except Exception as e:
                        print(f"Rol verilirken hata ({member.display_name}): {e}")
            # Şartı sağlamıyorsa ama önceden rolü varsa çıkar
            else:
                if role in member.roles:
                    try:
                        await member.remove_roles(role)
                        print(f"[ROL ALINDI] {member.display_name} -> {role.name}")
                    except Exception as e:
                        print(f"Rol alınırken hata ({member.display_name}): {e}")

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f"{bot.user.name} olarak başarıyla giriş yapıldı!")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="7/24 Ses Modu"))
    if not check_statuses.is_running():
        check_statuses.start()

@bot.event
async def on_presence_update(before, after):
    if after.bot:
        return
        
    guild = after.guild
    role = guild.get_role(ROLE_ID)
    if not role:
        return
        
    has_keyword = False
    for activity in after.activities:
        if isinstance(activity, discord.CustomActivity):
            if activity.name and KEYWORD.lower() in activity.name.lower():
                has_keyword = True
                break
            if activity.state and KEYWORD.lower() in activity.state.lower():
                has_keyword = True
                break

    if has_keyword and role not in after.roles:
        try:
            await after.add_roles(role)
            print(f"[ANLIK ROL VERİLDİ] {after.display_name} -> {role.name}")
        except Exception as e:
            print(f"Rol verilirken hata: {e}")
    elif not has_keyword and role in after.roles:
        try:
            await after.remove_roles(role)
            print(f"[ANLIK ROL ALINDI] {after.display_name} -> {role.name}")
        except Exception as e:
            print(f"Rol alınırken hata: {e}")

# --- ANA ÇALIŞTIRICI ---
async def main():
    async with bot:
        await start_web_server()
        bot.loop.create_task(join_voice_channel())
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())