import threading
import MCP_Server.state as state


class TestStateThreadSafety:
    def test_store_lock_exists(self):
        assert hasattr(state, 'store_lock')
        assert isinstance(state.store_lock, type(threading.Lock()))

    def test_concurrent_snapshot_access(self):
        """Multiple threads writing snapshots should not corrupt data."""
        errors = []

        def writer(thread_id):
            try:
                for i in range(100):
                    key = f"thread_{thread_id}_snap_{i}"
                    with state.store_lock:
                        state.snapshot_store[key] = {"data": i}
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(state.snapshot_store) == 500

    def test_browser_cache_ready_event(self):
        assert hasattr(state, 'browser_cache_ready')
        assert isinstance(state.browser_cache_ready, threading.Event)

    def test_ableton_connected_event(self):
        assert hasattr(state, 'ableton_connected_event')
        assert isinstance(state.ableton_connected_event, threading.Event)

    def test_effect_chain_store_exists(self):
        assert hasattr(state, 'effect_chain_store')
        assert isinstance(state.effect_chain_store, dict)
