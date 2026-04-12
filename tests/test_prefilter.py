from app.services.processor.prefilter import should_filter, FilterReason


def test_filter_unsubscribe_email():
    item = {"source_type": "gmail", "raw_payload": {"headers": {"List-Unsubscribe": "<mailto:unsub@example.com>"}, "subject": "Weekly deals", "body": "Buy stuff"}}
    result = should_filter(item["source_type"], item["raw_payload"])
    assert result is not None
    assert result.reason == "newsletter_unsubscribe"


def test_filter_bounce_email():
    item = {"source_type": "gmail", "raw_payload": {"headers": {}, "from": "mailer-daemon@google.com", "subject": "Delivery failed", "body": "Message not delivered"}}
    result = should_filter(item["source_type"], item["raw_payload"])
    assert result is not None
    assert result.reason == "bounce"


def test_filter_noreply_email():
    item = {"source_type": "gmail", "raw_payload": {"headers": {}, "from": "noreply@somecompany.com", "subject": "Your receipt", "body": "Thanks for your purchase"}}
    result = should_filter(item["source_type"], item["raw_payload"])
    assert result is not None
    assert result.reason == "noreply_sender"


def test_pass_real_email():
    item = {"source_type": "gmail", "raw_payload": {"headers": {}, "from": "dan@partner.co", "subject": "Partnership update", "body": "Here's the latest..."}}
    result = should_filter(item["source_type"], item["raw_payload"])
    assert result is None


def test_filter_cancelled_calendar_event():
    item = {"source_type": "calendar", "raw_payload": {"status": "cancelled", "summary": "Team standup"}}
    result = should_filter(item["source_type"], item["raw_payload"])
    assert result is not None
    assert result.reason == "cancelled_event"


def test_filter_declined_calendar_event():
    item = {"source_type": "calendar", "raw_payload": {"status": "confirmed", "summary": "Team standup", "attendees": [{"email": "elliot@ntangible.com", "responseStatus": "declined"}], "self_email": "elliot@ntangible.com"}}
    result = should_filter(item["source_type"], item["raw_payload"])
    assert result is not None
    assert result.reason == "declined_event"


def test_pass_real_calendar_event():
    item = {"source_type": "calendar", "raw_payload": {"status": "confirmed", "summary": "Meeting with Alliance Sports", "attendees": [{"email": "elliot@ntangible.com", "responseStatus": "accepted"}], "self_email": "elliot@ntangible.com"}}
    result = should_filter(item["source_type"], item["raw_payload"])
    assert result is None


def test_pass_mcp_file_always():
    result = should_filter("mcp_file", {"file_name": "doc.pdf", "content": "Some text"})
    assert result is None


def test_pass_manual_upload_always():
    result = should_filter("manual_upload", {"file_name": "notes.txt", "content": "Some notes"})
    assert result is None
