async def generate_rank_card(user, level, xp, next_xp, rank_num):
    width, height = 1200, 400
    image = Image.new("RGBA", (width, height), (15, 16, 18, 255))
    draw = ImageDraw.Draw(image)

    # 1. جلب صورة الأفتار وقصها بحجم مناسب للوحة 1200x400
    avatar_size = 210
    avatar_asset = user.display_avatar.with_format("png").with_size(256)
    avatar_bytes = await avatar_asset.read()
    avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    avatar_img = avatar_img.resize((avatar_size, avatar_size))

    mask = Image.new("L", (avatar_size, avatar_size), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, avatar_size, avatar_size), fill=255)
    image.paste(avatar_img, (60, 95), mask)

    # 2. تحميل الخط وأحجامه الجديدة لتناسب العرض
    base_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(base_dir, "Roboto-Bold.ttf")
    if not os.path.exists(font_path):
        font_path = os.path.join(base_dir, "Roboto.ttf")

    try:
        font_name = ImageFont.truetype(font_path, 60)
        font_big_num = ImageFont.truetype(font_path, 55)
        font_sub_label = ImageFont.truetype(font_path, 26)
        font_xp = ImageFont.truetype(font_path, 32)
    except Exception as e:
        print(f"⚠️ فشل قراءة الخط: {e}")
        font_name = font_big_num = font_sub_label = font_xp = ImageFont.load_default()

    # 3. اسم المستخدم بجانب الأفتار
    draw.text((300, 160), f"{user.display_name}", font=font_name, fill=(255, 255, 255))

    # 4. قسم الـ RANK (أعلى اليمين)
    draw.text((850, 50), f"#{rank_num}", font=font_big_num, fill=(255, 255, 255))
    draw.text((835, 120), "RANK", font=font_sub_label, fill=(140, 155, 205))

    # 5. قسم الـ LEVEL (أعلى اليمين)
    lvl_str = f"{level:02d}"
    draw.text((1050, 50), lvl_str, font=font_big_num, fill=(255, 255, 255))
    draw.text((1040, 120), "LEVEL", font=font_sub_label, fill=(140, 155, 205))

    # 6. نص الـ XP
    xp_text = f"{xp} XP / {next_xp} XP"
    draw.text((835, 200), xp_text, font=font_xp, fill=(240, 240, 245))

    # 7. شريط التقدم السفلي (Progress Bar)
    bar_x, bar_y, bar_w, bar_h = 300, 290, 840, 38
    draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), radius=19, fill=(40, 43, 50))

    current_lvl_xp = get_next_level_xp(level - 1) if level > 1 else 0
    xp_in_level = xp - current_lvl_xp
    needed_in_level = next_xp - current_lvl_xp
    progress = min(1.0, max(0.0, xp_in_level / needed_in_level)) if needed_in_level > 0 else 0

    if progress > 0:
        fill_w = int(bar_w * progress)
        draw.rounded_rectangle((bar_x, bar_y, bar_x + fill_w, bar_y + bar_h), radius=19, fill=(185, 200, 245))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(buffer, filename="rank.png")
