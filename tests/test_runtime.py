from __future__ import annotations

from grokenstein.runtime import ChatRuntime


def test_runtime_persists_history_and_handles_approvals(tmp_path):
    runtime = ChatRuntime(
        conversation_id="mysession",
        workspace_root=str(tmp_path / "workspace"),
        base_dir=tmp_path,
        model_backend="rule",
    )

    reply = runtime.handle_user_message("hello Grokenstein")
    assert "Grokenstein v0.0.4" in reply

    write_reply = runtime.handle_user_message("write hello-from-test to note.txt")
    assert "Approval required" in write_reply

    pending = runtime.broker.list_pending("mysession")
    assert len(pending) == 1
    approve_reply = runtime.handle_user_message(f"!approve {pending[0].request_id}")
    assert approve_reply == "OK"

    read_reply = runtime.handle_user_message("!fs read note.txt")
    assert read_reply == "hello-from-test"

    runtime.shutdown()

    restarted = ChatRuntime(
        conversation_id="mysession",
        workspace_root=str(tmp_path / "workspace"),
        base_dir=tmp_path,
        model_backend="rule",
    )
    history = restarted.handle_user_message("!history")
    assert "[YOU] hello Grokenstein" in history
    assert "[ASSISTANT]" in history
