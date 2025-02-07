import os
from dotenv import load_dotenv
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import docx

load_dotenv()
file_path = os.getenv("FILE_PATH")
output_folder = os.getenv("OUTPUT_FOLDER")
water_mark = os.getenv("WATER_MARK")


def format_image_name(img_count, img_ext) -> str:
    return os.path.join(output_folder, f"image_{img_count}.{img_ext}")


def save_image(img_filename, img_bytes) -> None:
    with open(img_filename, "wb") as img:
        img.write(img_bytes)


def print_watermark(img_filename) -> None:
    with Image.open(img_filename) as img:
        draw = ImageDraw.Draw(img)
        font_size = int(img.height * 0.04)  # Dynamically adjust font size
        try:
            font = ImageFont.truetype("/Library/Fonts/Arial.ttf", font_size)
        except Exception as e:
            font = ImageFont.load_default()
            print(f"Warning font size: {e}")
        text = water_mark
        position = (10, img.height - font_size - 10)  # 左下角
        draw.text(position, text, fill="white", font=font)
        img.save(img_filename)


def extract_text_and_images():
    """
    Extract text and image from file
    """
    if not file_path or not output_folder or not water_mark:
        raise ValueError("FILE_PATH 或 OUTPUT_FOLDER 未在 .env 文件中定義")

    # Check / Create folder
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    all_text = ""
    image_count = 0

    # Open PDF
    if file_path.endswith(".pdf"):
        pdf_document = fitz.open(file_path)
        # Loop through pages
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]

            # Extract Text
            all_text += page.get_text()

            # Extract Image
            images = page.get_images(full=True)
            for _img_idx, img in enumerate(images):
                image_count += 1
                xref = img[0]
                base_image = pdf_document.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                image_filename = format_image_name(image_count, image_ext)
                # Save Image
                save_image(image_filename, image_bytes)
                # Water Print
                print_watermark(image_filename)

    elif file_path.endswith(".docx"):
        # Open Word
        doc = docx.Document(file_path)

        # Extract Text
        for paragraph in doc.paragraphs:
            all_text += paragraph.text + "\n"

        # Extract Image
        for rel in doc.part.rels.values():
            if "image" in rel.target_ref:
                image_count += 1
                image_bytes = rel.target_part.blob
                image_ext = rel.target_ref.split(".")[-1]
                image_filename = format_image_name(image_count, image_ext)
                # Save Image
                save_image(image_filename, image_bytes)
                # Water Print
                print_watermark(image_filename)

    else:
        raise ValueError("只支持 PDF 和 Word 文件格式")

    # Save to Txt
    text_filename = os.path.join(output_folder, "extracted_text.txt")
    with open(text_filename, "w", encoding="utf-8") as text_file:
        text_file.write(all_text)

    print(f"Extraction complete! {image_count} images saved to '{output_folder}', "
          "and text saved to 'extracted_text.txt'.")


if __name__ == "__main__":
    extract_text_and_images()
