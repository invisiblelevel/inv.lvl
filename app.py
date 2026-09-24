import os
import json
import asyncio
import subprocess
import html
import math
from datetime import datetime
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError, RPCError

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("⚠️ Pillow не установлен — оптимизация картинок отключена")

api_id = int(os.environ.get('API_ID', 0))
api_hash = os.environ.get('API_HASH', '')
session_string = os.environ.get('SESSION_STRING', '')
channel_link = os.environ.get('CHANNEL_LINK', '')

SITE_URL = 'https://invisiblelevel.github.io/inv.lvl/'

CATEGORY_HASHTAGS = [
    'terrain', 'metal', 'wood', 'brick', 'concrete', 'stone',
    'tile', 'fabric', 'organic', 'plastic', 'leather', 'masonry', 'other'
]

CATEGORY_ORDER = [
    'terrain', 'metal', 'wood', 'brick', 'concrete', 'stone',
    'masonry', 'tile', 'fabric', 'organic', 'plastic', 'leather', 'other'
]

CATEGORY_NAMES_RU = {
    'terrain': 'Ландшафт', 'metal': 'Металл', 'wood': 'Дерево',
    'brick': 'Кирпич', 'concrete': 'Бетон', 'stone': 'Камень',
    'masonry': 'Кладка', 'tile': 'Плитка', 'fabric': 'Ткань',
    'organic': 'Органика', 'plastic': 'Пластик', 'other': 'Другое',
    'leather': 'Кожа'
}

CATEGORY_NAMES_EN = {
    'terrain': 'Terrain', 'metal': 'Metal', 'wood': 'Wood',
    'brick': 'Brick', 'concrete': 'Concrete', 'stone': 'Stone',
    'masonry': 'Masonry', 'tile': 'Tile', 'fabric': 'Fabric',
    'organic': 'Organic', 'plastic': 'Plastic', 'other': 'Other',
    'leather': 'Leather'
}

POSTS_PER_PAGE = 32
DOWNLOAD_DELAY = 3.0
MAX_RETRIES = 3
MAX_POSTS_PER_RUN = 100
IMAGE_MAX_WIDTH = 800
IMAGE_QUALITY = 82

DATA_FOLDER = 'public'
IMAGES_FOLDER = os.path.join(DATA_FOLDER, 'images')
os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(IMAGES_FOLDER, exist_ok=True)
POSTS_JSON = 'posts.json'

if not session_string:
    raise ValueError("❌ SESSION_STRING не задан.")

client = TelegramClient(StringSession(session_string), api_id, api_hash)


# ===================== ЗАГРУЗКА / СОХРАНЕНИЕ =====================

def load_all_posts():
    if os.path.exists(POSTS_JSON):
        try:
            with open(POSTS_JSON, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, list):
                    return []
                return data
        except Exception as e:
            print(f"⚠️ Ошибка чтения posts.json: {e}")
            return []
    return []


def save_all_posts(posts):
    tmp = POSTS_JSON + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)
    os.replace(tmp, POSTS_JSON)


# ===================== УТИЛИТЫ =====================

def escape_html(text):
    return html.escape(str(text)) if text else ''


def fix_typos(text):
    if not text:
        return text
    fixes = {
        'tileble': 'tileable',
        'TILEBLE': 'TILEABLE',
        'resolutin': 'resolution',
        'Resolutin': 'Resolution',
    }
    for bad, good in fixes.items():
        text = text.replace(bad, good)
    return text


def is_valid_tag(tag):
    if not tag or not tag.startswith('#'):
        return False
    body = tag[1:].strip()
    if not body:
        return False
    if body.isdigit():
        return False
    if len(body) < 2:
        return False
    return True


def format_text_for_html(text):
    if not text:
        return ''
    escaped = html.escape(text)
    lines = escaped.split('\n')
    result_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            result_lines.append('<br>')
        else:
            result_lines.append(stripped + '<br>')
    return ''.join(result_lines)


def load_text_file(filename):
    if not os.path.exists(filename):
        defaults = {
            'Readme_RU.txt': "Бесплатный архив PBR-текстур высокого разрешения.\n\nВсе материалы доступны для свободного использования в личных и коммерческих проектах.",
            'Readme_EN.txt': "Free high-resolution PBR texture archive.\n\nAll assets are free for personal and commercial projects.",
            'Donate.txt': "Поддержать проект:\n\nUSDT (TRC20): Ваш кошелек\nBoosty / DonationAlerts: ссылка",
            'Donate_EN.txt': "Support the project:\n\nUSDT (TRC20): Your wallet\nBoosty / DonationAlerts: link",
        }
        if filename in defaults:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(defaults[filename])

    variants = [filename, filename.lower(), filename.upper(),
                filename.replace(' ', ''), filename.replace(' ', '_'),
                filename.replace(' ', '-')]
    for name in variants:
        if os.path.exists(name):
            for encoding in ['utf-8', 'utf-8-sig', 'cp1251', 'latin-1']:
                try:
                    with open(name, 'r', encoding=encoding) as f:
                        return f.read()
                except Exception:
                    continue
    print(f"⚠️ Файл {filename} не найден.")
    return "Информация загружается..."


def optimize_image(path):
    if not PIL_AVAILABLE:
        return
    try:
        # Если файл уже WebP — ничего не делаем
        if path.lower().endswith('.webp'):
            return
        with Image.open(path) as img:
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            if img.width > IMAGE_MAX_WIDTH:
                ratio = IMAGE_MAX_WIDTH / img.width
                new_h = int(img.height * ratio)
                img = img.resize((IMAGE_MAX_WIDTH, new_h), Image.LANCZOS)
            # Сохраняем как WebP (перезаписываем поверх)
            webp_path = os.path.splitext(path)[0] + '.webp'
            img.save(webp_path, 'WEBP', quality=IMAGE_QUALITY, method=6)
            # Удаляем исходный jpg/png, если имя изменилось
            if webp_path != path and os.path.exists(path):
                os.remove(path)
    except Exception as e:
        print(f"⚠️ Не удалось оптимизировать {path}: {e}")


