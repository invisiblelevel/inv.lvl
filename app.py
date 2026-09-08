import os
import json
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import math

# ===================== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ =====================
api_id = int(os.environ.get('API_ID', 0))
api_hash = os.environ.get('API_HASH', '')
session_string = os.environ.get('SESSION_STRING', '')
channel_link = os.environ.get('CHANNEL_LINK', '')

CATEGORY_HASHTAGS = ['terrain', 'metal', 'wood', 'brick', 'concrete', 'stone', 'tile', 'fabric', 'organic', 'plastic', 'leather']
POSTS_PER_PAGE = 30
# ===============================================================

DATA_FOLDER = 'public'
os.makedirs(DATA_FOLDER, exist_ok=True)
POSTS_JSON = 'posts.json'

client = TelegramClient(StringSession(session_string), api_id, api_hash)

def load_all_posts():
    if os.path.exists(POSTS_JSON):
        try:
            with open(POSTS_JSON, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_all_posts(posts):
    with open(POSTS_JSON, 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

def get_last_post_id(posts):
    if not posts:
        return 0
    return max(p.get('id', 0) for p in posts)

async def download_photo(message, filename):
    path = os.path.join(DATA_FOLDER, filename)
    if os.path.exists(path):
        return path
    try:
        await client.download_media(message.media, file=path)
        return path
    except Exception as e:
        print(f"Ошибка скачивания: {e}")
        return None

async def parse_channel(existing_posts):
    entity = await client.get_entity(channel_link)
    username = entity.username

    last_id = get_last_post_id(existing_posts)
    print(f"📌 Последний сохраненный ID поста: {last_id}")

    new_messages = []
    async for msg in client.iter_messages(entity, min_id=last_id, reverse=True):
        new_messages.append(msg)

    if not new_messages:
        print("ℹ️ Новых постов нет")
        return []

    new_posts = []
    current_post = None

    for msg in new_messages:
        if msg.photo:
            filename = f"{msg.id}_preview.jpg"
            await download_photo(msg, filename)
            current_post = {
                'id': msg.id,
                'photo': filename,
                'text': "",
                'archive_link': None,
                'hashtags': []
            }
            new_posts.append(current_post)
            print(f"📸 Новый пост #{msg.id} (картинка)")

        elif msg.document:
            if current_post:
                current_post['id'] = max(current_post.get('id', 0), msg.id)
                current_post['archive_link'] = f"https://t.me/{username}/{msg.id}"
                if msg.text:
                    raw_text = msg.text
                    hashtags = [word.strip() for word in raw_text.split() if word.startswith('#')]
                    current_post['hashtags'] = hashtags
                    lines = [line.strip() for line in raw_text.split('\n') if line.strip() and not line.strip().startswith('#')]
                    current_post['text'] = '\n'.join(lines)
                print(f"📦 Новый пост #{msg.id} (архив + текст)")

    new_posts = [p for p in new_posts if p['photo'] is not None]
    print(f"✅ Найдено новых постов: {len(new_posts)}")
    return new_posts

def get_category(post):
    for tag in post.get('hashtags', []):
        if tag.startswith('#'):
            tag_clean = tag[1:].lower()
            if tag_clean in CATEGORY_HASHTAGS:
                return tag_clean
    return None

def render_card(post):
    lines = post['text'].split('\n') if post['text'] else []
    title = lines[0] if lines else "Текстура"
    desc = '\n'.join(lines[1:]) if len(lines) > 1 else ''
    
    tags_html = ""
    if post.get('hashtags'):
        tags_html = '<div class="tags">' + ' '.join([f'<span class="tag">{tag}</span>' for tag in post['hashtags']]) + '</div>'

    img_tag = f'<img src="{post["photo"]}" alt="{title}">' if post['photo'] else ''
    card_img = f'<a href="{post["photo"]}" target="_blank" title="Открыть в полном разрешении">{img_tag}</a>' if post['photo'] else ''

    return f'''
    <div class="card">
        {card_img}
        <div class="info">
            <div class="title">{title}</div>
            {f'<div class="desc">{desc}</div>' if desc else ''}
            {tags_html}
            {f'<a class="link" href="{post["archive_link"]}" target="_blank">Скачать архив</a>' if post['archive_link'] else ''}
        </div>
    </div>
    '''

def render_nav(current_page, total_pages, base_name):
    if total_pages <= 1:
        return ''
    nav = '<div class="pagination">'
    for i in range(1, total_pages + 1):
        if i == current_page:
            nav += f'<span class="active">{i}</span>'
        else:
            if i == 1:
                nav += f'<a href="{base_name}.html">{i}</a>'
            else:
                nav += f'<a href="{base_name}_page{i}.html">{i}</a>'
    nav += '</div>'
    return nav

def generate_page(posts, page_num, total_pages, base_name, title, category_posts):
    start = (page_num - 1) * POSTS_PER_PAGE
    end = min(start + POSTS_PER_PAGE, len(posts))
    page_posts = posts[start:end]

    all_page_tags = set()
    for p in page_posts:
        for t in p.get('hashtags', []):
            all_page_tags.add(t.lstrip('#'))
    keywords_str = ', '.join(all_page_tags)

    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{title}</title>
        <meta name="keywords" content="{keywords_str}, pbr textures, 3d assets">
        <meta name="description" content="{title} — бесплатные PBR текстуры и материалы для 3D художников.">
        <style>
            body {{ font-family: sans-serif; background: #1a1a1a; color: #fff; margin: 0; padding: 20px; }}
            .gallery {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 20px; max-width: 1200px; margin: 0 auto; }}
            .card {{ background: #2a2a2a; border-radius: 8px; overflow: hidden; transition: transform 0.2s; }}
            .card:hover {{ transform: scale(1.02); }}
            .card a img {{ width: 100%; height: 200px; object-fit: cover; display: block; cursor: zoom-in; transition: opacity 0.2s; }}
            .card a img:hover {{ opacity: 0.85; }}
            .card .info {{ padding: 15px; }}
            .card .info .title {{ font-weight: bold; margin-bottom: 5px; color: #fff; font-size: 1.1em; }}
            .card .info .desc {{ color: #aaa; font-size: 0.9em; white-space: pre-wrap; }}
            .card .info .tags {{ margin-top: 8px; display: flex; flex-wrap: wrap; gap: 4px; }}
            .card .info .tag {{ background: #3a3a3a; color: #8ab4f8; font-size: 0.75em; padding: 2px 6px; border-radius: 4px; }}
            .card .info .link {{ display: inline-block; margin-top: 10px; background: #4a6fa5; color: #fff; padding: 5px 15px; border-radius: 4px; text-decoration: none; font-size: 0.9em; }}
            .card .info .link:hover {{ background: #5a7fb5; }}
            .nav {{ text-align: center; margin-bottom: 30px; }}
            .nav a {{ color: #4a6fa5; text-decoration: none; margin: 0 10px; }}
            .nav a:hover {{ text-decoration: underline; }}
            .pagination {{ text-align: center; margin-top: 30px; }}
            .pagination a, .pagination span {{ display: inline-block; padding: 8px 14px; margin: 0 4px; background: #2a2a2a; border-radius: 4px; color: #fff; text-decoration: none; }}
            .pagination a:hover {{ background: #4a6fa5; }}
            .pagination span.active {{ background: #4a6fa5; }}
        </style>
    </head>
    <body>
        <div class="nav">
            <a href="index.html">Главная</a>
    '''

    for cat in category_posts.keys():
        html += f'<a href="{cat}.html">{cat.capitalize()}</a>'

    html += f'''
        </div>
        <h1 style="text-align:center; margin-bottom: 30px;">{title}</h1>
        <div class="gallery">
    '''

    for post in page_posts:
        html += render_card(post)

    html += '''
        </div>
    '''
    html += render_nav(page_num, total_pages, base_name)
    html += '''
    </body>
    </html>
    '''
    return html

def generate_site(all_posts):
    if not all_posts:
        print("ℹ️ Нет постов для генерации сайта")
        return

    sorted_posts = sorted(all_posts, key=lambda x: x.get('id', 0), reverse=True)

    category_posts = {}
    for post in sorted_posts:
        cat = get_category(post)
        if cat:
            if cat not in category_posts:
                category_posts[cat] = []
            category_posts[cat].append(post)

    total_pages = math.ceil(len(sorted_posts) / POSTS_PER_PAGE)
    for page_num in range(1, total_pages + 1):
        filename = 'index.html' if page_num == 1 else f'index_page{page_num}.html'
        html = generate_page(sorted_posts, page_num, total_pages, 'index', 'Все текстуры', category_posts)
        with open(os.path.join(DATA_FOLDER, filename), 'w', encoding='utf-8') as f:
            f.write(html)

    for cat, cat_posts in category_posts.items():
        total_pages_cat = math.ceil(len(cat_posts) / POSTS_PER_PAGE)
        for page_num in range(1, total_pages_cat + 1):
            filename = f'{cat}.html' if page_num == 1 else f'{cat}_page{page_num}.html'
            html = generate_page(cat_posts, page_num, total_pages_cat, cat, cat.capitalize(), category_posts)
            with open(os.path.join(DATA_FOLDER, filename), 'w', encoding='utf-8') as f:
                f.write(html)

    print(f"✅ Сайт успешно пересобран в папке {DATA_FOLDER}")

async def main():
    print("🔍 Проверяю канал на новые посты...")
    all_posts = load_all_posts()
    
    async with client:
        new_posts = await parse_channel(all_posts)
        if new_posts:
            all_posts.extend(new_posts)
            save_all_posts(all_posts)
            generate_site(all_posts)
        else:
            print("ℹ️ База актуальна, генерация страниц не требуется.")
            if not os.path.exists(os.path.join(DATA_FOLDER, "index.html")):
                generate_site(all_posts)

if __name__ == '__main__':
    asyncio.run(main())
