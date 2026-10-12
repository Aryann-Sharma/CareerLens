from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject


def make_pdf(text="Python SQL Git", *, pages=1, encrypted=False, laid_out=False):
    writer = PdfWriter()
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    for _ in range(pages):
        page = writer.add_blank_page(612, 792)
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if laid_out:
            # Separate text operations reproduce a visible document's line breaks.
            content = " T* ".join(f"({line}) Tj" for line in escaped.splitlines())
            stream.set_data(f"BT /F1 11 Tf 15 TL 50 740 Td {content} ET".encode("ascii"))
        else:
            stream.set_data(f"BT /F1 12 Tf 50 700 Td ({escaped}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("password")
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
