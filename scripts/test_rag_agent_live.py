"""Run an isolated n8n/Gemini/PGVector smoke test without publishing THE_X."""

import json
from pathlib import Path
import subprocess
import sys

from setup_n8n import COMPOSE, LOCAL, ROOT


SOURCE_ID = "theXOneRagDraft"
TEST_ID = "theXRagLiveSmoke"
TEST_NAME = "TEST ONLY - THE_X live RAG smoke"
QUESTIONS = [
    "Honda New GB350C ปี 2026 ปริมาตรกระบอกสูบกี่ซีซี? ใช้ข้อมูลสเปกในฐานเท่านั้น",
    "Honda New CB1000GT ปี 2026 เครื่องยนต์เป็นแบบใด? ใช้ข้อมูลสเปกในฐานเท่านั้น",
    "Honda รุ่น CB9999 ปี 2031 ปริมาตรกระบอกสูบกี่ซีซี? หากไม่มีข้อมูลให้บอกว่าไม่มี",
]
KEEP_NODES = {
    "THE_X AI Agent", "Google Gemini Chat Model", "Structured answer", "Validate answer",
    "Answer questions with a vector store", "Postgres PGVector Store",
    "Google Gemini - RAG answer", "Embeddings Google Gemini",
}


def compose(*args, capture=False):
    return subprocess.run([*COMPOSE, *args], cwd=ROOT, check=True,
                          capture_output=capture, text=capture, encoding="utf-8" if capture else None)


def summarize_output(output):
    start = output.rfind("\n{")
    if start < 0:
        raise ValueError("n8n did not return JSON execution data")
    execution = json.loads(output[start+1:])
    runs = execution["data"]["resultData"]["runData"]
    answers = [item["json"] for run in runs.get("THE_X AI Agent", [])
               for group in run.get("data", {}).get("main", []) if group for item in group]
    if len(answers) != len(QUESTIONS):
        raise ValueError(f"Expected {len(QUESTIONS)} AI answers, received {len(answers)}")
    report = []
    for question, answer in zip(QUESTIONS, answers):
        output_value = answer.get("output") or {}
        if isinstance(output_value, str):
            output_value = json.loads(output_value)
        report.append({"question": question, "reply": output_value.get("reply", ""),
                       "citation_ids": output_value.get("citation_ids", []),
                       "vector_tool_called": any(
                           step.get("action", {}).get("tool") == "Answer_questions_with_a_vector_store"
                           for step in answer.get("intermediateSteps", []))})
    checks = {
        "n8n_execution_success": execution.get("status") == "success",
        "vector_tool_called_for_every_question": all(item["vector_tool_called"] for item in report),
        "gb350c_displacement_correct": "348" in report[0]["reply"] and "GB350C" in report[0]["reply"],
        "cb1000gt_engine_correct": "DOHC" in report[1]["reply"] and "CB1000GT" in report[1]["reply"],
        "missing_model_not_invented": "ไม่มีข้อมูล" in report[2]["reply"] and "CB9999" in report[2]["reply"],
        "citations_unavailable_as_expected": all(item["citation_ids"] == [] for item in report),
    }
    return {"workflow_id": TEST_ID, "checks": checks, "cases": report,
            "started_at_utc": execution.get("startedAt"),
            "stopped_at_utc": execution.get("stoppedAt")}


def save_report(output):
    report = summarize_output(output)
    path = LOCAL / "rag-live-smoke-report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return print_report(report, path)


def print_report(report, path):
    for name, passed in report["checks"].items():
        print(f"{name}: {'PASS' if passed else 'FAIL'}")
    print(f"Report: {path}")
    return all(report["checks"].values())


def main():
    LOCAL.mkdir(parents=True, exist_ok=True)
    output_file = LOCAL / "rag-live-smoke-output.txt"
    if sys.argv[1:] == ["--report-only"]:
        path = LOCAL / "rag-live-smoke-report.json"
        if not print_report(json.loads(path.read_text(encoding="utf-8")), path):
            raise SystemExit("Live RAG smoke checks failed.")
        return
    source_file = LOCAL / "rag-live-smoke-source.json"
    test_file = LOCAL / "rag-live-smoke-import.json"
    try:
        compose("run", "--rm", "--no-deps", "-v", f"{LOCAL.as_posix()}:/output", "n8n",
                "export:workflow", f"--id={SOURCE_ID}", f"--output=/output/{source_file.name}")
        source = json.loads(source_file.read_text(encoding="utf-8"))[0]
        if source["id"] != SOURCE_ID or source["active"]:
            raise SystemExit("Expected the unpublished saved RAG draft.")
        projects = {entry.get("projectId") for entry in source.get("shared", [])
                    if entry.get("role") == "workflow:owner"}
        if len(projects) != 1:
            raise SystemExit("Cannot identify workflow owner project.")
        project_id = next(iter(projects))
        test = {key: value for key, value in source.items()
                if key not in {"shared", "createdAt", "updatedAt", "versionId", "triggerCount"}}
        test["id"], test["name"], test["active"] = TEST_ID, TEST_NAME, False
        test["nodes"] = [node for node in source["nodes"] if node["name"] in KEEP_NODES]
        if len(test["nodes"]) != len(KEEP_NODES):
            raise SystemExit("RAG nodes changed; no test workflow imported.")
        agent = next(node for node in test["nodes"] if node["name"] == "THE_X AI Agent")
        agent["parameters"]["options"]["returnIntermediateSteps"] = True
        test["nodes"].extend([
            {"id": "live-smoke-trigger", "name": "Manual test trigger",
             "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1,
             "position": [-900, 0], "parameters": {}},
            {"id": "live-smoke-questions", "name": "Prepare context",
             "type": "n8n-nodes-base.code", "typeVersion": 2,
             "position": [-650, 0],
             "parameters": {"mode": "runOnceForAllItems", "language": "javaScript",
                            "jsCode": "const questions = " + json.dumps(QUESTIONS, ensure_ascii=False) +
                            "; return questions.map(message => ({json:{message,history:[],sources:[]}}));"}},
        ])
        test["connections"] = {
            name: {kind: [[edge for edge in group if edge["node"] in KEEP_NODES]
                          for group in groups] for kind, groups in paths.items()}
            for name, paths in source["connections"].items() if name in KEEP_NODES
        }
        test["connections"].update({
            "Manual test trigger": {"main": [[{"node": "Prepare context", "type": "main", "index": 0}]]},
            "Prepare context": {"main": [[{"node": "THE_X AI Agent", "type": "main", "index": 0}]]},
        })
        # No memory or webhook is connected; this test cannot accept browser requests.
        test_file.write_text(json.dumps([test], ensure_ascii=False), encoding="utf-8")
        compose("run", "--rm", "--no-deps", "n8n", "import:workflow",
                f"--input=/bootstrap/{test_file.name}", f"--projectId={project_id}")
    finally:
        source_file.unlink(missing_ok=True)
        test_file.unlink(missing_ok=True)
    compose("restart", "n8n")
    result = compose("run", "--rm", "--no-deps", "n8n", "execute", f"--id={TEST_ID}",
                     "--rawOutput", capture=True)
    output_file.write_text(result.stdout, encoding="utf-8")
    if save_report(result.stdout):
        output_file.unlink(missing_ok=True)
    else:
        raise SystemExit("Live RAG smoke checks failed; raw output retained for debugging.")


if __name__ == "__main__":
    main()
