import qrcode
import base64
from io import BytesIO

def get_qr_code_image(data):
    """
    Generates a QR code for the given data and returns it as a base64 encoded string.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = BytesIO()
    try:
        img.save(buffer, format="PNG")
    except TypeError:
        # Fallback for PyPNGImage which doesn't accept 'format'
        img.save(buffer)
        
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return f"data:image/png;base64,{img_str}"
