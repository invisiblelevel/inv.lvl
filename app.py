import os
import json
import asyncio
import subprocess
from telethon import TelegramClient
from telethon.sessions import StringSession
import math

# ===================== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ =====================
api_id = int(os.environ.get('API_ID', 0))
api_hash = os.environ.get('API_HASH', '')
session_string = os.environ.get('SESSION_STRING', '')
channel_link = os.environ.get('CHANNEL_LINK', '')

CATEGORY_HASHTAGS = ['terrain', 'metal', 'wood', 'brick', 'concrete', 'stone', 'tile', 'fabric', 'organic', 'plastic', 'leather']

CATEGORY_NAMES_RU = {
    'terrain': 'Ландшафт',
    'metal': 'Металл',
    'wood': 'Дерево',
    'brick': 'Кирпич',
    'concrete': 'Бетон',
    'stone': 'Камень',
    'tile': 'Плитка',
    'fabric': 'Ткань',
    'organic': 'Органика',
    'plastic': 'Пластик',
    'leather': 'Кожа'
}

POSTS_PER_PAGE = 30
# ===============================================================

DATA_FOLDER = 'public'
os.makedirs(DATA_FOLDER, exist_ok=True)
POSTS_JSON = 'posts.json'

if not session_string:
    raise ValueError("❌ SESSION_STRING не задан. Добавь секрет SESSION_STRING в настройках репозитория.")

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

def load_text_file(filename):
    variants = [filename, filename.lower(), filename.replace(' ', ''), filename.replace(' ', '_')]
    for name in variants:
        if os.path.exists(name):
            for encoding in ['utf-8', 'cp1251', 'latin-1']:
                try:
                    with open(name, 'r', encoding=encoding) as f:
                        text = f.read()
                        print(f"✅ Успешно прочитан файл: {name} (кодировка: {encoding})")
                        return text
                except Exception as e:
                    print(f"⚠️ Не удалось прочитать {name} в кодировке {encoding}: {e}")
    print(f"❌ ВНИМАНИЕ: Файл '{filename}' вообще не найден в корне проекта!")
    return None

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

def render_card(post, lang='ru'):
    lines = post['text'].split('\n') if post['text'] else []
    title = lines[0] if lines else ("Texture" if lang == 'en' else "Текстура")
    desc = '\n'.join(lines[1:]) if len(lines) > 1 else ''
    
    tags_html = ""
    if post.get('hashtags'):
        tags_html = '<div class="tags">' + ' '.join([f'<span class="tag">{tag}</span>' for tag in post['hashtags']]) + '</div>'

    img_tag = f'<img src="{post["photo"]}" alt="{title}">' if post['photo'] else ''
    title_attr = "Open in full resolution" if lang == 'en' else "Открыть в полном разрешении"
    card_img = f'<a href="{post["photo"]}" target="_blank" title="{title_attr}">{img_tag}</a>' if post['photo'] else ''
    btn_text = 'Download Archive' if lang == 'en' else 'Скачать архив'

    return f'''
    <div class="card">
        {card_img}
        <div class="info">
            <div class="title">{title}</div>
            {f'<div class="desc">{desc}</div>' if desc else ''}
            {tags_html}
            {f'<a class="link" href="{post["archive_link"]}" target="_blank">{btn_text}</a>' if post['archive_link'] else ''}
        </div>
    </div>
    '''

def render_nav(current_page, total_pages, base_name, lang='ru'):
    if total_pages <= 1:
        return ''
    suffix = '_en' if lang == 'en' else ''
    ext = '.html'
    nav = '<div class="pagination">'
    for i in range(1, total_pages + 1):
        if i == current_page:
            nav += f'<span class="active">{i}</span>'
        else:
            if i == 1:
                nav += f'<a href="{base_name}{suffix}{ext}">{i}</a>'
            else:
                nav += f'<a href="{base_name}_page{i}{suffix}{ext}">{i}</a>'
    nav += '</div>'
    return nav

