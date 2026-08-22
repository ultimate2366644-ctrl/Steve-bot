import discord
from discord.ext import commands
import os
from PIL import Image, ImageDraw, ImageFont
import io
import aiohttp
from dotenv import load_dotenv
import motor.motor_asyncio

load_dotenv()

# ==========================================
# ⚙️ 1. إعدادات البوت والـ Intents
# ==========================================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================================
# 📊 2. إعدادات الـ IDs والمستويات والألوان
# ==========================================
LEVEL_UP_CHANNEL_ID = 1535716236665683988
BOOST_XP_REWARD = 1000

CENTRAL_KEY_ROLE_ID = 1535724919705567284

LEVEL_ROLES = {
    5: 1535727707000672346,
    10: 1535729181969752289,
    20: 1535718824069046415,
    35: CENTRAL_KEY_ROLE_ID,
    50: 1535728454106873916
}

COLOR_ROLES = {
    "red": 1536363420423819325,
    "purple": 1536363925111705640,
    "blue": 1536364244004503572
}

# ==========================================
# 🍃 3. الاتصال بـ MongoDB وإدارة البيانات
# ==========================================
MONGO_URI = os.getenv("MONGO_URI")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = client["DiscordBot"]
collection = db["users_xp"]

async def get_user_data(user_id: str):
    data = await collection.find_one({"_id": str(user_id)})
    if not data:
        return {"_id": str(user_id), "xp": 0, "level": 1}
    return data

async def update_user_data(user_id: str, xp: int, level: int):
    await collection.update_one(
        {"_id": str(user_id)},
        {"$set": {"xp": xp, "level": level}},
        upsert=True
    )

def get_next_level_xp(level: int) -> int:
    return 5 * (level ** 2) + (50 * level) + 100

async def get_user_rank(user_id: str) -> int:
    user_data = await get_user_data(user_id)
    user_xp = user_data.get("xp", 0)
    count = await collection.count_documents({"xp": {"$gt": user_xp}})
    return count + 1

# ==========================================
# 🎨 4. دالة إنشاء بطاقة الـ Rank
# ==========================================
async def generate_rank_card(
    member: discord.Member,
    level: int,
    current_xp: int,
    next_level_xp: int,
    rank_position: int = 1
):
    card = Image.new("RGBA", (1200, 400), color=(15, 16, 18, 255))
    draw = ImageDraw.Draw(card)

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(BASE_DIR, "roboto.ttf")

    timeout = aiohttp.ClientTimeout(total=10)

    if not os.path.exists(font_path):
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get("https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf") as resp:
                    if resp.status == 200:
                        with open(font_path, "wb") as f:
                            f.write(await resp.read())
        except Exception as e:
            print(f"⚠️ فشل تنزيل ملف الخط: {e}")

    try:
        font_name = ImageFont.truetype(font_path, 50)
        font_stats = ImageFont.truetype(font_path, 50)
        font_sub = ImageFont.truetype(font_path, 32)
        font_xp = ImageFont.truetype(font_path, 34)
    except Exception:
        font_name = font_stats = font_sub = font_xp = ImageFont.load_default()

    avatar_url = member.display_avatar.with_format("png").url
    avatar_bytes = None
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(avatar_url) as resp:
                if resp.status == 200:
                    avatar_bytes = await resp.read()
    except Exception as e:
        print(f"⚠️ فشل تنزيل الأفاتار: {e}")

    if avatar_bytes:
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    else:
        avatar = Image.new("RGBA", (200, 200), color=(100, 100, 100, 255))

    avatar_size = (200, 200)
    avatar = avatar.resize(avatar_size)

    mask = Image.new("L", avatar_size, 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, avatar_size[0], avatar_size[1]), fill=255)

    card.paste(avatar, (50, 100), mask)

    draw.text((285, 150), member.name, font=font_name, fill=(255, 255, 255, 255))

    NEW_COLOR = (188, 201, 247, 255)

    draw.text((880, 80), f"#{rank_position}", font=font_stats, fill=(255, 255, 255, 255), anchor="mm")
    draw.text((880, 135), "RANK", font=font_sub, fill=NEW_COLOR, anchor="mm")

    draw.text((1080, 80), f"{level:02d}", font=font_stats, fill=(255, 255, 255, 255), anchor="mm")
    draw.text((1080, 135), "LEVEL", font=font_sub, fill=NEW_COLOR, anchor="mm")

    xp_text = f"{current_xp} XP / {next_level_xp} XP"
    draw.text((950, 225), xp_text, font=font_xp, fill=(200, 200, 200, 255), anchor="mm")

    bar_x, bar_y = 285, 275
    bar_width, bar_height = 830, 40

    draw.rounded_rectangle(
        [bar_x, bar_y, bar_x + bar_width, bar_y + bar_height],
        radius=20,
        fill=(50, 53, 59, 255)
    )

    progress = min(current_xp / next_level_xp, 1.0) if next_level_xp > 0 else 0
    filled_width = int(bar_width * progress)

    if filled_width > 0:
        draw.rounded_rectangle(
            [bar_x, bar_y, bar_x + filled_width, bar_y + bar_height],
            radius=20,
            fill=NEW_COLOR
        )

    buffer = io.BytesIO()
    card.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(buffer, filename="rank_card.png")

