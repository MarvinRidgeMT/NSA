import pytest

from tools.imagery.http_cache import BlockedError, PoliteCache


def test_html_rejection_is_not_cached_or_retried(tmp_path):
    calls = []

    def transport(url, timeout):
        calls.append(url)
        return b'\n<html>\n <head><title>Request Rejected</title></head></html>'
    c = PoliteCache(tmp_path, transport=transport, sleep=lambda s: None)
    with pytest.raises(BlockedError):
        c.get('https://archive.example/x.lbl', ext='lbl')
    assert len(calls) == 1
    assert not list(tmp_path.glob('*.lbl')) and not (tmp_path / 'MANIFEST.jsonl').exists()


def test_retry_then_success_and_rate_limit(tmp_path):
    n = [0]
    t = [0.0]
    sleeps = []

    def transport(url, timeout):
        n[0] += 1
        if n[0] == 1:
            raise IOError('timeout')
        return b'{"ok": 1}'

    def sleep(s):
        sleeps.append(s); t[0] += s
    c = PoliteCache(tmp_path, min_interval_s=2.0, transport=transport, sleep=sleep, clock=lambda: t[0])
    body, sha, p, hit = c.get('https://a.example/1')
    assert body == b'{"ok": 1}' and not hit and n[0] == 2 and sleeps == [5.0]
    c.get('https://a.example/2')
    assert sleeps[-1] == pytest.approx(2.0)  # 2 s since the last request to the same host
    body, _, _, hit = c.get('https://a.example/1')
    assert hit and n[0] == 3