def generate_page(posts, page_num, total_pages, base_name, title, category_posts, lang='ru'):
    start = (page_num - 1) * POSTS_PER_PAGE
    end = min(start + POSTS_PER_PAGE, len(posts))
    page_posts = posts[start:end]

    all_page_tags = set()
    for p in page_posts:
        for t in p.get('hashtags', []):
            all_page_tags.add(t.lstrip('#'))
    keywords_str = ', '.join(all_page_tags)

    suffix = '_en' if lang == 'en' else ''
    home_link = f'index{suffix}.html'
    other_lang_link = f'{base_name}.html' if lang == 'en' else f'{base_name}_en.html'
    lang_btn_text = 'RU' if lang == 'en' else 'EN'

    info_title = 'Info' if lang == 'en' else 'Информация'
    info_desc = 'About the project and archive.' if lang == 'en' else 'О проекте и архиве.'
    info_btn = 'Open' if lang == 'en' else 'Открыть'

    donate_title = 'Donate' if lang == 'en' else 'Поддержка'
    donate_desc = 'Support the project.' if lang == 'en' else 'Поддержать проект.'
    donate_btn = 'Details' if lang == 'en' else 'Реквизиты'

    modal_info_h = 'About Project' if lang == 'en' else 'Информация о проекте'
    
    readme_filename = 'Readme EN.txt' if lang == 'en' else 'Readme RU.txt'
    readme_text = load_text_file(readme_filename)

    if readme_text:
        modal_info_p = '<pre style="white-space: pre-wrap; font-family: inherit; margin: 0; text-align: left;">' + readme_text + '</pre>'
    else:
        modal_info_p = 'Free archive of PBR textures.' if lang == 'en' else 'Бесплатный архив PBR-текстур.'

    modal_donate_h = 'Support Project' if lang == 'en' else 'Поддержать проект'
    
    donate_file_text = load_text_file('Donate.txt')
    if donate_file_text:
        modal_donate_p = '<pre style="white-space: pre-wrap; font-family: inherit; margin: 0; text-align: left;">' + donate_file_text + '</pre>'
    else:
        modal_donate_p = 'If these materials help in your work, you can support the archive.' if lang == 'en' else 'Если материалы помогают в работе, можешь поддержать архив.'

    home_text = 'Home' if lang == 'en' else 'Главная'

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
            .site-wrapper {{ display: flex; max-width: 1550px; margin: 0 auto; gap: 20px; align-items: flex-start; justify-content: center; }}
            
            .sidebar {{ width: 220px; flex-shrink: 0; display: flex; flex-direction: column; gap: 15px; position: sticky; top: 20px; }}
            .side-block {{ background: #2a2a2a; border-radius: 8px; padding: 20px; cursor: pointer; transition: transform 0.2s, background 0.2s; text-align: center; }}
            .side-block:hover {{ background: #333; transform: translateY(-2px); }}
            .side-block h3 {{ margin-top: 0; color: #fff; font-size: 1.1em; }}
            .side-block p {{ color: #aaa; font-size: 0.85em; margin-bottom: 15px; }}
            .side-block .btn-link {{ display: inline-block; background: #4a6fa5; color: #fff; padding: 6px 15px; border-radius: 4px; font-size: 0.85em; }}

            .main-content {{ flex: 1; min-width: 0; max-width: 1100px; }}
            
            .gallery {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 20px; }}
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
            
            .nav {{ text-align: center; margin-bottom: 20px; }}
            .nav a {{ color: #4a6fa5; text-decoration: none; margin: 0 10px; display: inline-block; }}
            .nav a:hover {{ text-decoration: underline; }}
            .lang-btn {{ background: #333; padding: 4px 10px; border-radius: 4px; border: 1px solid #4a6fa5; font-weight: bold; }}
            
            .pagination {{ text-align: center; margin-top: 30px; }}
            .pagination a, .pagination span {{ display: inline-block; padding: 8px 14px; margin: 0 4px; background: #2a2a2a; border-radius: 4px; color: #fff; text-decoration: none; }}
            .pagination a:hover {{ background: #4a6fa5; }}
            .pagination span.active {{ background: #4a6fa5; }}

            /* Модальные окна */
            .modal {{ display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); align-items: center; justify-content: center; }}
            .modal-content {{ background: #222; padding: 30px; border-radius: 10px; max-width: 600px; width: 90%; max-height: 80vh; overflow-y: auto; color: #fff; position: relative; box-shadow: 0 4px 20px rgba(0,0,0,0.5); line-height: 1.5; }}
            .close {{ position: absolute; right: 15px; top: 10px; font-size: 28px; cursor: pointer; color: #aaa; }}
            .close:hover {{ color: #fff; }}
            .modal-content code {{ background: #111; padding: 2px 6px; border-radius: 4px; color: #8ab4f8; font-family: monospace; }}

            @media (max-width: 1100px) {{
                .site-wrapper {{ flex-direction: column; align-items: stretch; }}
                .sidebar {{ width: 100%; position: static; flex-direction: row; }}
                .side-block {{ flex: 1; }}
            }}
        </style>
    </head>
    <body>
        <div class="nav">
            <a href="{home_link}">{home_text}</a>
    '''

    for cat in category_posts.keys():
        cat_filename = f'{cat}{suffix}.html'
        cat_display = CATEGORY_NAMES_RU.get(cat, cat.capitalize()) if lang == 'ru' else cat.capitalize()
        html += f'<a href="{cat_filename}">{cat_display}</a>'

    html += f'''
            <a href="{other_lang_link}" class="lang-btn">{lang_btn_text}</a>
        </div>
        <h1 style="text-align:center; margin-bottom: 30px;">{title}</h1>
        
        <div class="site-wrapper">
            <!-- Левый блок: Информация -->
            <div class="sidebar">
                <div class="side-block" onclick="openModal('infoModal')">
                    <h3>ℹ️ {info_title}</h3>
                    <p>{info_desc}</p>
                    <span class="btn-link">{info_btn}</span>
                </div>
            </div>

            <!-- Центральный блок с текстурами -->
            <div class="main-content">
                <div class="gallery">
    '''

    for post in page_posts:
        html += render_card(post, lang)

    html += '''
                </div>
    '''
    html += render_nav(page_num, total_pages, base_name, lang)
    html += '''
            </div>

            <!-- Правый блок: Donate -->
            <div class="sidebar">
                <div class="side-block" onclick="openModal('donateModal')">
                    <h3>🪙 {donate_title}</h3>
                    <p>{donate_desc}</p>
                    <span class="btn-link">{donate_btn}</span>
                </div>
            </div>
        </div>

        <!-- Модальное окно: Информация -->
        <div id="infoModal" class="modal" onclick="closeModal(event, 'infoModal')">
            <div class="modal-content">
                <span class="close" onclick="closeModalDirect('infoModal')">&times;</span>
                <h2>{modal_info_h}</h2>
                <div>{modal_info_p}</div>
            </div>
        </div>

        <!-- Модальное окно: Donate -->
        <div id="donateModal" class="modal" onclick="closeModal(event, 'donateModal')">
            <div class="modal-content">
                <span class="close" onclick="closeModalDirect('donateModal')">&times;</span>
                <h2>{modal_donate_h}</h2>
                <div>{modal_donate_p}</div>
            </div>
        </div>

        <script>
            function openModal(id) {{ 
                var m = document.getElementById(id);
                if(m) m.style.display = 'flex'; 
            }}
            function closeModalDirect(id) {{ 
                var m = document.getElementById(id);
                if(m) m.style.display = 'none'; 
            }}
            function closeModal(e, id) {{ 
                if(e.target.id === id) {{ 
                    document.getElementById(id).style.display = 'none'; 
                }} 
            }}
        </script>
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

    # Генерация русской версии
    total_pages = math.ceil(len(sorted_posts) / POSTS_PER_PAGE)
    for page_num in range(1, total_pages + 1):
        filename = 'index.html' if page_num == 1 else f'index_page{page_num}.html'
        html = generate_page(sorted_posts, page_num, total_pages, 'index', 'Все текстуры', category_posts, lang='ru')
        with open(os.path.join(DATA_FOLDER, filename), 'w', encoding='utf-8') as f:
            f.write(html)

    for cat, cat_posts in category_posts.items():
        total_pages_cat = math.ceil(len(cat_posts) / POSTS_PER_PAGE)
        cat_title_ru = CATEGORY_NAMES_RU.get(cat, cat.capitalize())
        for page_num in range(1, total_pages_cat + 1):
            filename = f'{cat}.html' if page_num == 1 else f'{cat}_page{page_num}.html'
            html = generate_page(cat_posts, page_num, total_pages_cat, cat, cat_title_ru, category_posts, lang='ru')
            with open(os.path.join(DATA_FOLDER, filename), 'w', encoding='utf-8') as f:
                f.write(html)

    # Генерация английской версии
    for page_num in range(1, total_pages + 1):
        filename = 'index_en.html' if page_num == 1 else f'index_page{page_num}_en.html'
        html = generate_page(sorted_posts, page_num, total_pages, 'index', 'All Textures', category_posts, lang='en')
        with open(os.path.join(DATA_FOLDER, filename), 'w', encoding='utf-8') as f:
            f.write(html)

    for cat, cat_posts in category_posts.items():
        total_pages_cat = math.ceil(len(cat_posts) / POSTS_PER_PAGE)
        cat_title_en = cat.capitalize()
        for page_num in range(1, total_pages_cat + 1):
            filename = f'{cat}_en.html' if page_num == 1 else f'{cat}_page{page_num}_en.html'
            html = generate_page(cat_posts, page_num, total_pages_cat, cat, cat_title_en, category_posts, lang='en')
            with open(os.path.join(DATA_FOLDER, filename), 'w', encoding='utf-8') as f:
                f.write(html)

    print(f"✅ Сайт успешно пересобран (RU + EN) в папке {DATA_FOLDER}")

def git_commit_and_push():
    try:
        print("🔄 Отправляю изменения обратно в репозиторий...")
        subprocess.run(["git", "config", "--global", "user.name", "github-actions[bot]"], check=True)
        subprocess.run(["git", "config", "--global", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)
        subprocess.run(["git", "add", "posts.json", "public/"], check=True)
        
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
        if status.stdout.strip():
            subprocess.run(["git", "commit", "-m", "Auto-update posts and site [skip ci]"], check=True)
            subprocess.run(["git", "push"], check=True)
            print("✅ Изменения успешно запушены в репозиторий!")
        else:
            print("ℹ️ Нет новых изменений для коммита.")
    except Exception as e:
        print(f"⚠️ Ошибка при автокоммите в Git: {e}")

async def main():
    print("🔍 Проверяю канал на новые посты...")
    all_posts = load_all_posts()

    print("👤 Авторизуюсь через StringSession...")
    await client.start()

    try:
        new_posts = await parse_channel(all_posts)
        if new_posts:
            all_posts.extend(new_posts)
            save_all_posts(all_posts)
            generate_site(all_posts)
            git_commit_and_push()
        else:
            print("ℹ️ База актуальна, генерирую страницы со свежими файлами текста...")
            generate_site(all_posts)
            git_commit_and_push()
    finally:
        await client.disconnect()
        print("🔒 Сессия закрыта")

if __name__ == '__main__':
    asyncio.run(main())
