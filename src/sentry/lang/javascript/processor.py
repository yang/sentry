import base64
import errno
import logging
import re
import sys
import time
import zlib
from io import BytesIO
from os.path import splitext
from typing import IO, Optional, Tuple
from urllib.parse import urlsplit

import sentry_sdk
from django.conf import settings
from django.utils.encoding import force_bytes, force_text
from requests.utils import get_encoding_from_headers
from symbolic import SourceMapView

from sentry import http
from sentry.interfaces.stacktrace import Stacktrace
from sentry.models import EventError, Organization, ReleaseFile
from sentry.models.releasefile import ARTIFACT_INDEX_FILENAME, ReleaseArchive, read_artifact_index
from sentry.stacktraces.processing import StacktraceProcessor
from sentry.utils import json, metrics

# Separate from either the source cache or the source maps cache, this is for
# holding the results of attempting to fetch both kinds of files, either from the
# database or from the internet. Files are stored as partial URLResults.
from sentry.utils.cache import cache as file_cache
from sentry.utils.files import compress_file
from sentry.utils.hashlib import md5_text
from sentry.utils.http import is_valid_origin
from sentry.utils.retries import ConditionalRetryPolicy, exponential_delay
from sentry.utils.safe import get_path
from sentry.utils.urls import non_standard_url_join

from .cache import SourceCache, SourceMapCache

__all__ = ["JavaScriptStacktraceProcessor"]


# number of surrounding lines (on each side) to fetch
# TODO (kmclb) Why do we grab 7 for node but only 5 for browser?
LINES_OF_CONTEXT = 5
BASE64_SOURCEMAP_PREAMBLE = "data:application/json;base64,"
BASE64_PREAMBLE_LENGTH = len(BASE64_SOURCEMAP_PREAMBLE)
UNKNOWN_MODULE = "<unknown module>"
CLEAN_MODULE_RE = re.compile(
    r"""^
(?:/|  # Leading slashes
(?:
    (?:java)?scripts?|js|build|static|node_modules|bower_components|[_\.~].*?|  # common folder prefixes
    v?(?:\d+\.)*\d+|   # version numbers, v1, 1.0.0
    [a-f0-9]{7,8}|     # short sha
    [a-f0-9]{32}|      # md5
    [a-f0-9]{40}       # sha1
)/)+|
(?:[-\.][a-f0-9]{7,}$)  # Ending in a commitish
""",
    re.X | re.I,
)
VERSION_RE = re.compile(r"^[a-f0-9]{32}|[a-f0-9]{40}$", re.I)
NODE_MODULES_RE = re.compile(r"\bnode_modules/")
SOURCE_MAPPING_URL_RE = re.compile(b"//# sourceMappingURL=(.*)$")
CACHE_CONTROL_RE = re.compile(r"max-age=(\d+)")
CACHE_CONTROL_MAX = 7200
CACHE_CONTROL_MIN = 60
# the maximum number of remote resources (i.e. source files) that should be
# fetched (each bundle/sourcemap pair counts as 1 fetch)
MAX_RESOURCE_FETCHES = 100

CACHE_MAX_VALUE_SIZE = settings.SENTRY_CACHE_MAX_VALUE_SIZE

logger = logging.getLogger(__name__)


class UnparseableSourcemap(http.BadSource):
    error_type = EventError.JS_INVALID_SOURCEMAP


def trim_line(line, column=0):
    """
    Trims a line down to a goal of 140 characters (with a little wiggle room to
    be sensible) and tries to trim around the given `column` (the location of
    the error). So it tries to extract 60 characters before and after the
    provided `column` to yield a better context.
    """
    line = line.strip("\n")
    ll = len(line)
    if ll <= 150:
        return line
    # this should be caught by `get_source_context`, but just in case...
    if column > ll:
        column = ll
    start = max(column - 60, 0)
    # Round down if it brings us close to the edge
    if start < 5:
        start = 0
    end = min(start + 140, ll)
    # Round up to the end if it's close
    if end > ll - 5:
        end = ll
    # If we are bumped all the way to the end,
    # make sure we still get a full 140 characters in the line
    if end == ll:
        start = max(end - 140, 0)
    line = line[start:end]
    if end < ll:
        # we've snipped from the end
        line += " {snip}"
    if start > 0:
        # we've snipped from the beginning
        line = "{snip} " + line
    return line


def get_source_context(source, lineno, colno, context=LINES_OF_CONTEXT):
    """
    Attempt to harvest pre- and post-context lines of code from the given
    source. Returns a tuple of (precontext lines, line that errored, postcontext lines).
    """
    if not source:
        return None, None, None

    # We're asking for something that doesn't exist. Because the error should be
    # different depending on whether we're pulling from minified or original
    # code, throw a generic error here and catch it back where we know which one
    # we're dealing with
    if lineno > len(source) or colno > len(source[lineno]):
        raise http.BadSource()

    # lineno's in JS are 1-indexed, while line numbers in SourceMapViews are 0-indexed
    # (check that the number is positive just in case. sometimes math is hard)
    if lineno > 0:
        lineno -= 1

    lower_bound = max(0, lineno - context)
    upper_bound = min(lineno + 1 + context, len(source))

    try:
        pre_context = [trim_line(x) for x in source[lower_bound:lineno]]
    except IndexError:
        pre_context = []

    try:
        context_line = trim_line(source[lineno], colno)
    except IndexError:
        context_line = ""

    try:
        post_context = [trim_line(x) for x in source[(lineno + 1) : upper_bound]]
    except IndexError:
        post_context = []

    return pre_context or None, context_line, post_context or None