# ===================== ПАРСИНГ TELEGRAM =====================

async def download_photo_safe(message, filename):
    # Если filename имеет .jpg/.png — работаем с ним, но после optimize_image
    # получится .webp. Проверяем оба варианта.
    path = os.path.join(IMAGES_FOLDER, filename)
    base_name = os.path.splitext(filename)[0]
    webp_path = os.path.join(IMAGES_FOLDER, base_name + '.webp')

    # Если webp уже есть — используем его
    if os.path.exists(webp_path):
        return True
    # Если оригинал уже есть — оптимизируем его и получим webp
    if os.path.exists(path):
        optimize_image(path)
        return True

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await client.download_media(message.media, file=path)
            await asyncio.sleep(DOWNLOAD_DELAY)
            optimize_image(path)
            return True
        except FloodWaitError as e:
            wait = e.seconds + 5
            print(f"⏳ FloodWait {wait}s (попытка {attempt}/{MAX_RETRIES})")
            await asyncio.sleep(wait)
        except RPCError as e:
            print(f"⚠️ RPC ошибка ({filename}): {e}")
            await asyncio.sleep(2 ** attempt)
        except Exception as e:
            print(f"⚠️ Ошибка скачивания {filename}: {e}")
            await asyncio.sleep(2 ** attempt)

    print(f"❌ Не удалось скачать {filename} после {MAX_RETRIES} попыток")
    return False


async def parse_channel(existing_posts):
    entity = await client.get_entity(channel_link)
    username = entity.username
    existing_ids = {p['id'] for p in existing_posts}
    last_known = max(existing_ids, default=0)

    min_id = max(0, last_known - 50)
    print(f"📌 Последний известный ID: {last_known}, начинаем с min_id={min_id}")

    new_messages = []
    async for msg in client.iter_messages(entity, min_id=min_id, reverse=True):
        new_messages.append(msg)
        if len(new_messages) >= MAX_POSTS_PER_RUN * 2:
            print(f"⚠️ Достигнут лимит {MAX_POSTS_PER_RUN} постов за запуск")
            break

    if not new_messages:
        print("ℹ️ Новых сообщений нет")
        return []

    new_posts = []
    current_post = None

    for msg in new_messages:
        if msg.photo:
            photo_filename = f"{msg.id}_preview.webp"
            ok = await download_photo_safe(msg, photo_filename)
            if not ok:
                print(f"🛑 Останавливаюсь: не скачалось фото {msg.id}")
                break

            current_post = {
                'id': msg.id,
                'photo_id': msg.id,
                'photo': photo_filename,
                'text': "",
                'archive_link': None,
                'archive_id': None,
                'hashtags': [],
            }
            new_posts.append(current_post)

        elif msg.document and current_post is not None:
            current_post['archive_id'] = msg.id
            current_post['archive_link'] = f"https://t.me/{username}/{msg.id}"

            if msg.text:
                raw_text = msg.text
                hashtags = [
                    word.strip() for word in raw_text.split()
                    if word.startswith('#') and is_valid_tag(word.strip())
                ]
                current_post['hashtags'] = hashtags
                lines = [
                    line.strip() for line in raw_text.split('\n')
                    if line.strip() and not line.strip().startswith('#')
                ]
                text_joined = '\n'.join(lines)
                current_post['text'] = fix_typos(text_joined)

            current_post['id'] = max(current_post['id'], msg.id)

    valid_posts = [
        p for p in new_posts
        if p.get('photo') and p.get('archive_link')
    ]

    valid_posts = [p for p in valid_posts if p['id'] not in existing_ids]

    seen = set()
    unique_posts = []
    for p in valid_posts:
        if p['id'] not in seen:
            seen.add(p['id'])
            unique_posts.append(p)

    print(f"✅ Новых постов: {len(unique_posts)}")
    return unique_posts


# ===================== ГЕНЕРАЦИЯ ТЕКСТА =====================

TAG_HUMAN_RU = {
    'terrain': 'ландшафтная', 'metal': 'металлическая', 'wood': 'деревянная',
    'brick': 'кирпичная', 'concrete': 'бетонная', 'stone': 'каменная',
    'masonry': 'каменная кладка', 'tile': 'плиточная', 'fabric': 'тканевая',
    'organic': 'органическая', 'plastic': 'пластиковая', 'leather': 'кожаная',
    'rust': 'ржавая', 'copper': 'медная', 'brass': 'латунная',
    'aluminum': 'алюминиевая', 'grille': 'решётчатая', 'patina': 'патинированная',
    'moss': 'мшистая', 'leaves': 'лиственная', 'grass': 'травяная',
    'sand': 'песчаная', 'gravel': 'гравийная', 'wall': 'стеновая',
    'denim': 'джинсовая', 'wool': 'шерстяная', 'velvet': 'бархатная',
    'velveteen': 'вельветовая', 'rubber': 'резиновая', 'stucco': 'штукатурная',
    'plaster': 'штукатурная', 'cardboard': 'картонная', 'mineral': 'минеральная',
    'ground': 'земляная', '8ktextures': 'разрешение 8K',
    '8ktexture': 'разрешение 8K', 'unrealengine': 'Unreal Engine',
    'unity': 'Unity', 'godot': 'Godot', 'gamedev': 'разработка игр',
    'texture': 'текстура', 'pbr': 'PBR',
}

TAG_HUMAN_EN = {
    'terrain': 'terrain', 'metal': 'metal', 'wood': 'wood',
    'brick': 'brick', 'concrete': 'concrete', 'stone': 'stone',
    'masonry': 'masonry', 'tile': 'tile', 'fabric': 'fabric',
    'organic': 'organic', 'plastic': 'plastic', 'leather': 'leather',
    'rust': 'rusty', 'copper': 'copper', 'brass': 'brass',
    'aluminum': 'aluminum', 'grille': 'grille', 'patina': 'patina',
    'moss': 'mossy', 'leaves': 'leaves', 'grass': 'grass',
    'sand': 'sand', 'gravel': 'gravel', 'wall': 'wall',
    'denim': 'denim', 'wool': 'wool', 'velvet': 'velvet',
    'velveteen': 'velveteen', 'rubber': 'rubber', 'stucco': 'stucco',
    'plaster': 'plaster', 'cardboard': 'cardboard', 'mineral': 'mineral',
    'ground': 'ground', '8ktextures': '8K resolution',
    '8ktexture': '8K resolution', 'unrealengine': 'Unreal Engine',
    'unity': 'Unity', 'godot': 'Godot', 'gamedev': 'game development',
    'texture': 'texture', 'pbr': 'PBR',
}

