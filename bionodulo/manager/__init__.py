__all__ = ["diagnose_workflow", "environment_status"]


def diagnose_workflow(*args, **kwargs):
    from bionodulo.manager.diagnostics import diagnose_workflow as _diagnose_workflow

    return _diagnose_workflow(*args, **kwargs)


def environment_status(*args, **kwargs):
    from bionodulo.manager.diagnostics import environment_status as _environment_status

    return _environment_status(*args, **kwargs)