def discover_sourcemap(result):
    """
    Given a UrlResult object representing a minified file, attempt to discover a
    sourcemap URL.

    If the URL is relative, it's resolved into an absolute URL before being
    returned.
    """
    # When coercing the headers returned by urllib to a dict
    # all keys become lowercase so they're normalized
    sourcemap = result.headers.get("sourcemap") or result.headers.get("x-sourcemap")

    # Force the header value to bytes since we'll be manipulating bytes here
    sourcemap = force_bytes(sourcemap) if sourcemap is not None else None

    if not sourcemap:
        parsed_body = result.body.split(b"\n")
        # Source maps are only going to exist at either the top or bottom of the document.
        # Technically, there isn't anything indicating *where* it should exist, so we
        # are generous and assume it's somewhere either in the first or last 5 lines.
        # If it's somewhere else in the document, you're probably doing it wrong.
        if len(parsed_body) > 10:
            possibilities = parsed_body[:5] + parsed_body[-5:]
        else:
            possibilities = parsed_body

        # We want to scan each line sequentially, and the last one found wins
        # This behavior is undocumented, but matches what Chrome and Firefox do.
        for line in possibilities:
            if line[:21] in (b"//# sourceMappingURL=", b"//@ sourceMappingURL="):
                # We want everything AFTER the indicator, which is 21 chars long
                sourcemap = line[21:].rstrip()

        # If we still haven't found anything, check end of last line AFTER source code.
        # This is not the literal interpretation of the spec, but browsers support it.
        # e.g. {code}//# sourceMappingURL={url}
        if not sourcemap:
            # Only look at last 300 characters to keep search space reasonable (minified
            # JS on a single line could be tens of thousands of chars). This is a totally
            # arbitrary number / best guess; most sourceMappingURLs are relative and
            # not very long.
            search_space = possibilities[-1][-300:].rstrip()
            match = SOURCE_MAPPING_URL_RE.search(search_space)
            if match:
                sourcemap = match.group(1)

    if sourcemap:
        # react-native shoves a comment at the end of the
        # sourceMappingURL line.
        # For example:
        #  sourceMappingURL=app.js.map/*ascii:...*/
        # This comment is completely out of spec and no browser
        # would support this, but we need to strip it to make
        # people happy.
        if b"/*" in sourcemap and sourcemap[-2:] == b"*/":
            index = sourcemap.index(b"/*")
            # comment definitely shouldn't be the first character,
            # so let's just make sure of that.
            # TODO (kmclb) shouldn't the regex take care of this?
            if index == 0:
                raise AssertionError(
                    "react-native comment found at bad location: %d, %r" % (index, sourcemap)
                )
            sourcemap = sourcemap[:index]
        # fix url so it's absolute
        sourcemap = non_standard_url_join(result.url, force_text(sourcemap))

    return force_text(sourcemap) if sourcemap is not None else None


def get_release_file_cache_key(release_id, releasefile_ident):
    return f"releasefile:v1:{release_id}:{releasefile_ident}"


def get_release_file_cache_key_meta(release_id, releasefile_ident):
    return "meta:%s" % get_release_file_cache_key(release_id, releasefile_ident)


MAX_FETCH_ATTEMPTS = 3


def should_retry_fetch(attempt: int, e: Exception) -> bool:
    return not attempt > MAX_FETCH_ATTEMPTS and isinstance(e, OSError) and e.errno == errno.ESTALE


fetch_retry_policy = ConditionalRetryPolicy(should_retry_fetch, exponential_delay(0.05))


def fetch_and_cache_artifact(
    filename,
    fetch_fn,
    release_file_cache_key,
    release_file_metadata_cache_key,
    headers,
    compress_fn,
):
    # If the release file is not in cache, check if we can retrieve at
    # least the size metadata from cache and prevent compression and
    # caching if payload exceeds the backend limit.
    z_body_size = None

    if CACHE_MAX_VALUE_SIZE:
        cache_meta = file_cache.get(release_file_metadata_cache_key)
        if cache_meta:
            z_body_size = int(cache_meta.get("compressed_size"))

    def fetch_release_body():
        # `fetch_fn` has the name of the file to fetch baked in
        with fetch_fn() as fp:
            if z_body_size and z_body_size > CACHE_MAX_VALUE_SIZE:
                return None, fp.read()
            else:
                return compress_fn(fp)

    try:
        with metrics.timer("sourcemaps.release_file_read"):
            z_body, body = fetch_retry_policy(fetch_release_body)
    except Exception:
        logger.error("sourcemap.compress_read_failed", exc_info=sys.exc_info())
        result = None
    else:
        headers = {k.lower(): v for k, v in headers.items()}
        encoding = get_encoding_from_headers(headers)
        result = http.UrlResult(filename, headers, body, 200, encoding)

        # If we don't have the compressed body for caching because the
        # cached metadata said it is too large a payload for the cache
        # backend, do not attempt to cache.
        if z_body:
            # This will implicitly skip too large payloads. Those will be cached
            # on the file system by `ReleaseFile.cache`, instead.
            file_cache.set(release_file_cache_key, (headers, z_body, 200, encoding), 3600)

            # In case the previous call to cache implicitly fails, we use
            # the meta data to avoid pointless compression which is done
            # only for caching.
            file_cache.set(release_file_metadata_cache_key, {"compressed_size": len(z_body)}, 3600)

    return result


def get_cache_keys(filename, release, dist):
    dist_name = dist and dist.name or None
    releasefile_ident = ReleaseFile.get_ident(filename, dist_name)
    cache_key = get_release_file_cache_key(
        release_id=release.id, releasefile_ident=releasefile_ident
    )

    # Cache key to store file metadata (currently only the size of the
    # compressed version of file). We cannot use the cache_key because large
    # payloads (silently) fail to cache due to e.g. memcached payload size
    # limitation and we use the meta data to avoid compression of such  files.
    cache_key_meta = get_release_file_cache_key_meta(
        release_id=release.id, releasefile_ident=releasefile_ident
    )

    return cache_key, cache_key_meta


def result_from_cache(filename, result):
    # Previous caches would be a 3-tuple instead of a 4-tuple,
    # so this is being maintained for backwards compatibility
    # TODO (kmclb) the cache has long since turned over - can we axe this?
    try:
        encoding = result[3]
    except IndexError:
        encoding = None

    return http.UrlResult(filename, result[0], zlib.decompress(result[1]), result[2], encoding)


