import pytest

from bot import int_env


def test_int_env_reads_a_value(monkeypatch):
    monkeypatch.setenv('PORTISH', '9100')

    assert int_env('PORTISH', 1) == 9100


@pytest.mark.parametrize('value', [None, '', '   '])
def test_int_env_falls_back_to_the_default(monkeypatch, value):
    # A set-but-empty var is the interesting one: `PORTISH=` in a .env file
    # bypasses os.getenv's default, so it has to be handled here.
    if value is None:
        monkeypatch.delenv('PORTISH', raising=False)
    else:
        monkeypatch.setenv('PORTISH', value)

    assert int_env('PORTISH', 8080) == 8080


def test_int_env_exits_with_a_message_on_garbage(monkeypatch, capsys):
    monkeypatch.setenv('PORTISH', 'nine thousand')

    with pytest.raises(SystemExit) as excinfo:
        int_env('PORTISH', 8080)

    assert excinfo.value.code == 1
    assert 'PORTISH must be a whole number' in capsys.readouterr().out
