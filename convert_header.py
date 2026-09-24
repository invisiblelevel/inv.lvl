from PIL import Image
import os

src = os.path.join('public', 'header.png')
dst = os.path.join('public', 'header.webp')

if not os.path.exists(src):
    print(f"❌ Не найден: {src}")
    exit(1)

img = Image.open(src)
print(f"Исходник: {img.size}, mode={img.mode}")

if img.mode not in ('RGB', 'RGBA'):
    img = img.convert('RGB')

# Уменьшаем ширину до разумного максимума
max_width = 1550
if img.width > max_width:
    ratio = max_width / img.width
    new_h = int(img.height * ratio)
    img = img.resize((max_width, new_h), Image.LANCZOS)
    print(f"Ресайз до: {img.size}")

# Сохраняем в WebP
img.save(dst, 'WEBP', quality=85, method=6)

old_size = os.path.getsize(src) / 1024
new_size = os.path.getsize(dst) / 1024

print()
print(f"Было:  {old_size:.0f} КБ")
print(f"Стало: {new_size:.0f} КБ")
print(f"Сжатие: {old_size/new_size:.1f}x")

# Удаляем старый PNG
try:
    os.remove(src)
    print(f"🗑️ Удалён: {src}")
except Exception as e:
    print(f"⚠️ Не удалось удалить {src}: {e}")

print()
print(f"📐 Финальный размер картинки: {img.size[0]}×{img.size[1]}")
print(f"📌 Используй эти значения для width и height в HTML:")
print(f'   <img src="header.webp" width="{img.size[0]}" height="{img.size[1]}" loading="eager" fetchpriority="high" alt="InvisibleLevel Textures">')