@metrics.wraps("sourcemaps.release_file")
def fetch_release_file(filename, release, dist=None):
    """
    Attempt to retrieve a release artifact from the database.

    Caches the result of that attempt (whether successful or not).
    """
    dist_name = dist.name if dist else None
    release_file_cache_key, release_file_metadata_cache_key = get_cache_keys(
        filename, release, dist
    )

    logger.debug("Checking cache for release artifact %r (release_id=%s)", filename, release.id)
    result = file_cache.get(release_file_cache_key)

    # not in the cache (meaning we haven't checked the database recently), so check the database
    if result is None:
        with metrics.timer("sourcemaps.release_artifact_from_file"):
            filename_choices = ReleaseFile.normalize(filename)
            filename_idents = [ReleaseFile.get_ident(f, dist_name) for f in filename_choices]

            logger.debug(
                "Checking database for release artifact %r (release_id=%s)", filename, release.id
            )

            possible_files = list(
                ReleaseFile.objects.filter(
                    release_id=release.id,
                    dist_id=dist.id if dist else None,
                    ident__in=filename_idents,
                ).select_related("file")
            )

            if len(possible_files) == 0:
                logger.debug(
                    "Release artifact %r not found in database (release_id=%s)",
                    filename,
                    release.id,
                )
                file_cache.set(release_file_cache_key, -1, 60)
                return None

            elif len(possible_files) == 1:
                releasefile = possible_files[0]

            else:
                # Pick first one that matches in priority order.
                # This is O(N*M) but there are only ever at most 4 things here
                # so not really worth optimizing.
                releasefile = next(
                    rf for ident in filename_idents for rf in possible_files if rf.ident == ident
                )

            logger.debug(
                "Found release artifact %r (id=%s, release_id=%s)",
                filename,
                releasefile.id,
                release.id,
            )

            result = fetch_and_cache_artifact(
                filename,
                lambda: ReleaseFile.cache.getfile(releasefile),
                release_file_cache_key,
                release_file_metadata_cache_key,
                releasefile.file.headers,
                compress_file,
            )

    # in the cache as an unsuccessful attempt
    elif result == -1:
        result = None

    # in the cache as a successful attempt, including the zipped contents of the file
    else:
        result = result_from_cache(filename, result)

    return result


@metrics.wraps("sourcemaps.get_from_archive")
def get_from_archive(url: str, archive: ReleaseArchive) -> Tuple[bytes, dict]:
    # TODO we should be matching on `ident` here, the way we do in
    # `fetch_release_file`, rather than just name (see
    # https://github.com/getsentry/sentry/issues/28048)
    candidates = ReleaseFile.normalize(url)
    for candidate in candidates:
        try:
            return archive.get_file_by_url(candidate)
        except KeyError:
            pass

    # None of the filenames matched
    raise KeyError(f"Not found in archive: '{url}'")


@metrics.wraps("sourcemaps.load_artifact_index")
def get_artifact_index(release, dist):
    dist_name = dist and dist.name or None

    ident = ReleaseFile.get_ident(ARTIFACT_INDEX_FILENAME, dist_name)
    artifact_index_cache_key = f"artifact-index:v1:{release.id}:{ident}"
    result = file_cache.get(artifact_index_cache_key)
    if result == -1:
        index = None
    elif result:
        index = json.loads(result)
    else:
        index = read_artifact_index(release, dist, use_cache=True)
        cache_value = -1 if index is None else json.dumps(index)
        # Only cache for a short time to keep the manifest up-to-date
        file_cache.set(artifact_index_cache_key, cache_value, timeout=60)

    return index


def get_index_entry(release, dist, url) -> Optional[dict]:
    try:
        index = get_artifact_index(release, dist)
    except Exception as exc:
        logger.error("sourcemaps.index_read_failed", exc_info=exc)
        return None

    if index:
        for candidate in ReleaseFile.normalize(url):
            entry = index.get("files", {}).get(candidate)
            if entry:
                return entry

    return None


@metrics.wraps("sourcemaps.fetch_release_archive")
def fetch_release_archive_for_url(release, dist, url) -> Optional[IO]:
    """Fetch release archive and cache if possible.

    Multiple archives might have been uploaded, so we need the URL
    to get the correct archive from the artifact index.

    If return value is not empty, the caller is responsible for closing the stream.
    """
    info = get_index_entry(release, dist, url)
    if info is None:
        # Cannot write negative cache entry here because ID of release archive
        # is not yet known
        return None

    archive_ident = info["archive_ident"]

    # TODO(jjbayer): Could already extract filename from info and return
    # it later

    archive_cache_key = get_release_file_cache_key(
        release_id=release.id, releasefile_ident=archive_ident
    )

    result = file_cache.get(archive_cache_key)

    if result == -1:
        return None
    elif result:
        return BytesIO(result)
    else:
        # archives are also stored in the ReleaseFile table (they're just files,
        # after all)
        qs = ReleaseFile.objects.filter(
            release_id=release.id, dist_id=dist.id if dist else dist, ident=archive_ident
        ).select_related("file")
        try:
            releasefile = qs[0]
        except IndexError:
            # This should not happen when there is an archive_ident in the manifest
            logger.error("sourcemaps.missing_archive", exc_info=sys.exc_info())
            # Cache as nonexistent:
            file_cache.set(archive_cache_key, -1, 60)
            return None
        else:
            try:
                file_ = fetch_retry_policy(lambda: ReleaseFile.cache.getfile(releasefile))
            except Exception:
                logger.error("sourcemaps.read_archive_failed", exc_info=sys.exc_info())

                return None

            # This will implicitly skip too large payloads.
            file_cache.set(archive_cache_key, file_.read(), 3600)
            file_.seek(0)

            return file_


def compress(fp: IO) -> Tuple[bytes, bytes]:
    """Alternative for compress_file when fp does not support chunks"""
    content = fp.read()
    return zlib.compress(content), content


