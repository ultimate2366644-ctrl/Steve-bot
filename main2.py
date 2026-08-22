import os
import io
import asyncio
import discord
from discord.ext import commands
from pymongo import MongoClient
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------
# 1. إعدادات البوت وقاعدة البيانات
# ---------------------------------------------------------
TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

LEVEL_UP_CHANNEL_ID = 123456789012345678  # استبدله بـ ID روم الترقية

# الاتصال بقاعدة البيانات MongoDB
try:
    cluster = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = cluster["DiscordBot"]
    collection = db["users_xp"]
    print("✅ تم الاتصال بقاعدة البيانات بنجاح!")
except Exception as e:
    print(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# رتب المستويات (مستوى: ID الرتبة)
LEVEL_ROLES = {
    5: 111111111111111111,
    10: 222222222222222222,
    20: 333333333333333333
}

# ---------------------------------------------------------
# 2. دوال التعامل مع البيانات والـ XP
# ---------------------------------------------------------
def load_data():
    """قراءة جميع بيانات المستخدمين من MongoDB"""
    users = {}
    try:
        for doc in collection.find():
            users[str(doc["_id"])] = {"xp": doc.get("xp", 0), "level": doc.get("level", 1)}
    except Exception as e:
        print(f"⚠️ خطأ أثناء جلب البيانات: {e}")
    return users

def save_user_data(user_id, xp, level):
    """حفظ أو تحديث بيانات مستخدم واحد في MongoDB"""
    try:
        collection.update_one(
            {"_id": str(user_id)},
            {"$set": {"xp": xp, "level": level}},
            upsert=True
        )
    except Exception as e:
        print(f"⚠️ خطأ أثناء حفظ البيانات: {e}")

def get_next_level_xp(level):
    """معادلة حساب الـ XP المطلوب للمستوى التالي"""
    return 50 * (level ** 2) + (100 * level)

def get_user_rank(user_id, users):
    """حساب ترتيب العضو بين باقي الأعضاء"""
    sorted_users = sorted(users.items(), key=lambda x: x[1]['xp'], reverse=True)
    for rank, (u_id, _) in enumerate(sorted_users, 1):
        if u_id == str(user_id):
            return rank
    return 1
# ---------------------------------------------------------
# 3. توليد صور البطاقات (Rank Card)
# ---------------------------------------------------------
async def generate_rank_card(user, level, xp, next_xp, rank_num):
    width, height = 800, 250
    image = Image.new("RGBA", (width, height), (15, 16, 18, 255))
    draw = ImageDraw.Draw(image)

    # خلفية البطاقة الداخلية
    draw.rounded_rectangle((20, 20, width - 20, height - 20), radius=20, fill=(24, 26, 32, 255))

    # جلب صورة الأفتار
    avatar_asset = user.display_avatar.with_format("png").with_size(128)
    avatar_bytes = await avatar_asset.read()
    avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    avatar_img = avatar_img.resize((140, 140))

    # قص الأفتار بشكل دائري
    mask = Image.new("L", (140, 140), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, 140, 140), fill=255)
    image.paste(avatar_img, (50, 55), mask)

    # إضافة النصوص
    try:
        font_title = ImageFont.truetype("arial.ttf", 32)
        font_sub = ImageFont.truetype("arial.ttf", 22)
    except:
        font_title = ImageFont.load_default()
        font_sub = font_title

    draw.text((210, 60), f"{user.display_name}", font=font_title, fill=(255, 255, 255))
    draw.text((210, 105), f"Rank: #{rank_num}  |  Level: {level}", font=font_sub, fill=(188, 201, 247))

    # شريط التقدم (Progress Bar)
    bar_x, bar_y, bar_w, bar_h = 210, 150, 530, 25
    draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), radius=12, fill=(40, 44, 52))

    current_lvl_xp = get_next_level_xp(level - 1) if level > 1 else 0
    xp_in_level = xp - current_lvl_xp
    needed_in_level = next_xp - current_lvl_xp
    progress = min(1.0, max(0.0, xp_in_level / needed_in_level))

    if progress > 0:
        fill_w = int(bar_w * progress)
        draw.rounded_rectangle((bar_x, bar_y, bar_x + fill_w, bar_y + bar_h), radius=12, fill=(188, 201, 247))

    draw.text((bar_x + bar_w - 120, bar_y - 28), f"{xp} / {next_xp} XP", font=font_sub, fill=(200, 200, 200))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(buffer, filename="rank.png")

