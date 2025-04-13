def format_bytes(bytes_val):
    if bytes_val is None:
        return "N/A"
    if not isinstance(bytes_val, (int, float)) or bytes_val < 0:
        return "Invalid" 
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024**2:
        return f"{bytes_val/1024:.1f} KiB"
    elif bytes_val < 1024**3:
        return f"{bytes_val/1024**2:.1f} MiB"
    else:
        return f"{bytes_val/1024**3:.1f} GiB"
