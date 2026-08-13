# Demo Target — House Conventions

This toy service has deliberate, consistently-applied conventions. The crew's reviewer
enforces them; the coder should (eventually) learn them from the brain instead of
being told. Seeded before the event as the demo fixture.

1. **Error envelope**: every non-2xx response body is
   `{"error": {"code": "<SCREAMING_SNAKE>", "message": "<human text>"}}` — raised via
   `app.errors.api_error(status, code, message)`, never a bare `HTTPException`.
2. **Handler naming**: route handlers are named `handle_<resource>_<verb>`
   (e.g. `handle_items_list`), snake_case, one resource per module in `app/routes/`.
3. **Response models**: every route declares `response_model=` with a Pydantic model
   defined in the same routes module, named `<Resource><Verb>Response`.
4. **Tests**: one test file per resource, functions named `test_<resource>__<behavior>`
   (double underscore between resource and behavior), using the shared `client` fixture.
5. **Style**: ruff, line length 100.
