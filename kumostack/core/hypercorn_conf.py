# Copyright (c) 2026 KumoStack Contributors
# Copyright (c) 2024 MiniStack Contributors
# Licensed under the MIT License. See LICENSE for details.
"""Hypercorn config — applied via `-c file:` in the Dockerfile ENTRYPOINT.

Hypercorn's `from_pyfile` collects every non-module, non-dunder
module-level attribute and `setattr`s it onto the Config object, so the
exported names must match Hypercorn's own (lowercase `certfile` /
`keyfile`). When USE_SSL is unset (default), nothing is exported and
the listener stays plain HTTP — same behaviour as before this flag was
introduced.
"""

import kumostack.core.tls as _tls

if _tls.use_ssl_enabled():
    certfile, keyfile = _tls.resolve_tls_material()
