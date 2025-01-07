def generate_qr_code_b64(uri: str) -> str:
    """Generate QR code for the URI and return as base64 string."""
    if not uri:
        raise ValueError("URI cannot be empty")

    try:
        import qrcode
        from io import BytesIO
        import base64
    except ImportError:
        raise ImportError("Please install qrcode library to generate QR codes.")

    try:
        # Create QR code instance
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )

        # Add the URI data
        qr.add_data(uri)
        qr.make(fit=True)

        # Create the QR code image
        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffered = BytesIO()
        img.save(buffered)  # Remove the format parameter altogether
        buffered.seek(0)
        return base64.b64encode(buffered.getvalue()).decode()

    except Exception as e:
        raise RuntimeError(f"Failed to generate QR code: {str(e)}")
