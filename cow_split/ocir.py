import os

# ===============================
# 🔥 Paddle CPU 완전 안정화 (import 전에!)
# ===============================
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

from tkinter import Tk, filedialog
from paddleocr import PaddleOCR
from PIL import Image, ImageDraw, ImageFont


def select_image_file():
    root = Tk()
    root.withdraw()
    return filedialog.askopenfilename(
        title="OCR 할 이미지 선택",
        filetypes=[
            ("Image files", "*.png;*.jpg;*.jpeg;*.bmp"),
            ("All files", "*.*")
        ]
    )


def main():
    print("📌 이미지 OCR 프로그램 시작")

    image_path = select_image_file()
    if not image_path:
        print("❌ 이미지 선택 취소")
        return

    print(f"🖼 선택된 이미지: {image_path}")

    # 🔑 핵심: 경로(str) 그대로 전달
    ocr = PaddleOCR(
        lang="korean",
        device="cpu",
        enable_mkldnn=False,
        cpu_threads=1,
        show_log=False
    )

    result = ocr.ocr(image_path, cls=True)

    if not result or not result[0]:
        print("❌ 인식된 텍스트 없음")
        return

    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)

    font_path = "font/NanumGothic-Bold.ttf"
    font = ImageFont.truetype(font_path, 24)

    for box, (text, score) in result[0]:
        top_left = tuple(map(int, box[0]))
        bottom_right = tuple(map(int, box[2]))

        print(f"Detected text: {text} (Probability: {score:.2f})")

        draw.rectangle([top_left, bottom_right], outline=(0, 255, 0), width=2)
        draw.text(top_left, text, font=font, fill=(255, 0, 0))

    output_path = os.path.join(
        os.path.dirname(image_path),
        "result_ocr.jpg"
    )
    image.save(output_path)

    print(f"✅ 결과 이미지 저장: {output_path}")


if __name__ == "__main__":
    main()
