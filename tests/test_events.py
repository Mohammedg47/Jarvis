from jarvis.core.events import EventBus, State


def test_subscribers_get_state_changes_and_repeats_are_skipped():
    bus = EventBus()
    seen: list[State] = []
    bus.subscribe(seen.append)
    bus.emit(State.IDLE)  # already idle
    bus.emit(State.LISTENING)
    bus.emit(State.LISTENING)
    bus.emit(State.THINKING)
    assert seen == [State.LISTENING, State.THINKING]
    assert bus.state == State.THINKING


def test_failing_subscriber_does_not_block_others():
    bus = EventBus()
    seen: list[State] = []

    def broken(state: State) -> None:
        raise RuntimeError("boom")

    bus.subscribe(broken)
    bus.subscribe(seen.append)
    bus.emit(State.SPEAKING)
    assert seen == [State.SPEAKING]
