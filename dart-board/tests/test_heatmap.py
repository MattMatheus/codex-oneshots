from src.dart_board.heatmap import render_heatmap


def test_render_heatmap_png_signature():
    png = render_heatmap([(0.5, 0.5), (0.55, 0.45)])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 1000
