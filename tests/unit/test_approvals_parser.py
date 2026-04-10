"""Testes unitários do parser de decisões de aprovação.

Função pura, sem I/O — toda a lógica do reconhecimento mora aqui, então
casos de borda devem ser cobertos. Falso-positivo é mais grave que
falso-negativo: melhor o usuário repetir do que aprovar algo errado.
"""

from gyros_os.approvals.parser import ApprovalDecision, parse_approval_decision


# ---------- Casos válidos: APROVAÇÃO ----------

def test_check_emoji_alone_is_approval_without_id():
    assert parse_approval_decision("✅") == ApprovalDecision("approve", None)


def test_check_emoji_with_id_space():
    assert parse_approval_decision("✅ 42") == ApprovalDecision("approve", 42)


def test_check_emoji_with_id_no_space():
    assert parse_approval_decision("✅42") == ApprovalDecision("approve", 42)


def test_aprova_word_alone():
    assert parse_approval_decision("aprova") == ApprovalDecision("approve", None)


def test_aprova_word_with_id():
    assert parse_approval_decision("aprova 7") == ApprovalDecision("approve", 7)


def test_aprova_case_insensitive():
    assert parse_approval_decision("APROVA") == ApprovalDecision("approve", None)
    assert parse_approval_decision("Aprova 13") == ApprovalDecision("approve", 13)


def test_aprovado_variant():
    assert parse_approval_decision("aprovado") == ApprovalDecision("approve", None)


def test_ok_is_NOT_approval_too_conversational():
    # "ok" é ambíguo demais — Camila pode estar só confirmando outra coisa.
    assert parse_approval_decision("ok") is None


def test_sim_is_NOT_approval_too_conversational():
    assert parse_approval_decision("sim") is None


# ---------- Casos válidos: REJEIÇÃO ----------

def test_x_emoji_alone_is_rejection():
    assert parse_approval_decision("❌") == ApprovalDecision("reject", None)


def test_x_emoji_with_id():
    assert parse_approval_decision("❌ 42") == ApprovalDecision("reject", 42)


def test_rejeita_word_with_id():
    assert parse_approval_decision("rejeita 7") == ApprovalDecision("reject", 7)


def test_cancela_alias():
    assert parse_approval_decision("cancela") == ApprovalDecision("reject", None)


# ---------- Whitespace tolerância ----------

def test_leading_trailing_whitespace_is_stripped():
    assert parse_approval_decision("   ✅  ") == ApprovalDecision("approve", None)
    assert parse_approval_decision("\t❌ 5\n") == ApprovalDecision("reject", 5)


# ---------- Falso-positivo: parser NÃO é ganancioso ----------

def test_check_with_extra_text_is_not_approval():
    assert parse_approval_decision("✅ acho que tá bom") is None


def test_check_inside_sentence_is_not_approval():
    assert parse_approval_decision("tudo bem ✅") is None


def test_aprova_with_extra_text_is_not_approval():
    assert parse_approval_decision("aprova essa ideia") is None


def test_random_message_is_not_approval():
    assert parse_approval_decision("oi tudo bem?") is None


def test_empty_string_returns_none():
    assert parse_approval_decision("") is None


def test_whitespace_only_returns_none():
    assert parse_approval_decision("   \n\t") is None


def test_number_alone_is_not_approval():
    # "42" sozinho não significa nada — ambíguo de propósito.
    assert parse_approval_decision("42") is None