CATEGORY_CONTEXT_RU = {
    'terrain': 'для создания реалистичных природных поверхностей в 3D-сценах',
    'metal': 'для металлических конструкций, оружия и техники',
    'wood': 'для деревянных поверхностей, мебели и архитектурных элементов',
    'brick': 'для кирпичных стен и фасадов зданий',
    'concrete': 'для бетонных стен, полов и промышленных объектов',
    'stone': 'для каменных поверхностей и декоративной отделки',
    'masonry': 'для каменной кладки и архитектурных конструкций',
    'tile': 'для напольной и настенной плитки',
    'fabric': 'для одежды, мягкой мебели и текстиля',
    'organic': 'для растительных и природных поверхностей',
    'plastic': 'для пластиковых изделий и поверхностей',
    'leather': 'для кожи, обуви и аксессуаров',
    'other': 'для разнообразных игровых и 3D-задач',
}

CATEGORY_CONTEXT_EN = {
    'terrain': 'for realistic natural surfaces in 3D scenes',
    'metal': 'for metal structures, weapons and machinery',
    'wood': 'for wooden surfaces, furniture and architecture',
    'brick': 'for brick walls and building facades',
    'concrete': 'for concrete walls, floors and industrial objects',
    'stone': 'for stone surfaces and decorative finishing',
    'masonry': 'for masonry and architectural structures',
    'tile': 'for floor and wall tiles',
    'fabric': 'for clothing, upholstery and textiles',
    'organic': 'for vegetation and natural surfaces',
    'plastic': 'for plastic products and surfaces',
    'leather': 'for leather, shoes and accessories',
    'other': 'for various game and 3D tasks',
}


def _get_category(post):
    """Возвращает категорию поста (или 'other')."""
    for tag in post.get('hashtags', []):
        if tag.startswith('#'):
            clean = tag[1:].lower()
            if clean in CATEGORY_HASHTAGS:
                return clean
    return 'other'


def _get_clean_tags(post):
    """Возвращает список чистых тегов без #, отфильтрованных от мусора."""
    tags = []
    for t in post.get('hashtags', []):
        if not is_valid_tag(t):
            continue
        body = t[1:].strip().lower()
        if body not in tags:
            tags.append(body)
    return tags


def _get_title(post, lang='ru'):
    """Возвращает первую строку текста как заголовок."""
    lines = post['text'].split('\n') if post.get('text') else []
    if lines:
        return lines[0]
    return "Texture" if lang == 'en' else "Текстура"


def generate_texture_description(post, lang='ru'):
    """Генерирует уникальное описание текстуры на основе названия, категории и тегов."""
    title = _get_title(post, lang)
    category = _get_category(post)
    tags = _get_clean_tags(post)
    extra_tags = [t for t in tags if t not in CATEGORY_HASHTAGS]

    if lang == 'ru':
        context = CATEGORY_CONTEXT_RU.get(category, 'для разнообразных 3D-задач')
        parts = []
        parts.append(
            f"<p><strong>{escape_html(title)}</strong> — это бесшовная PBR-текстура "
            f"высокого разрешения <strong>8K</strong>, которая отлично подойдёт {context}.</p>"
        )

        features = []
        for t in extra_tags:
            human = TAG_HUMAN_RU.get(t)
            if human and human.lower() not in title.lower():
                features.append(human)

        if features:
            features_str = ', '.join(features[:6])
            parts.append(
                f"<p>Особенности: {escape_html(features_str)}. "
                f"Текстура полностью бесшовная (tileable), что позволяет "
                f"использовать её для больших поверхностей без видимых стыков.</p>"
            )

        parts.append(
            "<p>Формат: PBR (Albedo, Normal, Roughness, Metallic, AO, Height). "
            "Разрешение: 8K. Совместимость: Unreal Engine, Unity, Godot, Blender, "
            "3ds Max, Maya, Substance Painter и другие 3D-редакторы.</p>"
        )

        parts.append(
            "<p>Скачать полный архив с текстурами можно по кнопке ниже — "
            "это бесплатно и доступно для личных и коммерческих проектов.</p>"
        )

        return '\n'.join(parts)

    else:
        context = CATEGORY_CONTEXT_EN.get(category, 'for various 3D tasks')
        parts = []
        parts.append(
            f"<p><strong>{escape_html(title)}</strong> is a seamless high-resolution "
            f"PBR texture in <strong>8K</strong>, perfect {context}.</p>"
        )

        features = []
        for t in extra_tags:
            human = TAG_HUMAN_EN.get(t)
            if human and human.lower() not in title.lower():
                features.append(human)

        if features:
            features_str = ', '.join(features[:6])
            parts.append(
                f"<p>Features: {escape_html(features_str)}. "
                f"The texture is fully tileable, allowing you to cover large surfaces "
                f"without visible seams.</p>"
            )

        parts.append(
            "<p>Format: PBR (Albedo, Normal, Roughness, Metallic, AO, Height). "
            "Resolution: 8K. Compatible with Unreal Engine, Unity, Godot, Blender, "
            "3ds Max, Maya, Substance Painter and other 3D software.</p>"
        )

        parts.append(
            "<p>Download the full archive with textures using the button below — "
            "it's free for personal and commercial projects.</p>"
        )

        return '\n'.join(parts)


