"""
Regression tests for TelegramApprovalHandler's LOGIC — request/response
bookkeeping, timeout-as-denial, and malformed callback handling. These
run without any live network calls (bot.send_message is mocked).

Live button-tap behavior itself was verified manually against the real
bot (see M6 Step 4 verification) — that part cannot be meaningfully
unit tested, per the project's real-verification rule for live services.
"""

import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.telegram_bot.approval_handler import TelegramApprovalHandler
from app.core.types import PermissionLevel


def _make_handler_with_mock_bot():
    mock_application = MagicMock()
    mock_application.bot.send_message = AsyncMock(return_value=None)

    handler = TelegramApprovalHandler(mock_application, chat_id="123456")

    # Give it a real running loop via a background thread, so
    # run_coroutine_threadsafe has somewhere valid to schedule onto.
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    handler.set_loop(loop)

    return handler, mock_application, loop, thread


def test_request_approval_registers_pending_and_sends_message():
    handler, mock_app, loop, thread = _make_handler_with_mock_bot()
    try:
        result_holder = {}

        def _run():
            # Simulate the button tap arriving shortly after the request
            # is registered, by resolving it directly (bypassing Telegram).
            import time
            time.sleep(0.2)
            with handler._lock:
                assert len(handler._pending) == 1
                request_id = next(iter(handler._pending))
                pending = handler._pending[request_id]
            pending.answer = True
            pending.event.set()

        t = threading.Thread(target=_run)
        t.start()

        approved = handler.request_approval("delete_demo", PermissionLevel.DELETE, {"target": "x"})
        result_holder["approved"] = approved
        t.join()

        assert result_holder["approved"] is True
        assert mock_app.bot.send_message.await_count == 1
        # pending request cleaned up after resolution
        assert len(handler._pending) == 0
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2)


def test_request_approval_times_out_as_denial():
    handler, mock_app, loop, thread = _make_handler_with_mock_bot()
    try:
        # Force a very short timeout for the test instead of waiting 120s
        import app.telegram_bot.approval_handler as approval_module
        original_timeout = approval_module.APPROVAL_TIMEOUT_SECONDS
        approval_module.APPROVAL_TIMEOUT_SECONDS = 0.3
        try:
            approved = handler.request_approval("delete_demo", PermissionLevel.DELETE, {"target": "x"})
        finally:
            approval_module.APPROVAL_TIMEOUT_SECONDS = original_timeout

        assert approved is False
        assert len(handler._pending) == 0  # cleaned up even on timeout
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2)


@pytest.mark.asyncio
async def test_handle_callback_resolves_matching_pending_request():
    handler, mock_app, loop, thread = _make_handler_with_mock_bot()
    try:
        import threading as _threading
        from app.telegram_bot.approval_handler import _PendingApproval

        request_id = "abc123def456"
        pending = _PendingApproval(event=_threading.Event())
        handler._pending[request_id] = pending

        mock_update = MagicMock()
        mock_update.callback_query.data = f"approve:{request_id}:yes"
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.edit_message_text = AsyncMock()
        mock_update.callback_query.message.text = "some prompt text"

        await handler.handle_callback(mock_update, MagicMock())

        assert pending.answer is True
        assert pending.event.is_set()
        mock_update.callback_query.answer.assert_awaited_once()
        mock_update.callback_query.edit_message_text.assert_awaited_once()
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2)


@pytest.mark.asyncio
async def test_handle_callback_ignores_unknown_request_id():
    handler, mock_app, loop, thread = _make_handler_with_mock_bot()
    try:
        mock_update = MagicMock()
        mock_update.callback_query.data = "approve:doesnotexist:yes"
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.edit_message_text = AsyncMock()

        # Must not raise
        await handler.handle_callback(mock_update, MagicMock())

        mock_update.callback_query.edit_message_text.assert_awaited_once()
        call_text = mock_update.callback_query.edit_message_text.call_args[0][0]
        assert "expired" in call_text.lower()
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2)


@pytest.mark.asyncio
async def test_handle_callback_ignores_malformed_data():
    handler, mock_app, loop, thread = _make_handler_with_mock_bot()
    try:
        mock_update = MagicMock()
        mock_update.callback_query.data = "not:valid"  # missing 3rd segment
        mock_update.callback_query.answer = AsyncMock()
        mock_update.callback_query.edit_message_text = AsyncMock()

        # Must not raise
        await handler.handle_callback(mock_update, MagicMock())

        # No edit attempted since we bail out early on malformed data
        mock_update.callback_query.edit_message_text.assert_not_awaited()
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2)