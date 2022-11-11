class EventError:
    # Generic
    UNKNOWN_ERROR = "unknown_error"

    # Schema validation
    INVALID_DATA = "invalid_data"
    INVALID_ATTRIBUTE = "invalid_attribute"
    MISSING_ATTRIBUTE = "missing_attribute"
    VALUE_TOO_LONG = "value_too_long"
    FUTURE_TIMESTAMP = "future_timestamp"
    PAST_TIMESTAMP = "past_timestamp"
    CLOCK_DRIFT = "clock_drift"
    INVALID_ENVIRONMENT = "invalid_environment"

    # Processing: Http
    SECURITY_VIOLATION = "security_violation"
    RESTRICTED_IP = "restricted_ip"
    FETCH_GENERIC_ERROR = "fetch_generic_error"
    FETCH_INVALID_HTTP_CODE = "fetch_invalid_http_code"
    FETCH_INVALID_ENCODING = "fetch_invalid_source_encoding"
    FETCH_TOO_LARGE = "fetch_too_large"
    FETCH_TIMEOUT = "fetch_timeout"
    TOO_LARGE_FOR_CACHE = "too_large_for_cache"

    # Processing: JavaScript
    JS_GENERIC_FETCH_ERROR = "js_generic_fetch_error"
    JS_RESTRICTED_IP = "js_restricted_ip"
    JS_SECURITY_VIOLATION = "js_security_violation"
    JS_TRUNCATED_URL = "js_truncated_url"
    JS_INVALID_URL = "js_invalid_url"
    JS_INVALID_HTTP_CODE = "js_invalid_http_code"
    JS_INVALID_CONTENT = "js_invalid_content"
    JS_NO_COLUMN = "js_no_column"  # deprecated in favor of JS_MISSING_ROW_OR_COLUMN
    JS_MISSING_ROW_OR_COLUMN = "js_missing_row_or_column"
    JS_INVALID_ROW_OR_COLUMN = "js_invalid_row_or_column"
    JS_MISSING_SOURCE = "js_no_source"  # TODO (kmclb) include things which used to be this in places where we check for this
    JS_MISSING_MINIFIED_SOURCE = "js_no_minified_source"
    JS_MISSING_ORIGINAL_SOURCE = "js_no_original_source"
    JS_INVALID_SOURCEMAP = "js_invalid_sourcemap"  # TODO (kmclb) look for UnparseableSourcemap
    JS_TOO_MANY_REMOTE_SOURCES = "js_too_many_sources"
    JS_INVALID_SOURCE_ENCODING = "js_invalid_source_encoding"
    JS_INVALID_SOURCEMAP_LOCATION = "js_invalid_sourcemap_location"
    JS_INVALID_STACKFRAME_LOCATION = "js_invalid_stackframe_location"
    JS_TOO_LARGE = (
        "js_too_large"  # deprecated in favor of JS_FETCH_TOO_LARGE and JS_TOO_LARGE_FOR_CACHE
    )
    JS_FETCH_TOO_LARGE = ("js_fetch_too_large",)
    JS_TOO_LARGE_FOR_CACHE = "js_too_large_for_cache"
    JS_FETCH_TIMEOUT = "js_fetch_timeout"
    JS_SCRAPING_DISABLED = "js_scraping_disabled"
    JS_UNKNOWN_ERROR = "js_unknown_error"

    # Processing: Native
    NATIVE_NO_CRASHED_THREAD = "native_no_crashed_thread"
    NATIVE_INTERNAL_FAILURE = "native_internal_failure"
    NATIVE_BAD_DSYM = "native_bad_dsym"
    NATIVE_MISSING_OPTIONALLY_BUNDLED_DSYM = "native_optionally_bundled_dsym"
    NATIVE_MISSING_DSYM = "native_missing_dsym"
    NATIVE_MISSING_SYSTEM_DSYM = "native_missing_system_dsym"
    NATIVE_MISSING_SYMBOL = "native_missing_symbol"
    NATIVE_SIMULATOR_FRAME = "native_simulator_frame"
    NATIVE_UNKNOWN_IMAGE = "native_unknown_image"
    NATIVE_SYMBOLICATOR_FAILED = "native_symbolicator_failed"

    # Processing: Proguard
    PROGUARD_MISSING_MAPPING = "proguard_missing_mapping"
    PROGUARD_MISSING_LINENO = "proguard_missing_lineno"

    _messages = {
        UNKNOWN_ERROR: "Unknown error",
        INVALID_DATA: "Discarded invalid value",
        INVALID_ATTRIBUTE: "Discarded unknown attribute",
        MISSING_ATTRIBUTE: "Missing value for required attribute",
        VALUE_TOO_LONG: "Discarded value due to exceeding maximum length",
        FUTURE_TIMESTAMP: "Invalid timestamp (in future)",
        PAST_TIMESTAMP: "Invalid timestamp (too old)",
        CLOCK_DRIFT: "Clock drift detected in SDK",
        INVALID_ENVIRONMENT: 'Environment cannot contain "/" or newlines',
        SECURITY_VIOLATION: "Cannot fetch resource because of a security violation",
        RESTRICTED_IP: "Cannot fetch resource because IP address is restricted",
        FETCH_GENERIC_ERROR: "Unable to fetch HTTP resource",
        FETCH_INVALID_HTTP_CODE: "HTTP request returned error response",
        FETCH_INVALID_ENCODING: "Source file was not encoded properly",
        FETCH_TOO_LARGE: "Remote file too large for downloading",
        FETCH_TIMEOUT: "Remote file took too long to load",
        TOO_LARGE_FOR_CACHE: "Remote file too large for caching",
        JS_GENERIC_FETCH_ERROR: "Unable to fetch resource",
        JS_RESTRICTED_IP: "Cannot fetch resource because IP address is restricted",
        JS_SECURITY_VIOLATION: "Cannot fetch resource because of a security violation",
        JS_TRUNCATED_URL: "Filename is truncated",
        JS_INVALID_URL: "URL is invalid",
        JS_INVALID_HTTP_CODE: "HTTP request returned error response",
        JS_INVALID_CONTENT: "Source file was not JavaScript",
        JS_NO_COLUMN: "Cannot apply sourcemap because stacktrace frame is missing column information",
        JS_MISSING_ROW_OR_COLUMN: "Cannot apply sourcemap because frame is missing row or column information",
        JS_INVALID_ROW_OR_COLUMN: "Cannot apply sourcemap because frame has invalid row or column information",
        JS_MISSING_SOURCE: "Source code was not found",
        JS_MISSING_MINIFIED_SOURCE: "Minified source code was not found",
        JS_MISSING_ORIGINAL_SOURCE: "Original source code was not found",
        JS_INVALID_SOURCEMAP: "Sourcemap was invalid or not parseable",
        JS_TOO_MANY_REMOTE_SOURCES: "The maximum number of remote source requests was made",
        JS_INVALID_SOURCE_ENCODING: "File was not encoded properly",
        JS_INVALID_SOURCEMAP_LOCATION: "Location from stackframe mapped to an invalid location in original code",
        JS_INVALID_STACKFRAME_LOCATION: "Location from stackframe doesn't exist in minified code",
        JS_TOO_LARGE: "Remote file too large for caching",
        JS_FETCH_TOO_LARGE: "Remote file too large for downloading",
        JS_TOO_LARGE_FOR_CACHE: "Remote file too large for caching",
        JS_FETCH_TIMEOUT: "Remote file took too long to load",
        JS_SCRAPING_DISABLED: "Web scraping is disabled",
        JS_UNKNOWN_ERROR: "Unknown error while attempting to appy source maps",
        NATIVE_NO_CRASHED_THREAD: "No crashed thread found in crash report",
        NATIVE_INTERNAL_FAILURE: "Internal failure when attempting to symbolicate",
        NATIVE_BAD_DSYM: "The debug information file used was broken",
        NATIVE_MISSING_OPTIONALLY_BUNDLED_DSYM: "An optional debug information file was missing",
        NATIVE_MISSING_DSYM: "A required debug information file was missing",
        NATIVE_MISSING_SYSTEM_DSYM: "A system debug information file was missing",
        NATIVE_MISSING_SYMBOL: "Could not resolve one or more frames in debug information file",
        NATIVE_SIMULATOR_FRAME: "Encountered an unprocessable simulator frame",
        NATIVE_UNKNOWN_IMAGE: "A binary image is referenced that is unknown",
        NATIVE_SYMBOLICATOR_FAILED: "Failed to process native stacktraces",
        PROGUARD_MISSING_MAPPING: "A proguard mapping file was missing",
        PROGUARD_MISSING_LINENO: "A proguard mapping file does not contain line info",
    }
    }

    @classmethod
    def get_message(cls, data):
        return cls(data).message

    def __init__(self, data):
        self._data = data

    @property
    def type(self):
        return self._data["type"]

    @property
    def data(self):
        return {k: v for k, v in self._data.items() if k != "type"}

    @property
    def message(self):
        return self._messages.get(self._data["type"], self._messages["unknown_error"])

    def get_api_context(self):
        return {"type": self.type, "message": self.message, "data": self.data}