def generate_texture_seo(post, lang='ru'):
    """Генерирует SEO-данные для страницы текстуры."""
    title = _get_title(post, lang)
    category = _get_category(post)
    tags = _get_clean_tags(post)

    if lang == 'ru':
        cat_name = CATEGORY_NAMES_RU.get(category, 'Текстура')
        seo_title = f"{title} — {cat_name} PBR текстура 8K | InvisibleLevel"
        keywords = [title, cat_name, "PBR", "8K", "бесшовная текстура", "tileable", "скачать"]
        keywords.extend([t for t in tags if t not in CATEGORY_HASHTAGS])
        seo_desc = (
            f"{title} — бесплатная бесшовная {cat_name.lower()} PBR текстура 8K. "
            f"Скачать архив с Albedo, Normal, Roughness, Metallic, AO, Height."
        )
    else:
        cat_name = CATEGORY_NAMES_EN.get(category, 'Texture')
        seo_title = f"{title} — {cat_name} PBR Texture 8K | InvisibleLevel"
        keywords = [title, cat_name, "PBR", "8K", "tileable", "seamless texture", "download"]
        keywords.extend([t for t in tags if t not in CATEGORY_HASHTAGS])
        seo_desc = (
            f"{title} — free seamless {cat_name.lower()} PBR texture 8K. "
            f"Download archive with Albedo, Normal, Roughness, Metallic, AO, Height."
        )

    return seo_title, seo_desc, ', '.join(keywords)


# ===================== ГЕНЕРАЦИЯ HTML =====================

def build_common_css():
    """Общий CSS для всех страниц."""
    return '''
            body { font-family: sans-serif; background: #1a1a1a; color: #fff; margin: 0; padding: 20px; }
            .header-banner { max-width: 1550px; margin: 0 auto 20px auto; text-align: center; }
            .header-banner img { width: 100%; max-height: 240px; object-fit: cover; border-radius: 10px; display: block; margin: 0 auto; }
            .site-wrapper { display: flex; max-width: 1550px; margin: 0 auto; gap: 20px; align-items: flex-start; justify-content: center; }
            .sidebar { width: 220px; flex-shrink: 0; display: flex; flex-direction: column; gap: 15px; position: sticky; top: 20px; }
            .side-block { background: #2a2a2a; border-radius: 8px; padding: 20px; cursor: pointer; transition: transform 0.2s, background 0.2s; text-align: center; }
            .side-block:hover { background: #333; transform: translateY(-2px); }
            .side-block h3 { margin-top: 0; color: #fff; font-size: 1.1em; display: flex; align-items: center; justify-content: center; gap: 8px; }
            .side-block h3 svg { width: 20px; height: 20px; fill: #8ab4f8; }
            .side-block p { color: #aaa; font-size: 0.85em; margin-bottom: 15px; }
            .side-block .btn-link { display: inline-block; background: #4a6fa5; color: #fff; padding: 6px 15px; border-radius: 4px; font-size: 0.85em; }
            .main-content { flex: 1; min-width: 0; max-width: 1100px; }
            .gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 20px; }
            .card { background: #2a2a2a; border-radius: 8px; overflow: hidden; transition: transform 0.2s; }
            .card:hover { transform: scale(1.02); }
            .card a img { width: 100%; height: 200px; object-fit: cover; display: block; cursor: pointer; transition: opacity 0.2s; }
            .card a img:hover { opacity: 0.85; }
            .card .info { padding: 15px; }
            .card .info .title { font-weight: bold; margin-bottom: 5px; color: #fff; font-size: 1.1em; }
            .card .info .desc { color: #aaa; font-size: 0.9em; white-space: pre-wrap; }
            .card .info .tags { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 4px; }
            .card .info .tag { background: #3a3a3a; color: #8ab4f8; font-size: 0.75em; padding: 2px 6px; border-radius: 4px; }
            .card .info .link { display: inline-block; margin-top: 10px; background: #4a6fa5; color: #fff; padding: 5px 15px; border-radius: 4px; text-decoration: none; font-size: 0.9em; }
            .card .info .link:hover { background: #5a7fb5; }
            .nav { text-align: center; margin-bottom: 20px; }
            .nav a { color: #4a6fa5; text-decoration: none; margin: 0 10px; display: inline-block; }
            .nav a:hover { text-decoration: underline; }
            .lang-btn { background: #333; padding: 4px 10px; border-radius: 4px; border: 1px solid #4a6fa5; font-weight: bold; }
            .pagination { text-align: center; margin-top: 30px; }
            .pagination a, .pagination span { display: inline-block; padding: 8px 14px; margin: 0 4px; background: #2a2a2a; border-radius: 4px; color: #fff; text-decoration: none; }
            .pagination a:hover { background: #4a6fa5; }
            .pagination span.active { background: #4a6fa5; }
            .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); align-items: center; justify-content: center; }
            .modal-content { background: #222; padding: 30px; border-radius: 10px; max-width: 600px; width: 90%; max-height: 80vh; overflow-y: auto; color: #fff; position: relative; box-shadow: 0 4px 20px rgba(0,0,0,0.5); line-height: 1.7; font-size: 1rem; }
            .modal-content h2 { margin-top: 0; margin-bottom: 20px; color: #8ab4f8; }
            .modal-content .text-body { color: #ddd; }
            .close { position: absolute; right: 15px; top: 10px; font-size: 28px; cursor: pointer; color: #aaa; }
            .close:hover { color: #fff; }
            .texture-page { max-width: 900px; margin: 0 auto; }
            .texture-page .big-image { width: 100%; border-radius: 10px; background: #111; padding: 10px; box-sizing: border-box; }
            .texture-page .big-image img { width: 100%; height: auto; border-radius: 8px; display: block; }
            .texture-page h1 { font-size: 1.8em; margin: 20px 0 10px 0; color: #fff; }
            .texture-page .breadcrumb { color: #888; font-size: 0.9em; margin-bottom: 10px; }
            .texture-page .breadcrumb a { color: #8ab4f8; text-decoration: none; }
            .texture-page .breadcrumb a:hover { text-decoration: underline; }
            .texture-page .description { line-height: 1.8; color: #ddd; font-size: 1.05em; }
            .texture-page .description p { margin: 12px 0; }
            .texture-page .tag-cloud { margin: 20px 0; display: flex; flex-wrap: wrap; gap: 6px; }
            .texture-page .tag-cloud span { background: #3a3a3a; color: #8ab4f8; padding: 5px 12px; border-radius: 6px; font-size: 0.85em; }
            .texture-page .buttons { margin-top: 25px; display: flex; gap: 10px; flex-wrap: wrap; }
            .texture-page .btn-download { display: inline-block; background: #4a6fa5; color: #fff; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-size: 1.1em; font-weight: bold; transition: background 0.2s; }
            .texture-page .btn-download:hover { background: #5a7fb5; }
            .texture-page .btn-back { display: inline-block; background: #333; color: #fff; padding: 14px 28px; border-radius: 8px; text-decoration: none; font-size: 1.1em; transition: background 0.2s; }
            .texture-page .btn-back:hover { background: #444; }
            @media (max-width: 1100px) {
                .site-wrapper { flex-direction: column; align-items: stretch; }
                .sidebar { width: 100%; position: static; flex-direction: row; }
                .side-block { flex: 1; }
            }
    '''


