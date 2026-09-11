from PIL import Image

def process_image(input_path, output_path):
    """
    将图片转换为 175×175 像素、32位ARGB（RGBA模式）、PNG格式
    :param input_path: 输入图片路径（支持 JPG/PNG/BMP 等常见格式）
    :param output_path: 输出图片路径（需以 .png 结尾）
    """
    # 1. 打开输入图片
    img = Image.open(input_path)

    # 2. 调整尺寸为 175×175 像素（使用 LANCZOS 算法保证缩放质量）
    img_resized = img.resize((175, 175), Image.LANCZOS)

    # 3. 转换为 RGBA 模式（32位ARGB：R/G/B/A 各8位，PNG保存时自动对应 ARGB 通道）
    img_rgba = img_resized.convert("RGBA")

    # 4. 保存为 PNG 格式
    img_rgba.save(output_path, format="PNG")

    print(f"处理完成！输出文件：{output_path}")


# 示例调用（替换为你自己的输入/输出路径）
if __name__ == "__main__":
    input_img = r"C:\Users\Hellucigen\Downloads\8192093b17528faa676f02bb32792c54.jpg"# 输入图片路径（如本地文件 "test.jpg"）
    output_img = "output.png" # 输出图片路径（必须以 .png 结尾）
    process_image(input_img, output_img)