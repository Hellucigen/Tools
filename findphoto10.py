import os
import shutil
from PIL import Image
from PIL.ExifTags import TAGS

# ===== 配置区域 =====
TARGET_DRIVE = "I:\\"  # 修改为你要查找的磁盘盘符
OUTPUT_DIR = "D:\\2024年10月照片"  # 查找到的照片将复制到此文件夹
TARGET_YEAR_MONTH = "2024-10"  # 目标年月
SUPPORTED_EXTS = (".jpg", ".jpeg", ".png", ".heic", ".tiff")


# ====================

def get_exif_date(file_path):
    """从照片EXIF中提取拍摄时间"""
    try:
        img = Image.open(file_path)
        exif = img._getexif()
        if exif:
            for tag_id, value in exif.items():
                tag_name = TAGS.get(tag_id, tag_id)
                if tag_name == "DateTimeOriginal":
                    # EXIF格式通常为 "2024:10:01 12:00:00"
                    return value.split(" ")[0].replace(":", "-")[:7]
    except Exception:
        pass
    return None


def find_and_copy_photos():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    print(f"正在扫描 {TARGET_DRIVE}，寻找 {TARGET_YEAR_MONTH} 的照片...")
    count = 0

    for root, _, files in os.walk(TARGET_DRIVE):
        for file in files:
            if file.lower().endswith(SUPPORTED_EXTS):
                full_path = os.path.join(root, file)
                date = get_exif_date(full_path)

                if date == TARGET_YEAR_MONTH:
                    dest_path = os.path.join(OUTPUT_DIR, file)
                    # 处理重名文件
                    base, ext = os.path.splitext(file)
                    i = 1
                    while os.path.exists(dest_path):
                        dest_path = os.path.join(OUTPUT_DIR, f"{base}_{i}{ext}")
                        i += 1

                    shutil.copy2(full_path, dest_path)
                    print(f"已找到并复制: {full_path}")
                    count += 1

    print(f"\n扫描完成！共找到并复制了 {count} 张照片到 {OUTPUT_DIR}")


if __name__ == "__main__":
    find_and_copy_photos()