def build_common_nav(category_posts, lang='ru', extra_lang_link=''):
    """Строит навигацию (меню категорий)."""
    suffix = '_en' if lang == 'en' else ''
    home_link = f'index{suffix}.html'
    home_text = 'Home' if lang == 'en' else 'Главная'
    lang_btn_text = 'RU' if lang == 'en' else 'EN'

    nav = f'<a href="{home_link}">{home_text}</a>'
    for cat in CATEGORY_ORDER:
        if cat in category_posts:
            cat_filename = f'{cat}{suffix}.html'
            cat_display = (
                CATEGORY_NAMES_RU.get(cat, cat.capitalize()) if lang == 'ru'
                else CATEGORY_NAMES_EN.get(cat, cat.capitalize())
            )
            nav += f'<a href="{cat_filename}">{cat_display}</a>'

    if extra_lang_link:
        nav += f'<a href="{extra_lang_link}" class="lang-btn">{lang_btn_text}</a>'

    return nav


def build_common_modals(lang='ru'):
    """Строит модалки Info и Donate."""
    modal_info_h = 'About Project' if lang == 'en' else 'Информация о проекте'
    readme_filename = 'Readme_EN.txt' if lang == 'en' else 'Readme_RU.txt'
    modal_info_p = format_text_for_html(load_text_file(readme_filename))

    modal_donate_h = 'Support Project' if lang == 'en' else 'Поддержать проект'
    donate_filename = 'Donate_EN.txt' if lang == 'en' else 'Donate.txt'
    modal_donate_p = format_text_for_html(load_text_file(donate_filename))

    return f'''
        <div id="infoModal" class="modal" onclick="closeModal(event, 'infoModal')">
            <div class="modal-content">
                <span class="close" onclick="closeModalDirect('infoModal')">&times;</span>
                <h2>{modal_info_h}</h2>
                <div class="text-body">{modal_info_p}</div>
            </div>
        </div>
        <div id="donateModal" class="modal" onclick="closeModal(event, 'donateModal')">
            <div class="modal-content">
                <span class="close" onclick="closeModalDirect('donateModal')">&times;</span>
                <h2>{modal_donate_h}</h2>
                <div class="text-body">{modal_donate_p}</div>
            </div>
        </div>
    '''


def build_common_scripts():
    """Скрипты модалок."""
    return '''
        <script>
            function openModal(id) { 
                var m = document.getElementById(id);
                if(m) m.style.display = 'flex'; 
            }
            function closeModalDirect(id) { 
                var m = document.getElementById(id);
                if(m) m.style.display = 'none'; 
            }
            function closeModal(e, id) { 
                if(e.target.id === id) { 
                    document.getElementById(id).style.display = 'none'; 
                } 
            }
        </script>
    '''


