"""AWS Lambda entrypoint for the shared, stateless cloud editor backend.

Wraps the FastAPI app (in ``BIONODULO_EDITOR_MODE``) with Mangum so the
editing-support endpoints (node schemas, workflow validate/import/export,
manager/resolve, templates, host_status) run serverlessly behind a Lambda
Function URL — $0 when idle. The website reverse-proxies ``/api/editor/*`` here,
injecting the shared ``BIONODULO_PROXY_SECRET``.

Lifespan is disabled: editor mode creates no run queue / collab / redis, so
there is nothing to start or stop per invocation.
"""
from mangum import Mangum

from server import create_app

handler = Mangum(create_app(), lifespan="off")
