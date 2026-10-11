from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


def make_image(text="Required skills: Python, SQL and Git.", format="PNG", size=(1000, 180), **options):
    image = Image.new("RGB", size, "white")
    ImageDraw.Draw(image).text((25, 40), text, font=ImageFont.load_default(size=32), fill="black")
    buffer = BytesIO()
    image.save(buffer, format=format, **options)
    return buffer.getvalue()
