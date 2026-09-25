"""
ClientTracker - Unified & Backwards-Compatible Jinja2 Template Engine
====================================================================

Solves Starlette / FastAPI breaking signature changes where TemplateResponse
swapped parameter ordering between (name, context) and (request, name, context),
preventing 'TypeError: unhashable type: dict' across newer Starlette environments.
"""

from fastapi.templating import Jinja2Templates
from typing import Any, Dict, Optional


class CompatibleJinja2Templates(Jinja2Templates):
    """
    Subclass that gracefully adapts to both legacy (name, context)
    and modern (request=request, name=name, context=context) calling signatures.
    """

    def TemplateResponse(self, *args, **kwargs):
        # Case 1: Legacy positional signature: TemplateResponse("template.html", {"request": request, ...})
        if args and isinstance(args[0], str):
            name = args[0]
            context = args[1] if len(args) > 1 else kwargs.get("context", {})
            request = context.get("request") if isinstance(context, dict) else kwargs.get("request")
            status_code = args[2] if len(args) > 2 else kwargs.get("status_code", 200)
            headers = args[3] if len(args) > 3 else kwargs.get("headers")
            media_type = args[4] if len(args) > 4 else kwargs.get("media_type")
            background = args[5] if len(args) > 5 else kwargs.get("background")

            # Try modern Starlette signature (request as first/keyword arg)
            try:
                return super().TemplateResponse(
                    request=request,
                    name=name,
                    context=context,
                    status_code=status_code,
                    headers=headers,
                    media_type=media_type,
                    background=background
                )
            except TypeError:
                # Fallback to legacy signature
                return super().TemplateResponse(
                    name=name,
                    context=context,
                    status_code=status_code,
                    headers=headers,
                    media_type=media_type,
                    background=background
                )

        # Case 2: Already called with keyword args or modern positional
        return super().TemplateResponse(*args, **kwargs)


templates = CompatibleJinja2Templates(directory="app/templates")
