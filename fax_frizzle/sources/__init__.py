"""
Input sources: the things that turn some inbound message into a Fax.

Each module here exposes an async `run(service, ...)` that owns its own
transport and never returns. Everything downstream of the Fax lives in
fax_frizzle.service and knows nothing about any of them.
"""