# ==========================================
# 🚀 5. الأحداث (Events)
# ==========================================
@bot.event
async def on_ready():
    print(f"✅ تم تسجيل الدخول بنجاح باسم البوت: {bot.user.name}")
    print("🍃 متصل بقاعدة بيانات MongoDB بنجاح!")

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if before.premium_since is None and after.premium_since is not None:
        user_id = str(after.id)
        user_data = await get_user_data(user_id)

        xp = user_data["xp"] + BOOST_XP_REWARD
        lvl = user_data["level"]
        next_level_xp = get_next_level_xp(lvl)

        while xp >= next_level_xp:
            lvl += 1
            next_level_xp = get_next_level_xp(lvl)

        await update_user_data(user_id, xp, lvl)

        level_channel = bot.get_channel(LEVEL_UP_CHANNEL_ID)
        if level_channel:
            await level_channel.send(
                f"🚀 **شكرًا جزيلًا {after.mention}!**\n"
                f"لقد قمت بعمل Boost للسيرفر وحصلت على مكافأة قدرها **+{BOOST_XP_REWARD} XP**! 🎉"
            )

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    if message.content.startswith("!"):
        await bot.process_commands(message)
        return

    user_id = str(message.author.id)
    user_data = await get_user_data(user_id)

    xp = user_data["xp"] + 15
    lvl = user_data["level"]
    next_level_xp = get_next_level_xp(lvl)

    if xp >= next_level_xp:
        while xp >= get_next_level_xp(lvl):
            lvl += 1

        await update_user_data(user_id, xp, lvl)

        level_channel = bot.get_channel(LEVEL_UP_CHANNEL_ID)
        new_next_xp = get_next_level_xp(lvl)

        if level_channel:
            user_rank = await get_user_rank(user_id)
            rank_file = await generate_rank_card(message.author, lvl, xp, new_next_xp, rank_position=user_rank)
            await level_channel.send(
                content=f"🎉 **مبروك {message.author.mention}!** ارتقيت إلى **المستوى {lvl}**!",
                file=rank_file
            )

            if lvl in LEVEL_ROLES:
                role_id = LEVEL_ROLES[lvl]
                role = message.guild.get_role(role_id)
                if role and role not in message.author.roles:
                    try:
                        await message.author.add_roles(role)
                        await level_channel.send(f"🎖️ إنجاز رائع! حصلت على رتبة **{role.name}**!")
                    except discord.Forbidden:
                        print(f"⚠️ البوت يفتقر للترتيب/الصلاحيات لإعطاء رتبة {role.name}")
    else:
        await update_user_data(user_id, xp, lvl)

    await bot.process_commands(message)

