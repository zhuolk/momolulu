from PIL import Image

from tools_cli.gif_pipeline import sample_background, analyze_frame, remove_background, grade


def solid(w, h, color, inner=None):
    im = Image.new("RGB", (w, h), color)
    if inner:
        for x in range(w // 4, w * 3 // 4):
            for y in range(h // 4, h * 3 // 4):
                im.putpixel((x, y), inner)
    return im


def test_sample_background_solid_and_gradient():
    assert sample_background(solid(40, 40, (255, 255, 255))) == (255, 255, 255)
    grad = Image.new("RGB", (40, 40))
    for x in range(40):
        for y in range(40):
            grad.putpixel((x, y), (x * 6, y * 6, (x + y) * 3))
    assert sample_background(grad) is None


def test_analyze_frame_ratios_on_solid_with_center_subject():
    im = solid(40, 40, (255, 255, 255), inner=(20, 120, 200))
    cleaned, edge = analyze_frame(im, (255, 255, 255))
    assert 0.60 <= cleaned <= 0.80 and edge == 1.0


def test_remove_background_border_transparent_subject_kept():
    im = solid(40, 40, (255, 255, 255), inner=(20, 120, 200))
    out = remove_background(im, (255, 255, 255))
    assert out.mode == "RGBA"
    assert out.getpixel((0, 0))[3] == 0 and out.getpixel((20, 20))[3] == 255


def test_remove_background_only_clears_connected_region():
    """被主体包围、不连通到边界的同色区域必须保留"""
    im = solid(40, 40, (255, 255, 255), inner=(20, 120, 200))
    for x in range(18, 22):
        for y in range(18, 22):
            im.putpixel((x, y), (255, 255, 255))
    assert remove_background(im, (255, 255, 255)).getpixel((20, 20))[3] == 255


def test_remove_background_clears_center_when_connected_to_border():
    """只验证连通性：erode=0 隔离掉腐蚀（腐蚀由 test_erode_* 单独覆盖）"""
    im = solid(40, 40, (255, 255, 255), inner=(20, 120, 200))
    for x in range(19, 21):
        for y in range(10, 30):
            im.putpixel((x, y), (255, 255, 255))
    assert remove_background(im, (255, 255, 255), erode=0).getpixel((20, 20))[3] == 0


def test_erode_shrinks_transparent_area_by_one_pixel():
    im = solid(40, 40, (255, 255, 255), inner=(20, 120, 200))
    assert remove_background(im, (255, 255, 255), erode=0).getpixel((9, 9))[3] == 0
    assert remove_background(im, (255, 255, 255), erode=1).getpixel((9, 9))[3] == 255


def test_grade_thresholds():
    assert grade(0.50, 1.00) == "easy"
    assert grade(0.90, 1.00) == "hard"      # 整图都是背景 → 必须判 hard，否则会输出全透明图
    assert grade(0.10, 0.40) == "medium"
    assert grade(0.03, 0.90) == "hard"
    assert grade(1.00, 1.00) == "hard"


def test_tiny_images_do_not_crash():
    assert sample_background(Image.new("RGB", (1, 1), (0, 0, 0))) == (0, 0, 0)
    assert remove_background(Image.new("RGB", (1, 1), (0, 0, 0)), (0, 0, 0)).size == (1, 1)
