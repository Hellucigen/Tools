import os
import shutil

# ================= 配置区域 =================

# 源文件夹：创意工坊下载的新Mod位置
source_dir = r"D:\Steam\steamapps\workshop\content\294100"

# 目标文件夹：RimWorld 游戏的 Mods 目录
target_dir = r"D:\Steam\steamapps\common\RimWorld\Mods"

# 【已更新】仅包含最新图片中的5个文件夹编号
folders_to_update = [
    "3551203752",
    "3498575851",
    "2379076640",
    "3770112044",
    "3717539116",
    "3750208980",
    "839005762"
]

def update_specific_mods(src, dst, mod_list):
    print(f"--- 准备处理 {len(mod_list)} 个指定 Mod ---")

    success_count = 0
    fail_count = 0

    for folder_name in mod_list:
        src_path = os.path.join(src, folder_name)
        dst_path = os.path.join(dst, folder_name)

        # 1. 检查源文件是否存在 (即创意工坊是否下载了该Mod)
        if not os.path.exists(src_path):
            print(f"[跳过] 源文件夹中未找到: {folder_name}")
            fail_count += 1
            continue

        try:
            # 2. 如果目标位置已经存在旧版本，先彻底删除
            if os.path.exists(dst_path):
                print(f"[清理] 正在删除旧版本: {folder_name} ...")
                shutil.rmtree(dst_path)

            # 3. 从源位置复制到目标位置
            # copytree 会把整个文件夹复制过去，无论目标之前是否存在（因为刚才已经删了）
            print(f"[复制] 正在安装/更新: {folder_name} ...")
            shutil.copytree(src_path, dst_path)

            success_count += 1
            print(f"[成功] {folder_name} 处理完成。")
            print("-" * 30)

        except Exception as e:
            print(f"[错误] 处理 {folder_name} 时失败: {e}")
            fail_count += 1

    print("\n================ 任务结束 ================")
    print(f"成功: {success_count} 个")
    print(f"失败/跳过: {fail_count} 个")


if __name__ == "__main__":
    update_specific_mods(source_dir, target_dir, folders_to_update)
    input("按回车键退出...")