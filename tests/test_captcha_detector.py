from scraper.captcha.detector import CaptchaDetector


def test_captcha_detector_recaptcha() -> None:
    det = CaptchaDetector([])
    html = "<html><div class='g-recaptcha'></div></html>"
    sig = det.detect(html)
    assert sig is not None
    assert sig.kind in {"recaptcha", "captcha", "custom"}


def test_captcha_detector_none() -> None:
    det = CaptchaDetector([])
    assert det.detect("<html><p>ok</p></html>") is None