def generate_texture_page(post, category_posts, lang='ru'):
    """Генерирует отдельную HTML-страницу для одной текстуры."""
    post_id = post['id']
    title = _get_title(post, lang)
    category = _get_category(post)

    suffix = '_en' if lang == 'en' else ''
    page_url = f"texture_{post_id}{suffix}.html"

    other_lang_link = (
        f"texture_{post_id}.html" if lang == 'en'
        else f"texture_{post_id}_en.html"
    )

    photo_file = post.get('photo', '')
    if photo_file:
        photo_file = os.path.splitext(photo_file)[0] + '.webp'
    photo_src = f'images/{photo_file}' if photo_file else ''
    full_photo_url = f"{SITE_URL}/images/{photo_file}" if photo_file else ''

    seo_title, seo_desc, keywords = generate_texture_seo(post, lang)
    description_html = generate_texture_description(post, lang)

    cat_display = (
        CATEGORY_NAMES_RU.get(category, category.capitalize()) if lang == 'ru'
        else CATEGORY_NAMES_EN.get(category, category.capitalize())
    )
    cat_link = f"{category}{suffix}.html"
    home_link = f"index{suffix}.html"
    home_text = 'Главная' if lang == 'ru' else 'Home'
    breadcrumb = (
        f'<div class="breadcrumb">'
        f'<a href="{home_link}">{home_text}</a> / '
        f'<a href="{cat_link}">{cat_display}</a> / '
        f'{escape_html(title)}'
        f'</div>'
    )

    btn_download_text = 'Download Archive' if lang == 'en' else 'Скачать архив'
    btn_back_text = 'Back to gallery' if lang == 'en' else 'Назад в галерею'

    download_btn = (
        f'<a class="btn-download" href="{post["archive_link"]}" '
        f'target="_blank" rel="noopener">{btn_download_text}</a>'
        if post.get('archive_link') else ''
    )

    valid_tags = [t for t in post.get('hashtags', []) if is_valid_tag(t)]
    tag_cloud = ''
    if valid_tags:
        tag_cloud = '<div class="tag-cloud">' + ' '.join(
            f'<span>{escape_html(t)}</span>' for t in valid_tags
        ) + '</div>'

    post_full_text = ''
    if post.get('text'):
        lines = post['text'].split('\n')
        if len(lines) > 1:
            extra = '\n'.join(lines[1:]).strip()
            if extra:
                post_full_text = f'<p><em>{format_text_for_html(extra)}</em></p>'

    seo_block = f'''
        <title>{escape_html(seo_title)}</title>
        <meta name="description" content="{escape_html(seo_desc)}">
        <meta name="keywords" content="{escape_html(keywords)}">
        <meta name="robots" content="index, follow">
        <meta name="author" content="InvisibleLevel">
        <link rel="canonical" href="{SITE_URL}/{page_url}">

        <meta property="og:type" content="article">
        <meta property="og:title" content="{escape_html(seo_title)}">
        <meta property="og:description" content="{escape_html(seo_desc)}">
        <meta property="og:url" content="{SITE_URL}/{page_url}">
        <meta property="og:image" content="{full_photo_url}">
        <meta property="og:site_name" content="InvisibleLevel Textures">
        <meta property="og:locale" content="{'ru_RU' if lang == 'ru' else 'en_US'}">

        <meta name="twitter:card" content="summary_large_image">
        <meta name="twitter:title" content="{escape_html(seo_title)}">
        <meta name="twitter:description" content="{escape_html(seo_desc)}">
        <meta name="twitter:image" content="{full_photo_url}">

        <script type="application/ld+json">
        {{
            "@context": "https://schema.org",
            "@type": "ImageObject",
            "name": "{escape_html(title)}",
            "description": "{escape_html(seo_desc)}",
            "contentUrl": "{full_photo_url}",
            "url": "{SITE_URL}/{page_url}",
            "inLanguage": "{'ru' if lang == 'ru' else 'en'}",
            "author": {{
                "@type": "Organization",
                "name": "InvisibleLevel"
            }}
        }}
        </script>
    '''

    nav = build_common_nav(category_posts, lang, extra_lang_link=other_lang_link)
    modals = build_common_modals(lang)
    scripts = build_common_scripts()
    css = build_common_css()

    html_page = f'''
    <!DOCTYPE html>
    <html lang="{'ru' if lang == 'ru' else 'en'}">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        {seo_block}
        <style>{css}</style>
    </head>
    <body>
        <div class="header-banner">
            <a href="{home_link}">
                <img src="header.webp" width="1550" height="234" loading="eager" fetchpriority="high" alt="InvisibleLevel Textures">
            </a>
        </div>
        <div class="nav">
            {nav}
        </div>
        <div class="texture-page">
            {breadcrumb}
            <h1>{escape_html(title)}</h1>
            <div class="big-image">
                <img src="{photo_src}" alt="{escape_html(title)} — PBR texture">
            </div>
            {tag_cloud}
            <div class="description">
                {description_html}
                {post_full_text}
            </div>
            <div class="buttons">
                {download_btn}
                <a class="btn-back" href="{cat_link}">{btn_back_text}</a>
            </div>
        </div>
        {modals}
        {scripts}
    </body>
    </html>
    '''
    return html_page


def render_card(post, lang='ru'):
    """Карточка в галерее. Ссылается на отдельную страницу текстуры."""
    lines = post['text'].split('\n') if post.get('text') else []
    title = escape_html(lines[0]) if lines else ("Texture" if lang == 'en' else "Текстура")
    desc = escape_html('\n'.join(lines[1:])) if len(lines) > 1 else ''

    if not desc:
        desc = ("8K PBR texture, tileable, free download"
                if lang == 'en' else
                "PBR текстура 8K, бесшовная, скачать бесплатно")

    clean_tags = [t for t in post.get('hashtags', []) if is_valid_tag(t)]
    tags_html = ''
    if clean_tags:
        tags_html = '<div class="tags">' + ' '.join(
            f'<span class="tag">{escape_html(t)}</span>' for t in clean_tags
        ) + '</div>'

    suffix = '_en' if lang == 'en' else ''
    texture_page_link = f'texture_{post["id"]}{suffix}.html'
    photo_file = post.get('photo', '')
    # На случай, если в posts.json остались старые .jpg — меняем на .webp
    if photo_file:
        photo_file = os.path.splitext(photo_file)[0] + '.webp'
    photo_src = f'images/{photo_file}' if photo_file else ''

    img_tag = (
        f'<img src="{photo_src}" alt="{title} — PBR texture" loading="lazy">'
        if photo_src else ''
    )
    card_img = (
        f'<a href="{texture_page_link}">{img_tag}</a>'
        if photo_src else ''
    )
    btn_text = 'Download Archive' if lang == 'en' else 'Скачать архив'

    archive_btn = (
        f'<a class="link" href="{post["archive_link"]}" target="_blank" rel="noopener">{btn_text}</a>'
        if post.get('archive_link') else ''
    )

    return f'''
    <div class="card" itemscope itemtype="https://schema.org/CreativeWork">
        {card_img}
        <div class="info">
            <div class="title" itemprop="name">{title}</div>
            <div class="desc" itemprop="description">{desc}</div>
            {tags_html}
            {archive_btn}
        </div>
    </div>
    '''


def render_nav(current_page, total_pages, base_name, lang='ru'):
    if total_pages <= 1:
        return ''
    suffix = '_en' if lang == 'en' else ''
    nav = '<div class="pagination">'
    for i in range(1, total_pages + 1):
        if i == current_page:
            nav += f'<span class="active">{i}</span>'
        else:
            if i == 1:
                nav += f'<a href="{base_name}{suffix}.html">{i}</a>'
            else:
                nav += f'<a href="{base_name}_page{i}{suffix}.html">{i}</a>'
    nav += '</div>'
    return nav


