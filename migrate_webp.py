import os
import json
from PIL import Image

DATA_FOLDER = 'public'
IMAGES_FOLDER = os.path.join(DATA_FOLDER, 'images')
POSTS_JSON = 'posts.json'

WEBP_QUALITY = 82


def migrate():
    if not os.path.exists(POSTS_JSON):
        print("❌ posts.json не найден")
        return

    with open(POSTS_JSON, 'r', encoding='utf-8') as f:
        posts = json.load(f)

    print(f"📚 Загружено постов: {len(posts)}")

    converted = 0
    skipped = 0
    errors = 0

    for post in posts:
        photo = post.get('photo')
        if not photo:
            continue

        if photo.lower().endswith('.webp'):
            skipped += 1
            continue

        if not photo.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue

        base_name = os.path.splitext(photo)[0]
        new_photo = f"{base_name}.webp"
        old_path = os.path.join(IMAGES_FOLDER, photo)
        new_path = os.path.join(IMAGES_FOLDER, new_photo)

        if not os.path.exists(old_path):
            print(f"⚠️ Не найден: {old_path}")
            errors += 1
            continue

        if os.path.exists(new_path):
            print(f"⏩ Уже есть: {new_photo}")
        else:
            try:
                with Image.open(old_path) as img:
                    if img.mode not in ('RGB', 'L'):
                        img = img.convert('RGB')
                    img.save(new_path, 'WEBP', quality=WEBP_QUALITY, method=6)
                print(f"✅ {photo} → {new_photo}")
            except Exception as e:
                print(f"❌ Ошибка {photo}: {e}")
                errors += 1
                continue

        # Обновляем posts.json
        post['photo'] = new_photo
        converted += 1

    with open(POSTS_JSON, 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

    # ===== Удаляем старые JPEG =====
    print()
    print("🗑️ Удаляю старые JPEG...")
    removed = 0
    for filename in os.listdir(IMAGES_FOLDER):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            old_file = os.path.join(IMAGES_FOLDER, filename)
            base_name = os.path.splitext(filename)[0]
            webp_file = os.path.join(IMAGES_FOLDER, base_name + '.webp')
            # Удаляем, только если рядом есть .webp (значит конвертация прошла)
            if os.path.exists(webp_file):
                try:
                    os.remove(old_file)
                    removed += 1
                except Exception as e:
                    print(f"⚠️ Не удалось удалить {filename}: {e}")
            else:
                print(f"⚠️ Пропущен (нет .webp): {filename}")

    print()
    print(f"✅ Конвертировано: {converted}")
    print(f"⏩ Пропущено (уже webp): {skipped}")
    print(f"❌ Ошибок: {errors}")
    print(f"🗑️ Удалено старых JPEG: {removed}")


if __name__ == '__main__':
    migrate()