def fetch_release_artifact(url, release, dist):
    """
    Attempt to retrieve a release artifact, either by extracting it from an
    archive or fetching it directly from the release. Returns None if the
    artifact can't be found.
    """
    release_file_cache_key, release_file_metadata_chache_key = get_cache_keys(url, release, dist)

    result = file_cache.get(release_file_cache_key)

    if result == -1:  # Cached as unavailable
        return None

    if result:
        return result_from_cache(url, result)

    start = time.monotonic()
    archive_file = fetch_release_archive_for_url(release, dist, url)
    if archive_file is not None:
        try:
            archive = ReleaseArchive(archive_file)
        except Exception as exc:
            logger.error("Failed to initialize archive for release %s", release.id, exc_info=exc)
            # TODO(jjbayer): cache error and return here
        else:
            with archive:
                try:
                    fp, headers = get_from_archive(url, archive)
                except KeyError:
                    # The manifest mapped the url to an archive, but the file
                    # is not there.
                    logger.error(
                        "Release artifact %r not found in archive %s", url, archive_file.id
                    )
                    file_cache.set(release_file_cache_key, -1, 60)
                    metrics.timing(
                        "sourcemaps.release_artifact_from_archive", time.monotonic() - start
                    )
                    return None
                except Exception as exc:
                    logger.error("Failed to read %s from release %s", url, release.id, exc_info=exc)
                    # TODO(jjbayer): cache error and return here
                else:
                    result = fetch_and_cache_artifact(
                        url,
                        lambda: fp,
                        release_file_cache_key,
                        release_file_metadata_chache_key,
                        headers,
                        # Cannot use `compress_file` because `ZipExtFile` does not support chunks
                        compress_fn=compress,
                    )
                    metrics.timing(
                        "sourcemaps.release_artifact_from_archive", time.monotonic() - start
                    )

                    return result

    # Fall back to maintain compatibility with old releases and versions of
    # sentry-cli which upload files individually
    result = fetch_release_file(url, release, dist)

    return result


def fetch_file(url, project=None, release=None, dist=None, allow_scraping=True):
    """
    Pull down a URL, returning a UrlResult object.

    (A UrlResult is really just a wrapper around various parts of an http
    response; for consistency, files which come from the database are presented
    in this format as well.)

    Attempts to fetch from the database first (assuming there's a release on the
    event), then the internet. Caches the result of each of those two attempts
    separately, whether or not those attempts are successful. Used for both
    minified source files and source maps.
    """
    # If our url has been truncated, it'd be impossible to fetch
    # so we check for this early and bail
    if url[-3:] == "...":
        raise http.CannotFetch(
            {
                "type": EventError.JS_TRUNCATED_URL,
                "url": http.expose_url(url),
                "phase": "fetch_file.precheck",
            }
        )

    # if we've got a release to look on, try that first (incl associated cache)
    if release:
        # the result, if found, will be tagged with a 200 OK, even though it's
        # not a web request
        result = fetch_release_artifact(url, release, dist)
    else:
        result = None

    # if it's not on the release, try the web-scraping cache

    webscraping_cache_key = f"source:cache:v4:{md5_text(url).hexdigest()}"

    if result is None:
        # if we can't scrape, the file can't be in the scraping cache, either,
        # so it's safe to bail before checking it if we fail either of these
        # checks
        if not allow_scraping:
            error = {
                "type": EventError.JS_SCRAPING_DISABLED,
                "url": http.expose_url(url),
                "phase": "fetch_file.web_scraping",
            }
            raise http.CannotFetch(error)
        if not url.startswith(("http:", "https:")):
            error = {
                "type": EventError.JS_INVALID_URL,
                "url": http.expose_url(url),
                "phase": "fetch_file.web_scraping",
            }
            raise http.CannotFetch(error)

        logger.debug("Checking cache for url %r", url)
        result = file_cache.get(webscraping_cache_key)
        if result is not None:
            # Previous caches would be a 3-tuple instead of a 4-tuple,
            # so this is being maintained for backwards compatibility
            # TODO (kmclb) the cache has long since turned over - remove this
            try:
                encoding = result[4]
            except IndexError:
                encoding = None
            # We got a cache hit, but the body is compressed, so we
            # need to decompress it before handing it off
            result = http.UrlResult(
                result[0], result[1], zlib.decompress(result[2]), result[3], encoding
            )

    # if it's not in the file cache, either, try to scrape the web
    if result is None:
        headers = {}
        verify_ssl = False
        if project and is_valid_origin(url, project=project):
            verify_ssl = bool(project.get_option("sentry:verify_ssl", False))
            token = project.get_option("sentry:token")
            if token:
                token_header = project.get_option("sentry:token_header") or "X-Sentry-Token"
                headers[token_header] = token

        with metrics.timer("sourcemaps.fetch"):
            try:
                result = http.fetch_file(url, headers=headers, verify_ssl=verify_ssl)
            except http.BadSource as err:
                # translate generic errors into JS-specific ones
                if err.type == EventError.RESTRICTED_IP:
                    err.type = EventError.JS_RESTRICTED_IP
                elif err.type == EventError.SECURITY_VIOLATION:
                    err.type = EventError.JS_SECURITY_VIOLATION
                elif err.type == EventError.FETCH_TIMEOUT:
                    err.type = EventError.JS_FETCH_TIMEOUT
                elif err.type == EventError.FETCH_TOO_LARGE:
                    err.type = EventError.JS_FETCH_TOO_LARGE
                elif err.type == EventError.FETCH_GENERIC_ERROR:
                    err.type = EventError.JS_GENERIC_FETCH_ERROR

                raise err

            # TODO (kmclb) Why do we even cache the result? If we have it, we
            # immediately make a sourceview out of it. Is it because the main
            # cache is shared by the whole server whereas the sourceview cache
            z_body = zlib.compress(result.body)
            file_cache.set(
                webscraping_cache_key,
                (url, result.headers, z_body, result.status, result.encoding),
                get_max_age(result.headers),
            )

            # the `cache.set` above can fail if the file is too large for the
            # cache. In that case we abort the fetch and cache a failure and
            # lock the domain for future http fetches.
            if file_cache.get(webscraping_cache_key) is None:
                error = {
                    "type": EventError.JS_TOO_LARGE,
                    "url": http.expose_url(url),
                    # We want size in megabytes to format nicely
                    "max_size": float(CACHE_MAX_VALUE_SIZE) / 1024 / 1024,
                    "phase": "fetch_file.web_scraping",
                }
                # TODO (kmclb) why lock the whole domain? why not just blacklist that one file?
                http.lock_domain(url, error=error)
                raise http.CannotFetch(error)

    # If we did not get a 200 OK (which could have come from the cache or a new
    # web request), just raise a cannot fetch here.
    if result.status != 200:
        raise http.CannotFetch(
            {
                "type": EventError.JS_INVALID_HTTP_CODE,
                "value": result.status,
                "url": http.expose_url(url),
                "phase": "fetch_file.web_scraping",
            }
        )

    # Make sure the file we're getting back is bytes. The only
    # reason it'd not be binary would be from old cached blobs, so
    # for compatibility with current cached files, let's coerce back to
    # binary and say utf8 encoding.
    # TODO (kmclb) this was 4 years ago - should be safe to remove
    if not isinstance(result.body, bytes):
        try:
            result = http.UrlResult(
                result.url,
                result.headers,
                result.body.encode("utf8"),
                result.status,
                result.encoding,
            )
        except UnicodeEncodeError:
            error = {
                "type": EventError.JS_INVALID_SOURCE_ENCODING,
                "value": "utf8",
                "url": http.expose_url(url),
                "phase": "process_file.pre_check",
            }
            raise http.CannotFetch(error)

    # For JavaScript files, check if content is something other than JavaScript/JSON (i.e. HTML)
    # NOTE: possible to have JS files that don't actually end w/ ".js", but
    # this should catch 99% of cases
    if urlsplit(url).path.endswith(".js"):
        # Check if first non-whitespace character is an open tag ('<'), which
        # will break both JS and JSON parsing. This most often happens when the
        # result is actually HTML, as can occur if the request is redirected to
        # a login screen. (We don't rely on the Content-Type header because apps
        # often don't set this correctly.)

        # Discard leading whitespace (often found before doctype)
        body_start = result.body[:50].lstrip()

        if body_start[:1] == b"<":
            error = {
                "type": EventError.JS_INVALID_CONTENT,
                "url": url,
                "content_start": body_start,
                "phase": "process_file.pre_check",
            }
            raise http.CannotFetch(error)

    return result