def build_seo_block(title, description, keywords, url, image_url, lang='ru'):
    safe_title = escape_html(title)
    safe_desc = escape_html(description)
    safe_keywords = escape_html(keywords)
    safe_url = escape_html(url)
    safe_image = escape_html(image_url) if image_url else f"{SITE_URL}/preview.jpg"
    locale = 'ru_RU' if lang == 'ru' else 'en_US'
    alt_locale = 'en_US' if lang == 'ru' else 'ru_RU'

    return f'''
        <title>{safe_title}</title>
        <meta name="description" content="{safe_desc}">
        <meta name="keywords" content="{safe_keywords}">
        <meta name="robots" content="index, follow">
        <meta name="author" content="InvisibleLevel">
        <link rel="canonical" href="{safe_url}">

        <meta property="og:type" content="website">
        <meta property="og:title" content="{safe_title}">
        <meta property="og:description" content="{safe_desc}">
        <meta property="og:url" content="{safe_url}">
        <meta property="og:image" content="{safe_image}">
        <meta property="og:site_name" content="InvisibleLevel Textures">
        <meta property="og:locale" content="{locale}">
        <meta property="og:locale:alternate" content="{alt_locale}">

        <meta name="twitter:card" content="summary_large_image">
        <meta name="twitter:title" content="{safe_title}">
        <meta name="twitter:description" content="{safe_desc}">
        <meta name="twitter:image" content="{safe_image}">

        <script type="application/ld+json">
        {{
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": "{safe_title}",
            "description": "{safe_desc}",
            "url": "{safe_url}",
            "inLanguage": "{'ru' if lang == 'ru' else 'en'}"
        }}
        </script>
    '''


def generate_page(posts, page_num, total_pages, base_name, title, category_posts, lang='ru'):
    start = (page_num - 1) * POSTS_PER_PAGE
    end = min(start + POSTS_PER_PAGE, len(posts))
    page_posts = posts[start:end]

    all_tags = set()
    for p in posts:
        for t in p.get('hashtags', []):
            if is_valid_tag(t):
                all_tags.add(t.lstrip('#').lower())
    keywords_str = ', '.join(sorted(all_tags)) if all_tags else "pbr textures, 3d assets, free textures"

    suffix = '_en' if lang == 'en' else ''
    page_suffix = '' if page_num == 1 else f'_page{page_num}'
    url = f"{SITE_URL}/{base_name}{page_suffix}{suffix}.html"

    first_photo = None
    for p in page_posts:
        if p.get('photo'):
            first_photo = f"{SITE_URL}/images/{p['photo']}"
            break

    if lang == 'ru':
        seo_title = f"{title} — Бесплатные PBR текстуры | InvisibleLevel"
        seo_desc = (f"{title}. Бесплатные PBR текстуры высокого разрешения для 3D художников "
                    f"и разработчиков игр. Скачивай бесплатно: {keywords_str}.")
    else:
        seo_title = f"{title} — Free PBR Textures | InvisibleLevel"
        seo_desc = (f"{title}. Free high-resolution PBR textures for 3D artists and game "
                    f"developers. Download for free: {keywords_str}.")

    seo_block = build_seo_block(seo_title, seo_desc, keywords_str, url, first_photo, lang)

    home_link = f'index{suffix}.html'
    other_lang_link = (
        f'{base_name}{page_suffix}.html' if lang == 'en'
        else f'{base_name}{page_suffix}_en.html'
    )

    info_title = 'Info' if lang == 'en' else 'Информация'
    info_desc = 'About the project and archive.' if lang == 'en' else 'О проекте и архиве.'
    info_btn = 'Open' if lang == 'en' else 'Открыть'

    donate_title = 'Support' if lang == 'en' else 'Поддержка'
    donate_desc = 'Support the project.' if lang == 'en' else 'Поддержать проект.'
    donate_btn = 'Details' if lang == 'en' else 'Реквизиты'

    home_text = 'Home' if lang == 'en' else 'Главная'

    css = build_common_css()
    nav = build_common_nav(category_posts, lang, extra_lang_link=other_lang_link)
    modals = build_common_modals(lang)
    scripts = build_common_scripts()

    html_page = f'''
    <!DOCTYPE html>
    <html lang="{'ru' if lang == 'ru' else 'en'}">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        {seo_block}
        <style>{css}</style>
    </head>
    <body>
        <div class="header-banner">
            <a href="{home_link}">
                <img src="header.webp" width="1550" height="234" loading="eager" fetchpriority="high" alt="InvisibleLevel Textures">
            </a>
        </div>
        <div class="nav">
            {nav}
        </div>
        <h1 style="text-align:center; margin-bottom: 30px;">{title}</h1>
        <div class="site-wrapper">
            <div class="sidebar">
                <div class="side-block" onclick="openModal('infoModal')">
                    <h3><svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg> {info_title}</h3>
                    <p>{info_desc}</p>
                    <span class="btn-link">{info_btn}</span>
                </div>
            </div>
            <div class="main-content">
                <div class="gallery">
    '''

    for post in page_posts:
        html_page += render_card(post, lang)

    html_page += '''
                </div>
    '''
    html_page += render_nav(page_num, total_pages, base_name, lang)
    html_page += f'''
            </div>
            <div class="sidebar">
                <div class="side-block" onclick="openModal('donateModal')">
                    <h3><svg viewBox="0 0 24 24"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg> {donate_title}</h3>
                    <p>{donate_desc}</p>
                    <span class="btn-link">{donate_btn}</span>
                </div>
            </div>
        </div>
        {modals}
        {scripts}
    </body>
    </html>
    '''
    return html_page


def generate_robots_txt():
    robots = f"""User-agent: *
Allow: /

Sitemap: {SITE_URL}/sitemap.xml
"""
    with open(os.path.join(DATA_FOLDER, 'robots.txt'), 'w', encoding='utf-8') as f:
        f.write(robots)
    print("✅ robots.txt создан")


