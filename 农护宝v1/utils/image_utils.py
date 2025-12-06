from io import BytesIO
from PIL import Image

def load_image_from_bytes(img_bytes: bytes) -> Image.Image:
    image = Image.open(BytesIO(img_bytes))
    if image.mode != "RGB":
        image = image.convert("RGB")
    return image