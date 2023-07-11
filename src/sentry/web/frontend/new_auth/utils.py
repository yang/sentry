from typing import Mapping, Optional

from django.http import (
    HttpResponse,
    HttpResponseRedirect,
)


def redirect(self, url: str, headers: Optional[Mapping[str, str]] = None) -> HttpResponse:
    pass


def redirect_with_headers(url: str, headers: Optional[Mapping[str, str]] = None) -> HttpResponse:
    res = HttpResponseRedirect(url)
    if headers:
        for k, v in headers.items():
            res[k] = v
    return res
