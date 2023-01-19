def test_one(live_server, session_browser):
    print("Test One.")
    print(f"live_server => {live_server.url}")
    session_browser.get(live_server.url)


def test_garbage_cookie(live_server, session_browser):
    # XXX: We explicitly set an extra garbage cookie, just so like in
    # production, there are more than one cookies set.
    #
    # This is the outcome of an incident where the acceptance tests failed to
    # capture an issue where cookie lookup in the frontend failed, but did NOT
    # fail in the acceptance tests because the code worked fine when
    # document.cookie only had one cookie in it.
    session_browser.save_cookie("acceptance_test_cookie", "1", live_server.url)

    session_browser.get(live_server.url)
