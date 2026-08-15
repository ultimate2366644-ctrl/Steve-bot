import discord
from discord.ext import commands
import json
import os
from PIL import Image, ImageDraw, ImageFont
import io
import urllib.request
from dotenv import load_dotenv

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
    5:  1535727707000672346,
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
# 💾 3. إدارة ملف حفظ البيانات (JSON)
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "users_xp.json")

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading JSON data: {e}")
            return {}
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ==========================================
# 🎨 4. دالة إنشاء بطاقة الـ Rank
# ==========================================
async def generate_rank_card(
    member: discord.Member,
    level: int,
    current_xp: int,
    next_level_xp: int
):
    card = Image.new("RGBA", (1200, 400), color=(15, 16, 18, 255))
    draw = ImageDraw.Draw(card)

    # 📁 مسار ملف roboto.ttf الموجود في المستودع
    font_path = os.path.join(BASE_DIR, "roboto.ttf")

    try:
        # 🔍 التكبير الأقصى للأحجام
        font_name = ImageFont.truetype(font_path, 65)   # اسم العضو
        font_stats = ImageFont.truetype(font_path, 55)  # أرقام #1 و 01
        font_sub = ImageFont.truetype(font_path, 38)    # كلمتي RANK و LEVEL
        font_xp = ImageFont.truetype(font_path, 36)     # نص الـ XP
    except Exception as e:
        print(f"⚠️ تعذر فتح ملف roboto.ttf: {e}")
        font_name = font_stats = font_sub = font_xp = ImageFont.load_default()

    # الصورة الشخصية
    avatar_url = member.display_avatar.with_format("png").url
    req = urllib.request.Request(avatar_url, headers={"User-Agent": "Mozilla/5.0"})
    avatar_bytes = urllib.request.urlopen(req).read()
    avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")

    avatar_size = (200, 200)
    avatar = avatar.resize(avatar_size)

    mask = Image.new("L", avatar_size, 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, avatar_size[0], avatar_size[1]), fill=255)

    card.paste(avatar, (50, 100), mask)

    # اسم العضو
    draw.text((285, 125), member.name, font=font_name, fill=(255, 255, 255, 255))

    NEW_COLOR = (188, 201, 247, 255)

    # 🏆 RANK
    draw.text((800, 90), "#1", font=font_stats, fill=(255, 255, 255, 255), anchor="mm")
    draw.text((800, 150), "RANK", font=font_sub, fill=NEW_COLOR, anchor="mm")

    # ⭐ LEVEL
    draw.text((1060, 90), f"{level:02d}", font=font_stats, fill=(255, 255, 255, 255), anchor="mm")
    draw.text((1060, 150), "LEVEL", font=font_sub, fill=NEW_COLOR, anchor="mm")

    # 📊 XP
    xp_text = f"{current_xp} XP / {next_level_xp} XP"
    draw.text((930, 225), xp_text, font=font_xp, fill=(200, 200, 200, 255), anchor="mm")

    # 📈 شريط التقدم
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

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if before.premium_since is None and after.premium_since is not None:
        users = load_data()
        user_id = str(after.id)

        if user_id not in users:
            users[user_id] = {"xp": 0, "level": 1}

        users[user_id]["xp"] += BOOST_XP_REWARD
        
        lvl = users[user_id]["level"]
        xp = users[user_id]["xp"]
        next_level_xp = 5 * (lvl ** 2) + (50 * lvl) + 100

        while xp >= next_level_xp:
            users[user_id]["level"] += 1
            lvl = users[user_id]["level"]
            next_level_xp = 5 * (lvl ** 2) + (50 * lvl) + 100

        save_data(users)

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

    users = load_data()
    user_id = str(message.author.id)

    if user_id not in users:
        users[user_id] = {"xp": 0, "level": 1}

    users[user_id]["xp"] += 15
    xp = users[user_id]["xp"]
    lvl = users[user_id]["level"]

    next_level_xp = 5 * (lvl ** 2) + (50 * lvl) + 100

    if xp >= next_level_xp:
        users[user_id]["level"] += 1
        new_lvl = users[user_id]["level"]
        
        level_channel = bot.get_channel(LEVEL_UP_CHANNEL_ID)
        target_channel = level_channel if level_channel else message.channel

        new_next_xp = 5 * (new_lvl ** 2) + (50 * new_lvl) + 100
        rank_file = await generate_rank_card(message.author, new_lvl, xp, new_next_xp)

        await target_channel.send(
            content=f"🎉 **مبروك {message.author.mention}!** ارتقيت إلى **المستوى {new_lvl}**!", 
            file=rank_file
        )

        if new_lvl in LEVEL_ROLES:
            role_id = LEVEL_ROLES[new_lvl]
            role = message.guild.get_role(role_id)
            if role:
                await message.author.add_roles(role)
                await target_channel.send(f"🎖️ إنجاز رائع! حصلت على رتبة **{role.name}** لإنهاء المستوى {new_lvl}!")

    save_data(users)
    await bot.process_commands(message)

# ==========================================
# 🛠️ 6. الأوامر (Commands)
# ==========================================
@bot.command()
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    users = load_data()
    user_id = str(member.id)

    if user_id in users:
        lvl = users[user_id]["level"]
        xp = users[user_id]["xp"]
        next_xp = 5 * (lvl ** 2) + (50 * lvl) + 100
        
        async with ctx.typing():
            rank_file = await generate_rank_card(member, lvl, xp, next_xp)
            await ctx.send(content=f"📊 تفضل {member.mention}، هذه بطاقة التقدم والمستوى الخاصة بك:", file=rank_file)
    else:
        await ctx.send(f"ليس لدى {member.name} أي نقاط XP حتى الآن، ابدأ بالدردشة أولاً!")

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
            f"• `!color purple` 🟣 (Dark Key - المستوى 10)\n"
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