def get_max_age(headers):
    cache_control = headers.get("cache-control")
    max_age = CACHE_CONTROL_MIN

    if cache_control:
        match = CACHE_CONTROL_RE.search(cache_control)
        if match:
            max_age = max(CACHE_CONTROL_MIN, int(match.group(1)))
    return min(max_age, CACHE_CONTROL_MAX)


def fetch_sourcemap(url, project=None, release=None, dist=None, allow_scraping=True):
    # it's possible for the contents of the sourcemap to be embedded in the sourceMappingURL itself
    if is_data_uri(url):
        try:
            body = base64.b64decode(
                force_bytes(url[BASE64_PREAMBLE_LENGTH:])
                + (b"=" * (-(len(url) - BASE64_PREAMBLE_LENGTH) % 4))
            )
        except TypeError as e:
            raise UnparseableSourcemap({"url": "<base64>", "reason": str(e)})
    else:
        # look in the database and, if not found, optionally try to scrape the web
        # allow errors to bubble through to caller
        result = fetch_file(
            url,
            project=project,
            release=release,
            dist=dist,
            allow_scraping=allow_scraping,
        )
        body = result.body
    try:
        # A SourceMapView is an object created by parsing the sourcemap, to
        # which one can pass a location (and possibly a function name) from the
        # minified code and which will return information (line/col, filename,
        # function name, variable name) about the corresponding original code.
        return SourceMapView.from_json_bytes(body)
    except Exception as exc:
        # This is in debug because the product shows an error already.
        logger.debug(str(exc), exc_info=True)
        raise UnparseableSourcemap({"url": http.expose_url(url)})


def is_data_uri(url):
    return url[:BASE64_PREAMBLE_LENGTH] == BASE64_SOURCEMAP_PREAMBLE


def generate_module(src):
    """
    Converts a url into a made-up module name by doing the following:
     * Extracting just the path name, ignoring querystrings
     * Trimming off the initial /
     * Trimming off the file extension
     * Removing useless folder prefixes

    e.g. http://google.com/js/v1.0/foo/bar/baz.js -> foo/bar/baz
    """
    if not src:
        return UNKNOWN_MODULE

    filename, ext = splitext(urlsplit(src).path)
    if filename.endswith(".min"):
        filename = filename[:-4]

    # TODO(dcramer): replace CLEAN_MODULE_RE with tokenizer completely
    tokens = filename.split("/")
    for idx, token in enumerate(tokens):
        # a SHA
        if VERSION_RE.match(token):
            return "/".join(tokens[idx + 1 :])

    return CLEAN_MODULE_RE.sub("", filename) or UNKNOWN_MODULE


def is_valid_frame(frame):
    return frame is not None and frame.get("lineno") is not None


