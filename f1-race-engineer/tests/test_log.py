from dashboard.log import EngineerLog


def test_engineer_log_maxlen_evicts_oldest():
    log = EngineerLog(maxlen=2)
    log.add_callout("t1", "first")
    log.add_callout("t2", "second")
    log.add_callout("t3", "third")

    snapshot = log.snapshot()

    assert len(snapshot) == 2
    assert snapshot[0]["text"] == "second"
    assert snapshot[1]["text"] == "third"


def test_engineer_log_qa_entry_shape():
    log = EngineerLog()
    log.add_qa("t1", "How's fuel?", "Fine, push on.")

    snapshot = log.snapshot()

    assert snapshot[0] == {"time": "t1", "type": "qa", "q": "How's fuel?", "text": "Fine, push on."}
