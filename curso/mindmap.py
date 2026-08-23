"""
curso/mindmap.py — Fase 2 do AI Course Generation Engine (ver
ai-course-engine-diagnostico.md, seção 8).

Mapa mental: Tema → Módulos → Conceitos → Subconceitos → Relações. NÃO
chama LLM — o CurriculumAgent já produziu essa estrutura inteira no
manifest (Fase 1); isto só reformata pra um formato nodes/edges que o
frontend consegue desenhar, e resolve os lesson_id reais (do Postgres,
via curso/store.list_lessons) pra permitir clicar num conceito e navegar
direto pra aula onde ele é ensinado.
"""

from __future__ import annotations


def build_mind_map(manifest: dict, lessons_reais: list[dict]) -> dict:
    """lessons_reais: saída de curso/store.list_lessons(course_id) — usada
    só pra casar título de aula -> lesson_id real (o manifest_json não
    guarda esse uuid). Retorna {"nodes": [...], "edges": [...]}."""
    titulo_para_id = {l["titulo"]: str(l["id"]) for l in lessons_reais}

    nodes = []
    edges = []

    root_id = "course"
    nodes.append({"id": root_id, "label": manifest.get("title", "Curso"), "type": "course"})

    for mi, modulo in enumerate(manifest.get("modules", [])):
        module_id = f"module-{mi}"
        nodes.append({"id": module_id, "label": modulo.get("title", ""), "type": "module"})
        edges.append({"from": root_id, "to": module_id})

        conceitos_vistos_no_modulo = set()
        for li, aula in enumerate(modulo.get("lessons", [])):
            lesson_node_id = f"lesson-{mi}-{li}"
            nodes.append({
                "id": lesson_node_id, "label": aula.get("title", ""), "type": "lesson",
                "lesson_id": titulo_para_id.get(aula.get("title")),
            })
            edges.append({"from": module_id, "to": lesson_node_id})

            for conceito in aula.get("concepts", []):
                # um conceito pode aparecer em mais de uma aula do mesmo
                # módulo — não duplica o nó, só liga de novo
                concept_node_id = f"concept-{mi}-{conceito}"
                if conceito not in conceitos_vistos_no_modulo:
                    nodes.append({"id": concept_node_id, "label": conceito, "type": "concept"})
                    conceitos_vistos_no_modulo.add(conceito)
                edges.append({"from": lesson_node_id, "to": concept_node_id})

    return {"nodes": nodes, "edges": edges}
