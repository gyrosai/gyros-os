"""Mapping de internal_ids do Pipefy pro pipe CIMI360 Curadoria 2026.

POR QUÊ separar em arquivo: esses IDs são acoplados ao pipe específico
(306947233). Quando o Gyros OS atender outro cliente Pipefy, vai ter
outro mapping. Isolar facilita ter pipe_id → mapping no futuro.

POR QUÊ os nomes são estranhos: alguns fields foram criados via "duplicar
field" na UI do Pipefy, herdando o internal_id do field original. Por
exemplo, o campo "Qual seu cargo?" tem internal_id `copy_of_qual_sua_uf`
porque foi duplicado do field "Qual sua UF?". A label visível na UI está
correta; o internal_id ficou com o nome herdado. NÃO renomear nada aqui:
o que vale na API GraphQL é o internal_id, não a label.
"""

from __future__ import annotations

CIMI360_2026_FIELD_IDS: dict[str, str] = {
    "nome_completo":     "nome_completo",
    "email":             "e_mail",
    "telefone":          "n_mero_de_telefone",
    "cpf":               "cpf",
    "empresa":           "empresa",
    "cargo":             "copy_of_qual_sua_uf",        # nome herdado, é "cargo" mesmo
    "cidade":            "qual_sua_cidade",
    "uf":                "qual_sua_uf",
    "linkedin":          "seu_perfil_no_linkedin",
    "instagram":         "seu_perfil_no_instagram",
    "minibio":           "fale_um_pouco_sobre_voc",
    "foto":              "anexe_aqui_sua_foto",        # JSON array de URLs assinadas
    "categoria_oficina": "copy_of_como_ficou_sabendo_do_cimi360",  # nome herdado, é multi-select
    "tema_oficina":      "sendo_instrutor_do_cimi360_quais_temas_conte_dos_voc_ensinaria_em_uma_oficina",
    "tema_outro":        "se_outros_foi_selecionado_escreva_aqui_qual_seria_o_tema",
}
