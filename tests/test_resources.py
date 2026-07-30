from __future__ import annotations

import struct

from PySide6.QtGui import QImage

from wslm.resources import APP_ICON_PATH, LOGO_PATH


def test_logo_is_transparent_1024_png() -> None:
    image = QImage(str(LOGO_PATH))

    assert not image.isNull()
    assert image.width() == 1024
    assert image.height() == 1024
    assert image.hasAlphaChannel()
    assert image.pixelColor(0, 0).alpha() == 0


def test_icon_contains_required_sizes() -> None:
    data = APP_ICON_PATH.read_bytes()
    reserved, icon_type, count = struct.unpack_from("<HHH", data)

    assert reserved == 0
    assert icon_type == 1
    assert count == 7

    sizes: set[tuple[int, int]] = set()
    for index in range(count):
        width, height = struct.unpack_from("<BB", data, 6 + index * 16)
        sizes.add((width or 256, height or 256))

    assert sizes == {
        (16, 16),
        (24, 24),
        (32, 32),
        (48, 48),
        (64, 64),
        (128, 128),
        (256, 256),
    }