# ---------------------------------------------------------
# 4. الأحداث (Events)
# ---------------------------------------------------------
@bot.event
async def on_ready():
    print(f"✅ تم تسجيل الدخول بواسطة: {bot.user.name}")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    # معالجة الأوامر أولاً والتوقف لتفادي التكرار
    if message.content.startswith("!"):
        await bot.process_commands(message)
        return

    loop = asyncio.get_event_loop()
    users = await loop.run_in_executor(None, load_data)
    user_id = str(message.author.id)

    if user_id not in users:
        users[user_id] = {"xp": 0, "level": 1}

    # منح 5 نقاط XP لكل رسالة
    users[user_id]["xp"] += 5
    xp = users[user_id]["xp"]
    lvl = users[user_id]["level"]

    next_level_xp = get_next_level_xp(lvl)

    # التحقق من ارتقاء المستوى
    if xp >= next_level_xp:
        while users[user_id]["xp"] >= get_next_level_xp(users[user_id]["level"]):
            users[user_id]["level"] += 1

        new_lvl = users[user_id]["level"]
        await loop.run_in_executor(None, save_user_data, user_id, xp, new_lvl)

        level_channel = bot.get_channel(LEVEL_UP_CHANNEL_ID)
        new_next_xp = get_next_level_xp(new_lvl)
        
        if level_channel:
            user_rank = get_user_rank(user_id, users)
            rank_file = await generate_rank_card(message.author, new_lvl, xp, new_next_xp, rank_num=user_rank)
            await level_channel.send(
                content=f"🎉 **مبروك {message.author.mention}!** ارتقيت إلى **المستوى {new_lvl}**!", 
                file=rank_file
            )

            if new_lvl in LEVEL_ROLES:
                role_id = LEVEL_ROLES[new_lvl]
                role = message.guild.get_role(role_id)
                if role and role not in message.author.roles:
                    try:
                        await message.author.add_roles(role)
                        await level_channel.send(f"🎖️ حصلت على رتبة جديدة: **{role.name}**!")
                    except discord.Forbidden:
                        print(f"⚠️ يفتقر البوت إلى صلاحيات إعطاء رتبة {role.name}")
    else:
        await loop.run_in_executor(None, save_user_data, user_id, xp, lvl)

# ---------------------------------------------------------
# 5. الأوامر (Commands)
# ---------------------------------------------------------

# أمر عرض البطاقة الشخصية
@bot.command(name="rank")
async def rank(ctx, member: discord.Member = None):
    member = member or ctx.author
    
    loop = asyncio.get_event_loop()
    users = await loop.run_in_executor(None, load_data)
    user_id = str(member.id)

    user_data = users.get(user_id, {"xp": 0, "level": 1})
    xp = user_data["xp"]
    lvl = user_data["level"]
    next_xp = get_next_level_xp(lvl)
    user_rank = get_user_rank(user_id, users)

    rank_file = await generate_rank_card(member, lvl, xp, next_xp, rank_num=user_rank)
    await ctx.send(file=rank_file)

# أمر عرض قائمة المتصدرين
@bot.command(name="leaderboard", aliases=["lb"])
async def leaderboard(ctx):
    loop = asyncio.get_event_loop()
    users = await loop.run_in_executor(None, load_data)

    if not users:
        await ctx.send("📋 لا توجد بيانات مسجلة في لوحة النتائج حتى الآن.")
        return

    sorted_users = sorted(users.items(), key=lambda x: x[1]['xp'], reverse=True)[:10]

    embed = discord.Embed(
        title="🏆 لوحة النتائج (أعلى 10 متصدرين)",
        color=discord.Color.gold()
    )

    for rank_num, (user_id, data) in enumerate(sorted_users, 1):
        member = ctx.guild.get_member(int(user_id))
        name = member.display_name if member else f"مستخدم مغادر ({user_id})"
        
        medal = "🥇" if rank_num == 1 else "🥈" if rank_num == 2 else "🥉" if rank_num == 3 else f"#{rank_num}"
        embed.add_field(
            name=f"{medal} {name}",
            value=f"**المستوى:** {data['level']} | **XP:** {data['xp']}",
            inline=False
        )

    await ctx.send(embed=embed)

bot.run(TOKEN)