def generate_sitemap(all_pages):
    today = datetime.now().strftime('%Y-%m-%d')
    urls = ""
    for page_url in sorted(all_pages):
        urls += f"""  <url>
    <loc>{SITE_URL}/{page_url}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
"""
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls}</urlset>
"""
    with open(os.path.join(DATA_FOLDER, 'sitemap.xml'), 'w', encoding='utf-8') as f:
        f.write(sitemap)
    print(f"✅ sitemap.xml создан ({len(all_pages)} страниц)")


def generate_site(all_posts):
    if not all_posts:
        print("ℹ️ Нет постов для генерации сайта")
        return

    sorted_posts = sorted(all_posts, key=lambda x: x.get('id', 0), reverse=True)

    category_posts = {}
    for post in sorted_posts:
        cat = _get_category(post)
        if cat:
            category_posts.setdefault(cat, []).append(post)

    all_pages = set()
    all_pages.add('index.html')
    all_pages.add('index_en.html')

    # ===== Главная RU =====
    total_pages = max(1, math.ceil(len(sorted_posts) / POSTS_PER_PAGE))
    for page_num in range(1, total_pages + 1):
        filename = 'index.html' if page_num == 1 else f'index_page{page_num}.html'
        html_content = generate_page(
            sorted_posts, page_num, total_pages, 'index',
            'Все текстуры', category_posts, lang='ru'
        )
        with open(os.path.join(DATA_FOLDER, filename), 'w', encoding='utf-8') as f:
            f.write(html_content)
        all_pages.add(filename)

    # ===== Категории RU =====
    for cat in CATEGORY_ORDER:
        if cat not in category_posts:
            continue
        cat_posts = category_posts[cat]
        total_pages_cat = max(1, math.ceil(len(cat_posts) / POSTS_PER_PAGE))
        cat_title_ru = CATEGORY_NAMES_RU.get(cat, cat.capitalize())
        for page_num in range(1, total_pages_cat + 1):
            filename = f'{cat}.html' if page_num == 1 else f'{cat}_page{page_num}.html'
            html_content = generate_page(
                cat_posts, page_num, total_pages_cat, cat,
                cat_title_ru, category_posts, lang='ru'
            )
            with open(os.path.join(DATA_FOLDER, filename), 'w', encoding='utf-8') as f:
                f.write(html_content)
            all_pages.add(filename)

    # ===== Главная EN =====
    for page_num in range(1, total_pages + 1):
        filename = 'index_en.html' if page_num == 1 else f'index_page{page_num}_en.html'
        html_content = generate_page(
            sorted_posts, page_num, total_pages, 'index',
            'All Textures', category_posts, lang='en'
        )
        with open(os.path.join(DATA_FOLDER, filename), 'w', encoding='utf-8') as f:
            f.write(html_content)
        all_pages.add(filename)

    # ===== Категории EN =====
    for cat in CATEGORY_ORDER:
        if cat not in category_posts:
            continue
        cat_posts = category_posts[cat]
        total_pages_cat = max(1, math.ceil(len(cat_posts) / POSTS_PER_PAGE))
        cat_title_en = CATEGORY_NAMES_EN.get(cat, cat.capitalize())
        for page_num in range(1, total_pages_cat + 1):
            filename = f'{cat}_en.html' if page_num == 1 else f'{cat}_page{page_num}_en.html'
            html_content = generate_page(
                cat_posts, page_num, total_pages_cat, cat,
                cat_title_en, category_posts, lang='en'
            )
            with open(os.path.join(DATA_FOLDER, filename), 'w', encoding='utf-8') as f:
                f.write(html_content)
            all_pages.add(filename)

    # ===== Отдельные страницы для каждой текстуры (RU + EN) =====
    print(f"📄 Проверяю отдельные страницы для {len(sorted_posts)} текстур...")
    texture_pages_new = 0
    texture_pages_skipped = 0

    for post in sorted_posts:
        post_id = post['id']

        # RU
        ru_filename = f'texture_{post_id}.html'
        ru_path = os.path.join(DATA_FOLDER, ru_filename)
        if os.path.exists(ru_path):
            all_pages.add(ru_filename)
            texture_pages_skipped += 1
        else:
            try:
                ru_html = generate_texture_page(post, category_posts, lang='ru')
                with open(ru_path, 'w', encoding='utf-8') as f:
                    f.write(ru_html)
                all_pages.add(ru_filename)
                texture_pages_new += 1
            except Exception as e:
                print(f"⚠️ Ошибка генерации RU-страницы для {post_id}: {e}")

        # EN
        en_filename = f'texture_{post_id}_en.html'
        en_path = os.path.join(DATA_FOLDER, en_filename)
        if os.path.exists(en_path):
            all_pages.add(en_filename)
            texture_pages_skipped += 1
        else:
            try:
                en_html = generate_texture_page(post, category_posts, lang='en')
                with open(en_path, 'w', encoding='utf-8') as f:
                    f.write(en_html)
                all_pages.add(en_filename)
                texture_pages_new += 1
            except Exception as e:
                print(f"⚠️ Ошибка генерации EN-страницы для {post_id}: {e}")

    print(f"✅ Новых страниц: {texture_pages_new}, пропущено (уже есть): {texture_pages_skipped}")

    generate_robots_txt()
    generate_sitemap(all_pages)

    print(f"✅ Сайт пересобран (RU + EN) + SEO файлы в папке {DATA_FOLDER}")


def git_commit_and_push():
    try:
        print("🔄 Отправляю изменения в репозиторий...")
        subprocess.run(["git", "config", "--global", "user.name", "github-actions[bot]"], check=True)
        subprocess.run(["git", "config", "--global", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)

        subprocess.run(["git", "add", "posts.json", "public/"], check=True)
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)

        if status.stdout.strip():
            subprocess.run(
                ["git", "commit", "-m", "Auto-update posts and images [skip ci]"],
                check=True
            )
            subprocess.run(["git", "push"], check=True)
            print("✅ Файлы запушены в репозиторий!")
        else:
            print("ℹ️ Нет изменений для коммита.")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Git ошибка: {e}")
    except Exception as e:
        print(f"⚠️ Ошибка при автокоммите: {e}")


async def main():
    print("🔍 Проверяю канал...")
    all_posts = load_all_posts()
    print(f"📚 Загружено постов: {len(all_posts)}")

    print("👤 Авторизуюсь...")
    await client.start()

    try:
        new_posts = await parse_channel(all_posts)

        if new_posts:
            all_posts.extend(new_posts)
            all_posts.sort(key=lambda x: x.get('id', 0))
            save_all_posts(all_posts)
            print(f"💾 Всего постов после обновления: {len(all_posts)}")

        print("🏗️ Пересобираю сайт...")
        generate_site(all_posts)
        git_commit_and_push()

    finally:
        await client.disconnect()
        print("🔒 Сессия закрыта")


if __name__ == '__main__':
    asyncio.run(main())
