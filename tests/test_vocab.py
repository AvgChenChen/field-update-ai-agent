from field_agent.vocab import stated_text


def test_stated_text_drops_direct_questions():
    assert stated_text("Drywall waits until Thursday. Do they need another day?") == "Drywall waits until Thursday."


def test_stated_text_drops_embedded_questions():
    assert stated_text("Couldn't finish, can you check if they need another day") == "Couldn't finish,"
    assert stated_text("Ask the plumber whether it's two more days.") == ""


def test_stated_text_keeps_statements_around_questions():
    text = "Probably need another day. Can you tell the drywallers? Back Thursday."
    assert stated_text(text) == "Probably need another day. Back Thursday."


def test_stated_text_keeps_plain_if_clauses():
    # "if" alone isn't a question: a conditional statement still states a duration.
    assert stated_text("If it rains it's another day.") == "If it rains it's another day."