class JavaScriptStacktraceProcessor(StacktraceProcessor):
    """
    Attempts to fetch source code for javascript frames.

    Frames must match the following requirements:

    - lineno >= 0
    - colno >= 0
    - abs_path is the HTTP URI to the source
    - context_line is empty

    Mutates the input ``data`` with expanded context if available.
    """

    def __init__(self, *args, **kwargs):
        StacktraceProcessor.__init__(self, *args, **kwargs)

        # Make sure we only fetch organization from cache
        # We don't need to persist it back since we don't want
        # to bloat the Event object.
        organization = getattr(self.project, "_organization_cache", None)
        if not organization:
            organization = Organization.objects.get_from_cache(id=self.project.organization_id)
        self.allow_scraping = organization.get_option(
            "sentry:scrape_javascript", True
        ) is not False and self.project.get_option("sentry:scrape_javascript", True)

        # tally of the number of files scraped from the web (this gets
        # incremented whether the scraping was successful or not; a bundle and
        # its map only count as one fetch)
        self.fetch_count = 0
        self.max_fetches = MAX_RESOURCE_FETCHES

        self.sourcemaps_touched = set()

        # cache holding mangled code, original code, and errors associated with
        # each abs_path in the stacktrace
        self.sourceview_cache = SourceCache()

        # cache holding source URLs, corresponding source map URLs, and source map objects
        self.sourcemap_cache = SourceMapCache()

        self.release = None
        self.dist = None

    def get_stacktraces(self, data):
        exceptions = get_path(data, "exception", "values", filter=True, default=())
        stacktraces = [e["stacktrace"] for e in exceptions if e.get("stacktrace")]

        if "stacktrace" in data:
            stacktraces.append(data["stacktrace"])

        return [(s, Stacktrace.to_python(s)) for s in stacktraces]

    def get_valid_frames(self):
        # build list of frames that we can actually grab source for
        frames = []
        for info in self.stacktrace_infos:
            frames.extend(get_path(info.stacktrace, "frames", filter=is_valid_frame, default=()))
        return frames

    def preprocess_step(self, processing_task):
        """
        Attempts to cache necessary sources for all frames, both minified files
        and their associated sourcemaps.

        Returns True except in the case where none of the frames is valid and
        no work is done.
        """
        frames = self.get_valid_frames()
        if not frames:
            logger.debug(
                "Event %r has no frames with enough context to " "fetch remote source",
                self.data["event_id"],
            )
            return False

        with sentry_sdk.start_span(op="JavaScriptStacktraceProcessor.preprocess_step.get_release"):
            self.release = self.get_release(create=True)
            if self.data.get("dist") and self.release:
                self.dist = self.release.get_dist(self.data["dist"])

        with sentry_sdk.start_span(
            op="JavaScriptStacktraceProcessor.preprocess_step.populate_source_cache"
        ):
            self.populate_source_cache(frames)
        return True

    def handles_frame(self, frame, stacktrace_info):
        platform = frame.get("platform") or self.data.get("platform")
        return platform in ("javascript", "node")

    def preprocess_frame(self, processable_frame):
        # Stores the resolved token.  This is used to cross refer to other
        # frames for function name resolution by call site.
        processable_frame.data = {"token": None}

    def process_frame(self, processable_frame, processing_task):
        """
        Attempt to demangle the given frame.

        `processable_frame` is a frame along with its index and processor
        `processing_task` is all of the frames we're trying to process, indexed
        by both stacktrace and processor.
        """
        incoming_frame = processable_frame.frame
        minified_source = None
        original_source = None
        original_abs_path = None
        token = None
        in_app = None

        sourceview_cache = self.sourceview_cache
        sourcemaps_cache = self.sourcemap_cache
        all_errors = []
        sourcemap_applied = False

        # can't demangle if there's no filename
        if not incoming_frame.get("abs_path"):
            return  # skip frame with no error

        # also can't demangle node's internal modules
        # therefore we only process user-land frames (starting with /)
        # or those created by bundle/webpack internals
        if self.data.get("platform") == "node" and not incoming_frame.get("abs_path").startswith(
            ("/", "app:", "webpack:")
        ):
            return  # skip frame with no error

        minified_file_fetching_errors = sourceview_cache.get_errors(incoming_frame["abs_path"])
        all_errors.extend(minified_file_fetching_errors)

        # we also need line and column numbers
        if not incoming_frame.get("lineno") or not incoming_frame.get("colno"):
            all_errors.append(
                {
                    "type": EventError.JS_MISSING_ROW_OR_COLUMN,
                    "url": http.expose_url(incoming_frame["abs_path"]),
                    "row": incoming_frame.get("lineno"),
                    "column": incoming_frame.get("colno"),
                    "phase": "process_frame.precheck",
                }
            )
            return None, None, all_errors

        # finally, the line and column numbers must be valid (greater than 0,
        # since both are 1-indexed in stacktraces)
        if incoming_frame["lineno"] <= 0 or incoming_frame["colno"] <= 0:
            all_errors.append(
                {
                    "type": EventError.JS_INVALID_ROW_OR_COLUMN,
                    "url": http.expose_url(incoming_frame["abs_path"]),
                    "row": incoming_frame["lineno"],
                    "column": incoming_frame["colno"],
                    "phase": "process_frame.precheck",
                }
            )
            return None, None, all_errors

        minified_source = self.get_sourceview(incoming_frame["abs_path"])

        if not minified_source:
            # If we haven't already recorded some error fetching or caching the
            # file (which we should have, if it's not here), then give the user
            # a generic "welp, couldn't find it!" error
            if not minified_file_fetching_errors:
                all_errors.append(
                    {
                        "type": EventError.JS_MISSING_MINIFIED_SOURCE,
                        "url": http.expose_url(incoming_frame["abs_path"]),
                    }
                )

            # without the minified source, there's nothing we can do, because no
            # minified file means no `sourceMappingURL`, no `sourceMappingURL`
            # means no sourcemap, and no sourcemap means no sourcemapping, no
            # adding context lines, and also no ability to decide whether or not
            # the frame is in-app
            return None, None, all_errors

        new_frame = dict(incoming_frame)
        raw_frame = dict(incoming_frame)

        sourcemap_url, sourcemap_view = sourcemaps_cache.get_link(incoming_frame["abs_path"])
        if sourcemap_url:
            self.sourcemaps_touched.add(sourcemap_url)

            sourcemap_fetching_errors = sourceview_cache.get_errors(sourcemap_url)
            all_errors.extend(sourcemap_fetching_errors)

        # TODO (kmclb) if we have no sourcemap url we certainly have no
        # sourcemap view, so this entire thing can be nested under the
        # sourcemap_url check, which would then let us clean up the elif below
        if sourcemap_view:
            if is_data_uri(sourcemap_url):
                sourcemap_label = f"{http.expose_url(incoming_frame['abs_path'])} (inline)"
            else:
                sourcemap_label = http.expose_url(sourcemap_url)

            # If we have this, it, together with the minified code, should let
            # the SourceMapView give us an original function name. If it comes
            # back as None, we'll just got original file and location in the
            # token.
            minified_function_name = incoming_frame.get("function")

            try:
                # Subtract 1 because line numbers are 1-indexed in frames, but
                # 0-indexed in SourceMapViews
                token = sourcemap_view.lookup(
                    incoming_frame["lineno"] - 1,
                    incoming_frame["colno"] - 1,
                    minified_function_name,
                    minified_source,
                )
            except Exception:
                token = None
                all_errors.append(
                    {
                        "type": EventError.JS_INVALID_STACKFRAME_LOCATION,
                        "row": incoming_frame.get("lineno"),
                        "column": incoming_frame.get("colno"),
                        "source": incoming_frame["abs_path"],
                    }
                )

            # persist the token so that we can find it later
            processable_frame.data["token"] = token

            # Add sourcemap name to frame data
            new_frame["data"] = dict(incoming_frame.get("data") or {}, sourcemap=sourcemap_label)

            # Keep track of the fact that we tried (even if it didn't work)
            sourcemap_applied = True

            if token is not None:
                # this is the path to the original source file
                original_abs_path = non_standard_url_join(sourcemap_url, token.src)

                logger.debug(
                    "Mapping compressed source %r to mapping in %r",
                    incoming_frame["abs_path"],
                    original_abs_path,
                )

                # this is the original source code
                original_source = self.get_sourceview(original_abs_path)

                # Reverse the subtracting we did before, since now we're going
                # the other direction (`src_line` and `src_col` are the location
                # in the original source code)
                new_frame["lineno"] = token.src_line + 1
                new_frame["colno"] = token.src_col + 1

                # Try to use the function name we got from `symbolic`
                original_function_name = token.function_name

                # If symbolic wasn't able to reconstruct the original function
                # name, see if we by any chance have a function name from the
                # previous frame, and if so, use that.
                # TODO (kmclb) Why does this make sense?
                if original_function_name is None:
                    last_token = None

                    # Find the previous token for function name handling as a
                    # fallback.
                    if (
                        processable_frame.previous_frame
                        and processable_frame.previous_frame.processor is self
                    ):
                        last_token = processable_frame.previous_frame.data.get("token")
                        if last_token:
                            original_function_name = last_token.name

                if original_function_name is not None:
                    new_frame["function"] = original_function_name

                # this is the name of the original source file
                filename = token.src

                # special case webpack support
                # `abs_path` will always be the full path with `webpack:///` prefix,
                # and filename will be relative to that (`abs_path` here is the
                # path to the original source file)
                if original_abs_path.startswith("webpack:"):
                    filename = original_abs_path
                    # webpack seems to use ~ to imply "relative to resolver root"
                    # which is generally seen for third party deps
                    # (i.e. node_modules)
                    if "/~/" in filename:
                        filename = "~/" + original_abs_path.split("/~/", 1)[-1]
                    else:
                        filename = filename.split("webpack:///", 1)[-1]

                    # As noted above:
                    # * [js/node] '~/' means they're coming from node_modules, so these are not app dependencies
                    # * [node] sames goes for `./node_modules/` and '../node_modules/', which is used when bundling node apps
                    # * [node] and webpack, which includes its own code to bootstrap all modules and its internals
                    #   eg. webpack:///webpack/bootstrap, webpack:///external
                    if (
                        # TODO (kmclb) doesn't the third condition make the
                        # first one redundant? This whole business can probably
                        # be simplified a bit.
                        filename.startswith("~/")
                        or "/node_modules/" in filename
                        or not filename.startswith("./")
                    ):
                        in_app = False
                    # And conversely, local dependencies start with './'
                    elif filename.startswith("./"):
                        in_app = True

                    # We want to explicitly generate a webpack module name
                    new_frame["module"] = generate_module(filename)

                # while you could technically use a subpath of 'node_modules' for your libraries,
                # it would be an extremely complicated decision and we've not seen anyone do it
                # so instead we assume if `node_modules` is in the path it's third party code
                elif "/node_modules/" in original_abs_path:
                    in_app = False

                # TODO (kmclb) these two checks (above and below this comment)
                # do essentially the same thing
                if original_abs_path.startswith("app:"):
                    if filename and NODE_MODULES_RE.search(filename):
                        in_app = False
                    else:
                        in_app = True

                new_frame["abs_path"] = original_abs_path
                new_frame["filename"] = filename

                if not incoming_frame.get("module") and original_abs_path.startswith(
                    ("http:", "https:", "webpack:", "app:")
                ):
                    new_frame["module"] = generate_module(original_abs_path)

        elif sourcemap_url:
            new_frame["data"] = dict(
                new_frame.get("data") or {}, sourcemap=http.expose_url(sourcemap_url)
            )

        # TODO: theoretically a minified source could point to
        # another mapped, minified source

        # TODO (kmclb) this will be cleaner if it moves up into the `token is
        # not None` check above, but for now I didn't want to move things around
        # too-too much
        if original_source is not None:
            # `expand_frame` mutates the frame in place; `changed_frame` is a
            # boolean indicating whether `expand_frame` had any effect
            try:
                changed_frame = self.expand_frame(new_frame, source=original_source)
            except http.BadSource:
                all_errors.append(
                    {
                        "type": EventError.JS_INVALID_SOURCEMAP_LOCATION,
                        "row": new_frame["lineno"],
                        "column": new_frame["colno"],
                        "source": new_frame["abs_path"],
                    }
                )

        # successful sourcemapping but no original source code
        elif original_source is None and token is not None:
            # Unlike with the minified SourceView above, we won't have tried to
            # get this original SourceView by pulling it from the release or
            # scraping it off the web - if it exists, it will have come as part
            # of the sourcemap's `sourcesContent` entry. So even if it's
            # missing, we wouldn't expect to have any errors associated with its
            # URL, meaning there's no question (as there was above) about
            # whether or not we need to add an error.
            all_errors.append(
                {
                    "type": EventError.JS_MISSING_ORIGINAL_CODE,
                    "url": http.expose_url(original_abs_path),
                }
            )
        # we don't have either a token nor original source, in which case we
        # already will have raised a JS_INVALID_STACKFRAME_LOCATION error
        else:
            pass

        # we would have bailed long ago if we didn't have a minified SourceView,
        # so no need to check that here as we did with the original one
        try:
            # as above, `expand_frame` mutates the raw frame in place;
            # `changed_raw` is a boolean indicating whether `expand_frame` had
            # any effect

            # TODO (kmclb) why do we have to have a SourceMapView for
            # changed_raw to be True?
            changed_raw = sourcemap_applied and self.expand_frame(raw_frame)
        except http.BadSource:
            # if `token` is None, we've already raised this error (which makes
            # it unclear if logically it's even possible to land here, but we
            # handle it just in case)
            if token is not None:
                all_errors.append(
                    {
                        "type": EventError.JS_INVALID_STACKFRAME_LOCATION,
                        "row": incoming_frame.get("lineno"),
                        "column": incoming_frame.get("colno"),
                        "source": incoming_frame["abs_path"],
                    }
                )

        # this is unlikely, but if by this point we haven't managed to add
        # context lines to either the new or raw frames AND we don't have any
        # errors to explain why not, it's not worth continuing to process the
        # frame, so only do so if at least one of those is true

        # TODO (kmclb) `changed_frame` implies `sourcemap_applied`
        if sourcemap_applied or all_errors or changed_frame or changed_raw:
            # Unclear how this would happen, but if we've got errors and yet
            # still have somehow managed to get a context line for the new
            # frame, we should ignore the errors
            if bool(new_frame.get("context_line")):
                all_errors = []

            if in_app is not None:
                new_frame["in_app"] = in_app
                raw_frame["in_app"] = in_app

            new_frames = [new_frame]
            raw_frames = [raw_frame] if changed_raw else None
            return new_frames, raw_frames, all_errors

    def expand_frame(self, frame, source=None):
        """
        Mutate the given frame to include context and pre- and post-context lines.

        Returns a boolean indicating success or failure.
        """

        if frame.get("lineno") is not None:
            if source is None:
                source = self.get_sourceview(frame["abs_path"])
                if source is None:
                    logger.debug("No source found for %s", frame["abs_path"])
                    return False

            frame["pre_context"], frame["context_line"], frame["post_context"] = get_source_context(
                source=source, lineno=frame["lineno"], colno=frame.get("colno") or 0
            )
            return True
        return False

    def get_sourceview(self, filename):
        if filename not in self.sourceview_cache:
            # if we hit this, we haven't yet made an attempt to find this file
            # (any previous attempt would result in either the file or an error
            # being in the cache)
            self.cache_source(filename)
        return self.sourceview_cache.get(filename)

    def cache_source(self, filename):
        """
        Look for and (if found, cache) a minified source file and its associated
        source map (if any).
        """

        sourcemap_cache = self.sourcemap_cache
        sourceview_cache = self.sourceview_cache

        self.fetch_count += 1

        if self.fetch_count > self.max_fetches:
            # TODO (kmclb) Keep track of which files get booted this way?
            sourceview_cache.add_error(filename, {"type": EventError.JS_TOO_MANY_REMOTE_SOURCES})
            return

        # TODO: respect cache-control/max-age headers to some extent
        logger.debug("Attempting to cache source %r", filename)
        try:
            # this both looks in the database and tries to scrape the internet
            with sentry_sdk.start_span(
                op="JavaScriptStacktraceProcessor.cache_source.fetch_file"
            ) as span:
                span.set_data("filename", filename)
                result = fetch_file(
                    filename,
                    project=self.project,
                    release=self.release,
                    dist=self.dist,
                    allow_scraping=self.allow_scraping,
                )
        except http.BadSource as exc:
            # most people don't upload release artifacts for their third-party libraries,
            # so ignore problems with `node_modules` files
            if "node_modules" in filename:
                pass
            else:
                sourceview_cache.add_error(filename, exc.data)

            # either way, there's no more for us to do here, since we don't have
            # a valid file to cache
            return
        sourceview_cache.add(filename, result.body, result.encoding)

        # `result.url` is definitionally a full URL, while `filename` might use
        # `~`. By aliasing one to the other, we ensure we can find the minified
        # file under either name
        sourceview_cache.alias(result.url, filename)

        sourcemap_url = discover_sourcemap(result)
        if not sourcemap_url:
            return

        logger.debug(
            "Found sourcemap URL %r for minified script %r", sourcemap_url[:256], result.url
        )
        sourcemap_cache.link(filename, sourcemap_url)
        if sourcemap_url in sourcemap_cache:
            return

        # pull down sourcemap
        try:
            with sentry_sdk.start_span(
                op="JavaScriptStacktraceProcessor.cache_source.fetch_sourcemap"
            ) as span:
                span.set_data("sourcemap_url", sourcemap_url)
                # `sourcemap_view` is an object which will look up original
                # source code information given locations/function names from
                # minified code
                sourcemap_view = fetch_sourcemap(
                    sourcemap_url,
                    project=self.project,
                    release=self.release,
                    dist=self.dist,
                    allow_scraping=self.allow_scraping,
                )
        except http.BadSource as exc:
            # we don't perform the same check here as above, because if someone has
            # uploaded a node_modules file, which has a sourceMappingURL, they
            # presumably would like it mapped (and would like to know why it's not
            # working, if that's the case). If they're not looking for it to be
            # mapped, then they shouldn't be uploading the source file in the
            # first place.
            sourceview_cache.add_error(filename, exc.data)
            return

        sourcemap_cache.add(sourcemap_url, sourcemap_view)

        # cache any inlined original source code
        for src_id, source_name in sourcemap_view.iter_sources():
            # A SourceView is an object which wraps and gives access to code
            # from a single file (original or minified)
            source_view = sourcemap_view.get_sourceview(src_id)
            if source_view is not None:
                self.sourceview_cache.add(
                    non_standard_url_join(sourcemap_url, source_name), source_view
                )

    def populate_source_cache(self, frames):
        """
        Fetch all sources that we know are required (being referenced directly
        in frames).
        """
        pending_file_list = set()
        for f in frames:
            # We can't even attempt to fetch source if abs_path is None
            if f.get("abs_path") is None:
                continue
            # Chrome does a weird thing with anonymous callbacks of methods like
            # `Array.forEach`. (See
            # https://github.com/getsentry/sentry-javascript/issues/3800.) This
            # just bails early instead of exposing a fetch error that may be
            # confusing.
            if f["abs_path"] == "<anonymous>":
                continue

            # we cannot fetch any other files than those uploaded by user

            # TODO (kmclb) This is probably too restrictive - not everyone uses
            # RewriteFrames, and we'll just end up doing the same fetching
            # process later. We can just test for the inclusion of
            # `node_modules` in the abs_path, the abs_path starting with
            # `internal` (no slash), abs_paths with only a filename (like
            # `domain.js`), and any other indicator we might have that the frame
            # is internal to node itself.
            if self.data.get("platform") == "node" and not f.get("abs_path").startswith("app:"):
                continue
            pending_file_list.add(f["abs_path"])

        for idx, filename in enumerate(pending_file_list):
            with sentry_sdk.start_span(
                op="JavaScriptStacktraceProcessor.populate_source_cache.cache_source"
            ) as span:
                span.set_data("filename", filename)
                self.cache_source(filename=filename)

    def close(self):
        StacktraceProcessor.close(self)
        if self.sourcemaps_touched:
            metrics.incr(
                "sourcemaps.processed", amount=len(self.sourcemaps_touched), skip_internal=True
            )
