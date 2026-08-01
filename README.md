# fax.frizzle.lol

Send it a message, it prints on a thermal receipt printer.

## Input sources

Faxes arrive through *sources*, selected with `FAX_SOURCES` (comma separated,
default `discord`). Each source turns whatever it receives into a `Fax` and
hands it to the `FaxService`, which is the only thing that talks to the printer.

| source    | what it is                                                                            |
|-----------|---------------------------------------------------------------------------------------|
| `discord` | the bot: DMs and the `/fax` slash command                                              |
| `http`    | `POST /fax` with a bearer token — drives the smoke test, and is where email will land  |

See `.env.example` for the variables each one needs.

## dev

```sh
uv sync
```
```sh
uv run python bot.py
```

### tests

```sh
./bin/test        # unit tests and render regressions
./bin/smoke-test  # end to end: launches bot.py against a fake networked printer
```

Both are only really meaningful inside the devcontainer — the render path needs
the UnifontEX that the Dockerfile installs system-wide.