# ==========================================
# 🛠️ 6. الأوامر (Commands)
# ==========================================
@bot.command()
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    user_id = str(member.id)

    async with ctx.typing():
        user_data = await get_user_data(user_id)
        lvl = user_data["level"]
        xp = user_data["xp"]
        next_xp = get_next_level_xp(lvl)
        user_rank = await get_user_rank(user_id)

        for target_lvl, role_id in LEVEL_ROLES.items():
            if lvl >= target_lvl:
                role = ctx.guild.get_role(role_id)
                if role and role not in member.roles:
                    try:
                        await member.add_roles(role)
                    except discord.Forbidden:
                        pass

        rank_file = await generate_rank_card(member, lvl, xp, next_xp, rank_position=user_rank)
        await ctx.send(content=f"📊 تفضل {member.mention}، هذه بطاقة التقدم والمستوى الخاصة بك:", file=rank_file)

@bot.command(name="top", aliases=["leaderboard", "lb"])
async def leaderboard(ctx):
    cursor = collection.find().sort("xp", -1).limit(10)
    top_users = await cursor.to_list(length=10)

    if not top_users:
        await ctx.send("❌ لا توجد بيانات مسجلة للأعضاء حتى الآن!")
        return

    embed = discord.Embed(
        title="🏆 **لوحة متصدري السيرفر (Top 10)**",
        description="أعلى الأعضاء من حيث نقاط الـ XP والمستوى:",
        color=discord.Color.gold()
    )

    medals = ["🥇", "🥈", "🥉"]
    description_text = ""

    for index, doc in enumerate(top_users, start=1):
        user_id = doc["_id"]
        user = ctx.guild.get_member(int(user_id))
        username = user.mention if user else f"عضو مغادر (`{user_id}`)"
        
        rank_icon = medals[index - 1] if index <= 3 else f"`#{index}`"
        
        xp = doc.get("xp", 0)
        level = doc.get("level", 1)

        description_text += f"{rank_icon} **{username}** — **المستوى:** `{level}` | **XP:** `{xp:,}`\n"

    embed.description = description_text
    embed.set_footer(text=f"طلب بواسطة: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

    await ctx.send(embed=embed)

@bot.command()
async def color(ctx, choice: str = None):
    central_role = ctx.guild.get_role(CENTRAL_KEY_ROLE_ID)

    if not central_role or central_role not in ctx.author.roles:
        await ctx.send(f"❌ {ctx.author.mention} هذا الأمر مخصص فقط لأصحاب **Central Key (مستوى 35+)**!")
        return

    if not choice or choice.lower() not in ["red", "purple", "blue", "remove"]:
        await ctx.send(
            f"🎨 {ctx.author.mention} بصفتك صاحب **Central Key**، يمكنك اختيار لون أحد المفاتيح السابقة:\n"
            f"• `!color red` 🔴 (Red Key - المستوى 5)\n"
            f"• `!color purple` 🟣 (Dark Key - المستوى 10)\.py\n"
            f"• `!color blue` 🔵 (Eleventh Key - المستوى 20)\n"
            f"• `!color remove` ❌ (إزالة اللون واستعادة اللون الأساسي)"
        )
        return

    choice = choice.lower()

    color_roles_to_remove = [
        ctx.guild.get_role(r_id) for r_id in COLOR_ROLES.values()
        if ctx.guild.get_role(r_id) and ctx.guild.get_role(r_id) in ctx.author.roles
    ]

    if choice == "remove":
        if color_roles_to_remove:
            await ctx.author.remove_roles(*color_roles_to_remove)
            await ctx.send(f"✅ تم إزالة اللون المخصص واكتساب اللون الأساسي لمستواك يا {ctx.author.mention}.")
        else:
            await ctx.send(f"⚠️ {ctx.author.mention} ليس لديك لون مخصص لإزالته.")
        return

    selected_role_id = COLOR_ROLES[choice]
    selected_role = ctx.guild.get_role(selected_role_id)

    if selected_role:
        if color_roles_to_remove:
            await ctx.author.remove_roles(*color_roles_to_remove)
        await ctx.author.add_roles(selected_role)
        await ctx.send(f"✅ تم تغيير لون اسمك بنجاح إلى لون **{selected_role.name}** يا {ctx.author.mention}! 🎉")
    else:
        await ctx.send("❌ حدث خطأ: لم يتم العثور على رتبة اللون في السيرفر، يرجى التأكد من الـ IDs.")

# ==========================================
# 🔌 7. تشغيل البوت
# ==========================================
token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("❌ Error: DISCORD_TOKEN is missing in environment variables!")
